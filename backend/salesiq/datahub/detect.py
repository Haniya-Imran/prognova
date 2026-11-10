"""Module A - Data Hub: column role detection and validation."""
from __future__ import annotations

import re
import warnings

import numpy as np
import pandas as pd

from ..schema import ColumnMapping, REQUIRED_HELP

# Name hints per role, strongest first.
_NAME_HINTS: dict[str, list[str]] = {
    "date": ["order date", "invoicedate", "invoice date", "invoice_date", "transaction date", "sale date",
             "date", "datetime", "timestamp", "day", "period", "month", "time"],
    "revenue": ["revenue", "sales", "sale amount", "net sales", "total amount", "amount", "turnover",
                "line total", "total", "gmv", "value"],
    "quantity": ["quantity", "qty", "units", "unit sold", "units sold", "volume", "count"],
    "unit_price": ["unit price", "unitprice", "unit_price", "price", "rate", "selling price"],
    "order_id": ["invoice", "invoice no", "invoiceno", "order id", "order_id", "orderid", "order number",
                 "transaction id", "receipt", "bill"],
    "product": ["product name", "description", "product", "item", "item name", "sku", "stockcode",
                "stock code", "product id", "article"],
    "category": ["category", "sub-category", "subcategory", "department", "product line", "segment", "class"],
    "region": ["region", "country", "state", "city", "market", "territory", "zone", "province"],
    "store": ["store", "shop", "branch", "outlet", "location", "warehouse"],
    "customer": ["customer id", "customer_id", "customerid", "customer", "client", "buyer"],
}


def _norm(name: str) -> str:
    return re.sub(r"[\s_\-]+", " ", name.strip().lower())


def to_number(series: pd.Series) -> pd.Series:
    """Convert text to numbers, tolerating currency symbols, thousands separators and decimal commas."""
    s = series.astype("string").str.strip()
    s = s.str.replace(r"[\s$€£¥₹]|Rs\.?|PKR|USD", "", regex=True)
    sample = s.dropna().head(500)
    # European style "1.234,50" / "99,00": comma is the decimal mark.
    euro = sample.str.fullmatch(r"-?\d{1,3}(\.\d{3})*,\d{1,4}|-?\d+,\d{1,4}")
    if len(sample) and euro.mean() > 0.6:
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:
        s = s.str.replace(",", "", regex=False)
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)  # (12.5) accounting negatives
    return pd.to_numeric(s, errors="coerce")


_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d", "%Y-%m",
    # day-first is tried before month-first, so fully ambiguous dates (01/03/2024) read as 1 March
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%d/%m/%y %H:%M", "%d/%m/%y",
    "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y", "%m/%d/%y %H:%M", "%m/%d/%y",
    "%d.%m.%Y %H:%M", "%d.%m.%Y", "%d.%m.%y %H:%M", "%d.%m.%y", "%d-%m-%Y", "%m-%d-%Y",
    "%d-%b-%Y", "%d %b %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y", "%b-%y", "%b %Y",
]


def to_datetime(series: pd.Series) -> pd.Series:
    """Parse dates by picking the single format that reads the most values.

    One consistent format avoids mixing 03/04 as March in one row and April in another.
    """
    s = series.astype("string").str.strip()
    sample = s.dropna().head(1000)
    if sample.empty:
        return pd.to_datetime(s, errors="coerce")
    best, best_rate = None, 0.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for fmt in _DATE_FORMATS:
            rate = pd.to_datetime(sample, format=fmt, errors="coerce").notna().mean()
            if rate > best_rate + 1e-9:
                best, best_rate = fmt, rate
            if rate == 1.0:
                break
        if best is not None and best_rate >= 0.95:
            return pd.to_datetime(s, format=best, errors="coerce")
        iso = pd.to_datetime(s, errors="coerce", format="ISO8601")
        if iso.notna().mean() > 0.95:
            return iso
        return pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=True)


def _numeric_ratio(series: pd.Series) -> float:
    sample = series.dropna().head(1000)
    if sample.empty:
        return 0.0
    return float(to_number(sample).notna().mean())


def _date_ratio(series: pd.Series) -> float:
    sample = series.dropna().head(500)
    if sample.empty:
        return 0.0
    # Pure small integers (e.g. quantities) are not dates.
    if sample.astype(str).str.fullmatch(r"-?\d{1,6}").mean() > 0.8:
        return 0.0
    return float(to_datetime(sample).notna().mean())


