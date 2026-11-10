"""Module C - EDA Studio.

Computes the exploration once per dataset (it is cached by the workspace), so
opening the EDA page never re-scans a million rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..analytics.kpis import base_kpis

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _r(x, nd=2):
    if x is None:
        return None
    try:
        if np.isnan(x):
            return None
    except TypeError:
        pass
    return round(float(x), nd)


def _describe(s: pd.Series) -> dict:
    s = s.dropna()
    if s.empty:
        return {}
    q = s.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return {"count": int(len(s)), "mean": _r(s.mean()), "std": _r(s.std()), "min": _r(s.min()),
            "p05": _r(q[0.05]), "p25": _r(q[0.25]), "median": _r(q[0.5]), "p75": _r(q[0.75]),
            "p95": _r(q[0.95]), "max": _r(s.max()), "skew": _r(s.skew())}


def _log_hist(values: pd.Series, bins: int = 40) -> dict:
    v = values[values > 0]
    if v.empty:
        return {"edges": [], "counts": []}
    lo, hi = np.log10(v.min()), np.log10(v.max())
    edges = np.logspace(lo, hi if hi > lo else lo + 1, bins + 1)
    counts, edges = np.histogram(v, bins=edges)
    return {"edges": [_r(e, 4) for e in edges], "counts": counts.tolist(), "scale": "log"}


def overview(sales: pd.DataFrame, returns: pd.DataFrame, quality: dict, raw_columns: list[str]) -> dict:
    numeric = [c for c in ("quantity", "unit_price", "revenue") if c in sales]
    categorical = [c for c in ("order_id", "product", "category", "region", "store", "customer") if c in sales]
    stats = {c: _describe(sales[c]) for c in numeric}
    order_stats = None
    if "order_id" in sales:
        orders = sales.groupby("order_id", observed=True).agg(value=("revenue", "sum"), lines=("revenue", "size"))
        order_stats = {"order_value": _describe(orders["value"]), "lines_per_order": _describe(orders["lines"])}
    cards = {c: int(sales[c].nunique()) for c in categorical}
    return {
        "raw_rows": quality.get("rows"), "raw_columns": len(raw_columns), "column_names": raw_columns,
        "clean_rows": int(len(sales)), "return_rows": int(len(returns)) if returns is not None else 0,
        "date_min": sales["date"].min().strftime("%Y-%m-%d"), "date_max": sales["date"].max().strftime("%Y-%m-%d"),
        "numeric_columns": numeric, "categorical_columns": categorical, "cardinality": cards,
        "missing_cells": int(sum(m["missing"] for m in quality.get("missing", []))),
        "duplicate_rows": quality.get("duplicate_rows"),
        "line_stats": stats, "order_stats": order_stats,
        "totals": base_kpis(sales, returns),
    }


def distributions(sales: pd.DataFrame) -> dict:
    out = {"line_revenue": _log_hist(sales["revenue"])}
    if "order_id" in sales:
        ov = sales.groupby("order_id", observed=True)["revenue"].sum()
        out["order_value"] = _log_hist(ov)
        out["order_value_note"] = (f"Half of all orders are under {ov.median():,.0f}; the top 5% are above "
                                   f"{ov.quantile(0.95):,.0f}. A log scale is used because a few very large "
                                   f"orders would otherwise squash the chart.")
    if "unit_price" in sales:
        out["unit_price"] = _log_hist(sales["unit_price"])
    if "quantity" in sales:
        out["quantity"] = _log_hist(sales["quantity"])
    return out


def time_analysis(sales: pd.DataFrame, has_time: bool) -> dict:
    daily = sales.groupby("day")["revenue"].sum()
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max(), freq="D"), fill_value=0)
    weekly = daily.resample("W-MON", label="left", closed="left").sum()
    monthly = daily.resample("MS").sum()
    last = sales["day"].max()
    partial_last = (last.to_period("M").end_time.normalize() - last).days > 1
    m_full = monthly.iloc[:-1] if partial_last else monthly
    mom = m_full.pct_change() * 100
    yoy = (m_full / m_full.shift(12) - 1) * 100
    monthly_rows = []
    for p, v in monthly.items():
        complete = not (partial_last and p == monthly.index[-1])
        monthly_rows.append({"month": p.strftime("%Y-%m"), "revenue": _r(v), "complete": complete,
                             "mom_pct": _r(mom.get(p)) if complete else None,
                             "yoy_pct": _r(yoy.get(p)) if complete else None})
    yearly = []
    for y, grp in m_full.groupby(m_full.index.year):
        yearly.append({"year": int(y), "revenue": _r(grp.sum()), "months": int(len(grp)),
                       "full_year": len(grp) == 12})

    selling = daily[daily > 0]
    dow = selling.groupby(selling.index.dayofweek).mean().reindex(range(7))
    dow_days = selling.groupby(selling.index.dayofweek).size().reindex(range(7), fill_value=0)
    month_avg = m_full.groupby(m_full.index.month).mean()
    seas_index = (month_avg / month_avg.mean() * 100).reindex(range(1, 13))
    hour = None
    if has_time:
        h = sales.groupby(sales["date"].dt.hour)["revenue"].sum()
        hour = {"hours": [f"{int(x):02d}:00" for x in h.index], "revenue": [_r(v) for v in h.values]}

    peak = m_full.sort_values(ascending=False)
    roll = daily.rolling(28, min_periods=14)
    cv_daily = selling.std() / selling.mean() if len(selling) else None
    cv_monthly = m_full.std() / m_full.mean() if len(m_full) > 1 else None
    return {
        "daily": {"date": [d.strftime("%Y-%m-%d") for d in daily.index], "revenue": [_r(v) for v in daily.values],
                  "rolling_28d_mean": [_r(v) for v in roll.mean().values]},
        "weekly": {"week": [d.strftime("%Y-%m-%d") for d in weekly.index], "revenue": [_r(v) for v in weekly.values]},
        "monthly": monthly_rows,
        "yearly": yearly,
        "weekday": {"day": WEEKDAYS, "avg_revenue_per_selling_day": [_r(v) for v in dow.values],
                    "selling_days": dow_days.tolist()},
        "seasonality_index": {"month": MONTHS, "index": [_r(v, 1) for v in seas_index.values],
                              "note": "100 = an average month. 150 means 50% above an average month."},
        "hour": hour,
        "peak_months": [{"month": p.strftime("%b %Y"), "revenue": _r(v)} for p, v in peak.head(3).items()],
        "low_months": [{"month": p.strftime("%b %Y"), "revenue": _r(v)} for p, v in peak.tail(3)[::-1].items()],
        "volatility": {"daily_cv_pct": _r(cv_daily * 100 if cv_daily is not None else None),
                       "monthly_cv_pct": _r(cv_monthly * 100 if cv_monthly is not None else None),
                       "zero_sales_days": int((daily == 0).sum()), "total_days": int(len(daily)),
                       "note": "Coefficient of variation = standard deviation / average. Higher means bumpier sales."},
        "partial_last_month": bool(partial_last),
    }


def _dim_table(sales: pd.DataFrame, dim: str, n: int = 15) -> dict | None:
    if dim not in sales:
        return None
    agg = {"revenue": ("revenue", "sum"), "lines": ("revenue", "size")}
    if "quantity" in sales:
        agg["units"] = ("quantity", "sum")
    if "order_id" in sales:
        agg["orders"] = ("order_id", "nunique")
    agg["months_active"] = ("day", lambda d: d.dt.to_period("M").nunique())
    g = sales.groupby(dim, observed=True).agg(**agg)
    g = g[g.index.astype(str) != "Unknown"]
    total = sales["revenue"].sum()
    g["share_pct"] = g["revenue"] / total * 100
    # Growth: last 3 complete months vs the same 3 months a year earlier.
    last = sales["day"].max()
    end = (last.to_period("M") - (1 if (last.to_period("M").end_time.normalize() - last).days > 1 else 0))
    recent = pd.period_range(end - 2, end, freq="M")
    before = pd.period_range(end - 14, end - 12, freq="M")
    per = sales["day"].dt.to_period("M")
    r_now = sales[per.isin(recent)].groupby(dim, observed=True)["revenue"].sum()
    r_bef = sales[per.isin(before)].groupby(dim, observed=True)["revenue"].sum()
    if per.min() <= before[0]:
        g["growth_pct"] = (r_now.reindex(g.index) / r_bef.reindex(g.index) - 1) * 100
    else:
        g["growth_pct"] = np.nan
    g = g.sort_values("revenue", ascending=False)
    top = g.head(n)
    # "Lowest performers" only among items sold steadily, so one-off listings don't crowd the list.
    steady = g[g["months_active"] >= max(3, int(g["months_active"].median()))]
    bottom = steady.tail(n)[::-1]

    def rows(frame):
        out = frame.reset_index().rename(columns={dim: "name"})
        out["name"] = out["name"].astype(str)
        out = out.replace([np.inf, -np.inf], np.nan).round(2)
        return [{k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in rec.items()}
                for rec in out.to_dict("records")]

    growth_basis = (f"{recent[0].strftime('%b %Y')}-{recent[-1].strftime('%b %Y')} vs "
                    f"{before[0].strftime('%b %Y')}-{before[-1].strftime('%b %Y')}")
    return {"count": int(len(g)), "top": rows(top), "bottom": rows(bottom), "growth_basis": growth_basis,
            "top_share_pct": _r(top["share_pct"].sum())}


def dimensions(sales: pd.DataFrame) -> dict:
    return {d: _dim_table(sales, d) for d in ("product", "category", "region", "store")}


def correlation(sales: pd.DataFrame) -> dict | None:
    if "order_id" not in sales:
        daily = sales.groupby("day").agg(revenue=("revenue", "sum"), lines=("revenue", "size"))
        cols = daily
        level = "day"
    else:
        agg = {"order_value": ("revenue", "sum"), "lines": ("revenue", "size")}
        if "quantity" in sales:
            agg["units"] = ("quantity", "sum")
        if "unit_price" in sales:
            agg["avg_unit_price"] = ("unit_price", "mean")
        cols = sales.groupby("order_id", observed=True).agg(**agg)
        level = "order"
    if cols.shape[1] < 2:
        return None
    sp = cols.corr(method="spearman")
    labels = list(cols.columns)
    return {"level": level, "labels": labels, "spearman": sp.round(3).to_numpy().tolist(),
            "note": ("Spearman rank correlation per order (robust to the very large wholesale orders). "
                     "1 = always rise together, 0 = no link, -1 = move in opposite directions.")}


def returns_analysis(sales: pd.DataFrame, returns: pd.DataFrame) -> dict | None:
    if returns is None or returns.empty:
        return None
    gm = sales.groupby(sales["day"].dt.to_period("M"))["revenue"].sum()
    rm = returns.groupby(returns["date"].dt.to_period("M"))["revenue"].sum().abs()
    rows = [{"month": str(p), "returns": _r(rm.get(p, 0.0)), "rate_pct": _r(rm.get(p, 0.0) / v * 100) if v else None}
            for p, v in gm.items()]
    top = None
    if "product" in returns:
        t = returns.groupby("product", observed=True)["revenue"].sum().abs().sort_values(ascending=False).head(10)
        top = [{"name": str(k), "returns": _r(v)} for k, v in t.items()]
    return {"by_month": rows, "top_returned_products": top,
            "total_returns": _r(abs(returns["revenue"].sum())), "lines": int(len(returns))}


def run_eda(sales: pd.DataFrame, returns: pd.DataFrame, quality: dict, raw_columns: list[str], has_time: bool) -> dict:
    return {
        "overview": overview(sales, returns, quality, raw_columns),
        "distributions": distributions(sales),
        "time": time_analysis(sales, has_time),
        "dimensions": dimensions(sales),
        "correlation": correlation(sales),
        "returns": returns_analysis(sales, returns),
    }
