"""Module B - Data Quality & Preparation.

Turns a raw table plus a column mapping into the canonical sales table that
every later stage uses. Every cleaning decision is logged with a row count so
the UI can explain exactly what happened.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..datahub.detect import detect_frequency, to_datetime, to_number
from ..schema import CleaningOptions, ColumnMapping

DIMENSIONS = ("product", "category", "region", "store", "customer")


@dataclass
class PreparedData:
    sales: pd.DataFrame          # valid positive sales lines (canonical columns)
    returns: pd.DataFrame        # returns / cancellations kept apart
    steps: list[dict] = field(default_factory=list)
    quality: dict = field(default_factory=dict)
    available: dict = field(default_factory=dict)  # which canonical roles exist
    has_time_of_day: bool = False


def _step(steps: list, name: str, rows: int, detail: str) -> None:
    steps.append({"step": name, "rows_affected": int(rows), "detail": detail})


def quality_report(raw: pd.DataFrame, mapping: ColumnMapping) -> dict:
    """Describe raw data health before anything is changed."""
    n = len(raw)
    missing = [
        {"column": c, "missing": int(raw[c].isna().sum()), "pct": round(float(raw[c].isna().mean() * 100), 2)}
        for c in raw.columns
    ]
    dup_rows = int(raw.duplicated().sum())
    types = []
    for c in raw.columns:
        s = raw[c].dropna().head(2000)
        num = to_number(s).notna().mean() if len(s) else 0
        types.append({"column": c, "inferred": "numeric" if num >= 0.9 else "text",
                      "role": next((r for r, v in mapping.as_dict().items() if v == c), None)})
    dates = to_datetime(raw[mapping.date])
    bad_dates = int(dates.isna().sum() - raw[mapping.date].isna().sum())
    value = _line_value(raw, mapping)
    neg = int((value < 0).sum())
    zero = int((value == 0).sum())
    pos = value[value > 0]
    if len(pos) > 10:
        q1, q3 = np.percentile(pos, [25, 75])
        upper = q3 + 3 * (q3 - q1)
        extreme = int((pos > upper).sum())
        outlier = {"method": "Line value above Q3 + 3*IQR", "threshold": round(float(upper), 2),
                   "count": extreme, "pct": round(extreme / max(len(pos), 1) * 100, 2),
                   "max_value": round(float(pos.max()), 2), "median_value": round(float(np.median(pos)), 2)}
    else:
        outlier = {"method": "Line value above Q3 + 3*IQR", "count": 0, "pct": 0}
    freq = detect_frequency(dates)
    return {
        "rows": n,
        "columns": int(raw.shape[1]),
        "missing": missing,
        "duplicate_rows": dup_rows,
        "column_types": types,
        "unparseable_dates": bad_dates,
        "negative_value_rows": neg,
        "zero_value_rows": zero,
        "outliers": outlier,
        "frequency": freq,
        "date_min": None if dates.dropna().empty else str(dates.min()),
        "date_max": None if dates.dropna().empty else str(dates.max()),
    }


def _line_value(raw: pd.DataFrame, mapping: ColumnMapping) -> pd.Series:
    if mapping.revenue:
        return to_number(raw[mapping.revenue])
    return to_number(raw[mapping.quantity]) * to_number(raw[mapping.unit_price])


def prepare(raw: pd.DataFrame, mapping: ColumnMapping, options: CleaningOptions | None = None) -> PreparedData:
    options = options or CleaningOptions()
    steps: list[dict] = []
    quality = quality_report(raw, mapping)
    df = raw.copy()
    _step(steps, "Loaded", len(df), f"{len(df):,} rows and {df.shape[1]} columns read from the file.")

    if options.drop_duplicates:
        before = len(df)
        df = df.drop_duplicates()
        _step(steps, "Removed exact duplicates", before - len(df),
              "Rows identical in every column were treated as double-recorded and kept once.")

    out = pd.DataFrame(index=df.index)
    out["date"] = to_datetime(df[mapping.date])
    if mapping.quantity:
        out["quantity"] = to_number(df[mapping.quantity])
    if mapping.unit_price:
        out["unit_price"] = to_number(df[mapping.unit_price])
    if mapping.revenue:
        out["revenue"] = to_number(df[mapping.revenue])
        rev_note = f"Revenue taken from '{mapping.revenue}'."
    else:
        out["revenue"] = out["quantity"] * out["unit_price"]
        rev_note = f"Revenue calculated as '{mapping.quantity}' x '{mapping.unit_price}'."
    _step(steps, "Revenue defined", 0, rev_note + " This is sales revenue, not profit (no cost data is used).")

    if mapping.order_id:
        out["order_id"] = df[mapping.order_id].astype("string").str.strip()
    for dim in DIMENSIONS:
        col = getattr(mapping, dim)
        if col:
            vals = df[col].astype("string").str.strip()
            if dim == "customer":
                vals = vals.str.replace(r"\.0$", "", regex=True)
            out[dim] = vals

    # Rows that cannot be used at all.
    bad_date = out["date"].isna()
    _step(steps, "Dropped rows without a valid date", int(bad_date.sum()),
          f"Dates that could not be read in '{mapping.date}' cannot be placed on the timeline.")
    out = out[~bad_date]
    bad_val = out["revenue"].isna()
    _step(steps, "Dropped rows without a numeric value", int(bad_val.sum()),
          "Rows whose sales value is blank or not a number.")
    out = out[~bad_val]

    # Non-merchandise lines (postage, fees, manual adjustments).
    if "product" in out and (options.non_merchandise_codes or options.non_merchandise_prefixes):
        codes = {c.upper() for c in options.non_merchandise_codes}
        pcode = out["product"].str.upper()
        mask = pcode.isin(codes)
        for p in options.non_merchandise_prefixes:
            mask |= pcode.str.startswith(p.upper()).fillna(False)
        mask = mask.fillna(False)
        _step(steps, "Removed non-product lines", int(mask.sum()),
              "Postage, carriage, bank charges, fees, manual adjustments, gift vouchers and test codes are not product sales.")
        out = out[~mask]

    # Returns and cancellations are kept apart.
    ret_mask = pd.Series(False, index=out.index)
    if options.separate_returns:
        ret_mask |= out["revenue"] < 0
        if "quantity" in out:
            ret_mask |= out["quantity"] < 0
        if options.cancellation_prefix and "order_id" in out:
            ret_mask |= out["order_id"].str.upper().str.startswith(options.cancellation_prefix.upper()).fillna(False)
    returns = out[ret_mask].copy()
    _step(steps, "Separated returns / cancellations", int(ret_mask.sum()),
          "Negative lines and cancelled invoices are reported as returns, not mixed into the sales trend.")
    out = out[~ret_mask]

    zero = out["revenue"] <= 0
    _step(steps, "Dropped zero-value lines", int(zero.sum()),
          "Lines with a price or value of 0 add no revenue (free samples or data-entry gaps).")
    out = out[~zero]

    for dim in DIMENSIONS:
        if dim in out:
            missing = out[dim].isna()
            if missing.any():
                label = "Unknown"
                out[dim] = out[dim].fillna(label)
                _step(steps, f"Filled missing {dim}", int(missing.sum()),
                      f"Missing {dim} labelled 'Unknown' so the sale still counts in totals.")

    out = out.sort_values("date").reset_index(drop=True)
    out["day"] = out["date"].dt.normalize()
    for dim in DIMENSIONS + ("order_id",):
        if dim in out:
            out[dim] = out[dim].astype("category")
    for col in ("revenue", "quantity", "unit_price"):
        if col in out:
            out[col] = out[col].astype("float64")

    has_time = bool((out["date"].dt.hour + out["date"].dt.minute).gt(0).mean() > 0.5) if len(out) else False
    available = {r: (r in out.columns) for r in ("quantity", "unit_price", "order_id") + DIMENSIONS}
    _step(steps, "Ready for analysis", len(out), f"{len(out):,} valid sales lines from "
          f"{out['date'].min():%d %b %Y} to {out['date'].max():%d %b %Y}." if len(out) else "No valid rows left.")
    return PreparedData(sales=out, returns=returns.reset_index(drop=True), steps=steps,
                        quality=quality, available=available, has_time_of_day=has_time)
