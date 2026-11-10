"""Module D - Sales Analytics Engine: KPI calculations.

A KPI is only produced when the columns it needs exist. Missing inputs give
``None`` plus a note, never an invented number.
"""
from __future__ import annotations

import pandas as pd

from .filters import Filters, apply, apply_dates, apply_dims, resolve_period


def _sum(frame: pd.DataFrame, col: str) -> float:
    return float(frame[col].sum()) if col in frame and len(frame) else 0.0


def base_kpis(sales: pd.DataFrame, returns: pd.DataFrame) -> dict:
    gross = _sum(sales, "revenue")
    ret = abs(_sum(returns, "revenue")) if returns is not None and len(returns) else 0.0
    k = {"gross_revenue": gross, "returns_value": ret, "net_revenue": gross - ret,
         "return_rate_pct": (ret / gross * 100) if gross > 0 else None,
         "lines": int(len(sales))}
    if "order_id" in sales:
        orders = int(sales["order_id"].nunique())
        k["orders"] = orders
        k["avg_order_value"] = gross / orders if orders else None
        k["items_per_order"] = len(sales) / orders if orders else None
    else:
        k["orders"] = k["avg_order_value"] = k["items_per_order"] = None
    k["units"] = _sum(sales, "quantity") if "quantity" in sales else None
    if "customer" in sales:
        known = sales["customer"].astype(str)
        k["customers"] = int(known[known != "Unknown"].nunique())
    else:
        k["customers"] = None
    days = sales["day"].nunique() if len(sales) else 0
    k["selling_days"] = int(days)
    k["avg_daily_revenue"] = gross / days if days else None
    return k


def _top(frame: pd.DataFrame, dim: str, by: str = "revenue") -> dict | None:
    if dim not in frame or frame.empty or by not in frame:
        return None
    g = frame.groupby(dim, observed=True)[by].sum()
    g = g[g.index.astype(str) != "Unknown"]
    if g.empty:
        return None
    total = frame[by].sum()
    return {"name": str(g.idxmax()), "value": float(g.max()), "share_pct": float(g.max() / total * 100) if total else None}


def _pct(now, before):
    if now is None or before in (None, 0):
        return None
    return (now / before - 1) * 100


def kpis(sales: pd.DataFrame, returns: pd.DataFrame, f: Filters) -> dict:
    s = apply(sales, f)
    r = apply(returns, f) if returns is not None and len(returns) else returns
    start, end = resolve_period(sales, f)
    cur = base_kpis(s, r)
    # Previous period of equal length, same non-date filters.
    length = (end - start).days + 1
    p_end = start - pd.Timedelta(days=1)
    p_start = p_end - pd.Timedelta(days=length - 1)
    s_dims = apply_dims(sales, f)
    r_dims = apply_dims(returns, f) if returns is not None and len(returns) else returns
    has_prev = p_start >= sales["day"].min()
    prev = base_kpis(apply_dates(s_dims, p_start, p_end), apply_dates(r_dims, p_start, p_end) if r_dims is not None and len(r_dims) else r_dims) if has_prev else None
    # Same period one year earlier.
    y_start, y_end = start - pd.DateOffset(years=1), end - pd.DateOffset(years=1)
    has_year = y_start >= sales["day"].min()
    year = base_kpis(apply_dates(s_dims, y_start, y_end), apply_dates(r_dims, y_start, y_end) if r_dims is not None and len(r_dims) else r_dims) if has_year else None

    growth = {}
    for key in ("gross_revenue", "net_revenue", "orders", "units", "avg_order_value", "customers"):
        growth[key] = {"vs_previous_period_pct": _pct(cur.get(key), prev.get(key)) if prev else None,
                       "vs_last_year_pct": _pct(cur.get(key), year.get(key)) if year else None}
    return {
        "period": {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"), "days": int(length)},
        "previous_period": {"start": p_start.strftime("%Y-%m-%d"), "end": p_end.strftime("%Y-%m-%d"),
                            "available": bool(has_prev)},
        "last_year_period": {"start": y_start.strftime("%Y-%m-%d"), "end": y_end.strftime("%Y-%m-%d"),
                             "available": bool(has_year)},
        "current": cur, "previous": prev, "last_year": year, "growth": growth,
        "best_product_by_revenue": _top(s, "product"),
        "best_product_by_units": _top(s, "product", "quantity"),
        "top_category": _top(s, "category"),
        "top_region": _top(s, "region"),
        "top_store": _top(s, "store"),
    }
