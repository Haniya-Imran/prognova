"""Module F - Forecasting Lab: turn the canonical sales table into clean time series."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TARGETS = {
    "net_revenue": "Net revenue (sales minus returns)",
    "gross_revenue": "Gross revenue (sales before returns)",
    "units": "Units sold",
}


@dataclass
class PreparedSeries:
    daily: pd.Series            # one value per calendar day, zeros where nothing was sold
    monthly: pd.Series          # complete calendar months only (index = month start)
    granularity: str            # daily | weekly | monthly | irregular
    dropped_partial: list[str]  # months left out because they were not fully covered
    target: str


def _daily(sales: pd.DataFrame, returns: pd.DataFrame, target: str) -> pd.Series:
    if target == "units":
        if "quantity" not in sales:
            raise ValueError("This dataset has no quantity column, so units cannot be forecast.")
        s = sales.groupby("day")["quantity"].sum()
        if len(returns) and "quantity" in returns:
            s = s.add(returns.assign(day=returns["date"].dt.normalize()).groupby("day")["quantity"].sum(), fill_value=0)
    else:
        s = sales.groupby("day")["revenue"].sum()
        if target == "net_revenue" and len(returns):
            r = returns.assign(day=returns["date"].dt.normalize()).groupby("day")["revenue"].sum()
            s = s.add(-r.abs(), fill_value=0)
    if s.empty:
        return s
    idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(idx, fill_value=0.0).astype(float)


def granularity_of(days: pd.Index) -> str:
    d = pd.Series(pd.DatetimeIndex(days).unique()).sort_values()
    if len(d) < 3:
        return "irregular"
    med = d.diff().dt.days.dropna().median()
    if med <= 1.5:
        return "daily"
    if med <= 8:
        return "weekly"
    if med <= 35:
        return "monthly"
    return "irregular"


def build_series(sales: pd.DataFrame, returns: pd.DataFrame, target: str = "net_revenue") -> PreparedSeries:
    if target not in TARGETS:
        raise ValueError(f"Unknown target '{target}'.")
    if target == "net_revenue" and (returns is None or returns.empty):
        target = "gross_revenue"
    returns = returns if returns is not None else pd.DataFrame()
    gran = granularity_of(sales["day"]) if len(sales) else "irregular"
    daily = _daily(sales, returns, target)
    if daily.empty:
        return PreparedSeries(daily, pd.Series(dtype=float), gran, [], target)

    monthly = daily.resample("MS").sum()
    first, last = daily.index.min(), sales["day"].max()
    tol = {"daily": 1, "weekly": 7}.get(gran, 31)
    dropped = []
    # A month counts only if the data covers it from start to end.
    if (first - first.to_period("M").start_time).days > tol:
        dropped.append(first.strftime("%b %Y"))
        monthly = monthly.iloc[1:]
    month_end = last.to_period("M").end_time.normalize()
    if (month_end - last).days > tol and len(monthly):
        dropped.append(last.strftime("%b %Y"))
        monthly = monthly.iloc[:-1]
    monthly.index.freq = "MS"
    # Daily history used by daily models stops at the end of the last complete month.
    if len(monthly):
        cut = monthly.index[-1] + pd.offsets.MonthEnd(0)
        daily = daily[daily.index <= cut]
        start = monthly.index[0]
        daily = daily[daily.index >= start]
    return PreparedSeries(daily=daily, monthly=monthly, granularity=gran, dropped_partial=dropped, target=target)