def detect_columns(frame: pd.DataFrame) -> dict:
    """Suggest a role for each column, with a confidence score."""
    cols = list(frame.columns)
    normed = {c: _norm(c) for c in cols}
    numeric = {c: _numeric_ratio(frame[c]) for c in cols}
    taken: set[str] = set()
    suggestions: dict[str, dict] = {}

    def name_score(col: str, role: str) -> float:
        n = normed[col]
        for rank, hint in enumerate(_NAME_HINTS[role]):
            if n == hint:
                return 1.0 - rank * 0.01
        for rank, hint in enumerate(_NAME_HINTS[role]):
            if re.search(rf"\b{re.escape(hint)}\b", n):
                return 0.8 - rank * 0.01
        return 0.0

    order = ["date", "order_id", "quantity", "unit_price", "revenue", "customer",
             "category", "store", "region", "product"]
    for role in order:
        best, best_score = None, 0.0
        for col in cols:
            if col in taken:
                continue
            score = name_score(col, role)
            if score == 0:
                continue
            if role == "date":
                ratio = _date_ratio(frame[col])
                if ratio < 0.8:
                    continue
                score = score * 0.5 + ratio * 0.5
            elif role in ("revenue", "quantity", "unit_price"):
                if numeric[col] < 0.9:
                    continue
            if score > best_score:
                best, best_score = col, score
        if role == "date" and best is None:
            # Fall back to the column that parses best as dates.
            ratios = {c: _date_ratio(frame[c]) for c in cols if c not in taken and numeric[c] < 0.5}
            if ratios:
                c, r = max(ratios.items(), key=lambda kv: kv[1])
                if r >= 0.9:
                    best, best_score = c, 0.6 * r
        if best is not None:
            taken.add(best)
            suggestions[role] = {"column": best, "confidence": round(best_score, 2)}

    mapping = ColumnMapping(**{k: v["column"] for k, v in suggestions.items()})
    column_info = []
    for c in cols:
        s = frame[c]
        column_info.append({
            "name": c,
            "non_null": int(s.notna().sum()),
            "missing": int(s.isna().sum()),
            "unique": int(s.nunique(dropna=True)),
            "looks_numeric": numeric[c] >= 0.9,
            "examples": [str(v) for v in s.dropna().astype(str).unique()[:3]],
        })
    uncertain = [r for r, v in suggestions.items() if v["confidence"] < 0.75]
    return {
        "mapping": mapping.as_dict(),
        "confidence": {k: v["confidence"] for k, v in suggestions.items()},
        "uncertain_roles": uncertain,
        "columns": column_info,
    }


def validate_mapping(frame: pd.DataFrame, mapping: ColumnMapping) -> list[str]:
    """Return a list of problems; empty list means the mapping is usable."""
    errors: list[str] = []
    cols = set(frame.columns)
    for role, col in mapping.as_dict().items():
        if col and col not in cols:
            errors.append(f"Column '{col}' (chosen for {role}) is not in the file.")
    used = [c for c in mapping.used_columns()]
    if len(used) != len(set(used)):
        errors.append("The same column was chosen for more than one role.")
    if not mapping.date:
        errors.append("Choose the date column. " + REQUIRED_HELP)
    if not mapping.revenue and not (mapping.quantity and mapping.unit_price):
        errors.append("Choose a revenue column, or both quantity and unit price. " + REQUIRED_HELP)
    if errors:
        return errors
    if to_datetime(frame[mapping.date].dropna().head(2000)).notna().mean() < 0.8:
        errors.append(f"Column '{mapping.date}' does not look like dates (under 80% parse).")
    for role in ("revenue", "quantity", "unit_price"):
        col = getattr(mapping, role)
        if col and _numeric_ratio(frame[col]) < 0.8:
            errors.append(f"Column '{col}' (chosen for {role}) is not mostly numbers.")
    return errors


def detect_frequency(dates: pd.Series) -> dict:
    """Describe how often records occur: daily, weekly, monthly or irregular."""
    d = pd.Series(pd.to_datetime(dates.dropna()).dt.normalize().unique()).sort_values()
    if len(d) < 3:
        return {"frequency": "insufficient", "median_gap_days": None, "distinct_dates": int(len(d))}
    gaps = d.diff().dt.days.dropna()
    med = float(np.median(gaps))
    if med <= 1.5:
        freq = "daily"
    elif med <= 8:
        freq = "weekly"
    elif med <= 35:
        freq = "monthly"
    else:
        freq = "irregular"
    return {"frequency": freq, "median_gap_days": med, "distinct_dates": int(len(d))}
