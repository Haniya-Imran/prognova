"""Module E - Interactive dashboard payload.

Returns chart-ready numbers (not images). The frontend draws them with Plotly,
so every bar and line is a real aggregate of the filtered data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .filters import Filters, apply
from .kpis import kpis

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def auto_grain(days: int) -> str:
    if days <= 92:
        return "day"
    if days <= 400:
        return "week"
    return "month"


def _series(frame: pd.DataFrame, grain: str) -> pd.DataFrame:
    rule = {"day": "D", "week": "W-MON", "month": "MS"}[grain]
    agg = {"revenue": ("revenue", "sum")}
    if "order_id" in frame:
        agg["orders"] = ("order_id", "nunique")
    if "quantity" in frame:
        agg["units"] = ("quantity", "sum")
    if frame.empty:
        return pd.DataFrame(columns=["period"] + list(agg))
    if grain == "week":
        key = frame["day"] - pd.to_timedelta(frame["day"].dt.dayofweek, unit="D")
    elif grain == "month":
        key = frame["day"].dt.to_period("M").dt.start_time
    else:
        key = frame["day"]
    g = frame.groupby(key).agg(**agg)
    full = pd.date_range(g.index.min(), g.index.max(), freq=rule if grain != "week" else "W-MON")
    g = g.reindex(full, fill_value=0)
    g.index.name = "period"
    return g.reset_index()


def _bars(frame: pd.DataFrame, dim: str, n: int = 10) -> list[dict] | None:
    if dim not in frame or frame.empty:
        return None
    agg = {"revenue": ("revenue", "sum")}
    if "quantity" in frame:
        agg["units"] = ("quantity", "sum")
    if "order_id" in frame:
        agg["orders"] = ("order_id", "nunique")
    g = frame.groupby(dim, observed=True).agg(**agg).sort_values("revenue", ascending=False)
    total = frame["revenue"].sum()
    g["share_pct"] = g["revenue"] / total * 100 if total else 0
    out = g.head(n).reset_index().rename(columns={dim: "name"})
    out["name"] = out["name"].astype(str)
    return out.round(2).to_dict("records")


def _heatmap(frame: pd.DataFrame, has_time: bool) -> dict | None:
    if frame.empty:
        return None
    if has_time:
        hours = frame["date"].dt.hour
        g = frame.groupby([frame["date"].dt.dayofweek, hours])["revenue"].sum().unstack(fill_value=0)
        hrs = list(range(int(hours.min()), int(hours.max()) + 1))
        g = g.reindex(index=range(7), columns=hrs, fill_value=0)
        return {"kind": "weekday_hour", "x": [f"{h:02d}:00" for h in hrs], "y": WEEKDAYS,
                "z": g.round(2).to_numpy().tolist(), "x_title": "Hour of day", "y_title": "Weekday"}
    g = frame.groupby([frame["day"].dt.dayofweek, frame["day"].dt.month])["revenue"].sum().unstack(fill_value=0)
    g = g.reindex(index=range(7), columns=range(1, 13), fill_value=0)
    return {"kind": "weekday_month", "x": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                            "Nov", "Dec"], "y": WEEKDAYS, "z": g.round(2).to_numpy().tolist(),
            "x_title": "Month", "y_title": "Weekday"}


def _year_overlay(frame: pd.DataFrame) -> list[dict]:
    if frame.empty:
        return []
    m = frame.groupby(frame["day"].dt.to_period("M"))["revenue"].sum()
    out = []
    for year in sorted({p.year for p in m.index}):
        vals = [float(m.get(pd.Period(f"{year}-{mm:02d}", "M"), np.nan)) for mm in range(1, 13)]
        out.append({"year": int(year), "values": [None if np.isnan(v) else round(v, 2) for v in vals]})
    return out


def _pareto(frame: pd.DataFrame) -> dict | None:
    if "product" not in frame or frame.empty:
        return None
    g = frame.groupby("product", observed=True)["revenue"].sum().sort_values(ascending=False)
    cum = g.cumsum() / g.sum() * 100
    n = len(g)
    top20 = max(int(round(n * 0.2)), 1)
    step = max(n // 200, 1)
    pts = [{"pct_products": round((i + 1) / n * 100, 2), "pct_revenue": round(float(cum.iloc[i]), 2)}
           for i in range(0, n, step)]
    return {"products": n, "top20_share_pct": round(float(cum.iloc[top20 - 1]), 2),
            "products_for_80pct": int((cum < 80).sum() + 1), "curve": pts}


def dashboard(sales: pd.DataFrame, returns: pd.DataFrame, f: Filters, grain: str | None, has_time: bool) -> dict:
    k = kpis(sales, returns, f)
    s = apply(sales, f)
    grain = grain or auto_grain(k["period"]["days"])
    ts = _series(s, grain)
    r = apply(returns, f) if returns is not None and len(returns) else pd.DataFrame()
    ret_series = []
    if len(r):
        rr = r.assign(day=r["date"].dt.normalize()).groupby(r["date"].dt.to_period("M"))["revenue"].sum().abs()
        gm = s.groupby(s["day"].dt.to_period("M"))["revenue"].sum()
        ret_series = [{"month": str(p), "returns": round(float(v), 2),
                       "rate_pct": round(float(v / gm[p] * 100), 2) if p in gm and gm[p] else None}
                      for p, v in rr.items()]
    return {
        "filters": f.as_dict(),
        "grain": grain,
        "kpis": k,
        "trend": {"period": [p.strftime("%Y-%m-%d") for p in ts["period"]],
                  **{c: ts[c].round(2).tolist() for c in ts.columns if c != "period"}},
        "top_products": _bars(s, "product", 12),
        "regions": _bars(s, "region", 12),
        "categories": _bars(s, "category", 12),
        "stores": _bars(s, "store", 12),
        "heatmap": _heatmap(s, has_time),
        "year_overlay": _year_overlay(s),
        "pareto": _pareto(s),
        "returns_by_month": ret_series,
        "empty": bool(s.empty),
    }


def dimension_values(sales: pd.DataFrame, dim: str, query: str = "", limit: int = 50) -> list[dict]:
    """Options for a filter dropdown, biggest sellers first, optional text search."""
    if dim not in sales:
        return []
    g = sales.groupby(dim, observed=True)["revenue"].sum().sort_values(ascending=False)
    names = g.index.astype(str)
    if query:
        g = g[names.str.contains(query, case=False, regex=False)]
    return [{"value": str(n), "revenue": round(float(v), 2)} for n, v in g.head(limit).items()]
