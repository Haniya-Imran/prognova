"""Module F - Forecasting Lab: candidate models.

Every model answers the same question: given history that ends at the end of a
month, what are the totals for the next ``h`` calendar months? Daily models
forecast every day and add the days up into calendar months, so the three
forecast values always line up exactly with three calendar months.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .ets import fit_forecast


@dataclass
class ModelSpec:
    key: str
    name: str
    family: str
    min_months: int
    needs_daily: bool
    description: str
    fn: Callable = field(repr=False)


def _month_starts(after: pd.Timestamp, h: int) -> pd.DatetimeIndex:
    return pd.date_range(after + pd.offsets.MonthBegin(1), periods=h, freq="MS")


def _days_to_months(values: np.ndarray, start: pd.Timestamp, h: int) -> np.ndarray:
    idx = pd.date_range(start, periods=len(values), freq="D")
    s = pd.Series(values, index=idx).resample("MS").sum()
    return s.iloc[:h].to_numpy()


def _horizon_days(last_month: pd.Timestamp, h: int) -> tuple[pd.Timestamp, int]:
    start = last_month + pd.offsets.MonthBegin(1)
    end = start + pd.offsets.MonthBegin(h) - pd.Timedelta(days=1)
    return start, int((end - start).days) + 1


# ---- monthly models ---------------------------------------------------------

def naive(monthly: pd.Series, daily: pd.Series, h: int) -> np.ndarray:
    return np.repeat(monthly.iloc[-1], h)


def seasonal_naive(monthly: pd.Series, daily: pd.Series, h: int) -> np.ndarray:
    return np.array([monthly.iloc[-12 + i] for i in range(h)])


def moving_average(monthly: pd.Series, daily: pd.Series, h: int) -> np.ndarray:
    return np.repeat(monthly.iloc[-3:].mean(), h)


def seasonal_naive_growth(monthly: pd.Series, daily: pd.Series, h: int) -> np.ndarray:
    recent = monthly.iloc[-3:].sum()
    year_ago = monthly.iloc[-15:-12].sum()
    growth = recent / year_ago if year_ago > 0 else 1.0
    growth = float(np.clip(growth, 0.5, 2.0))
    return np.array([monthly.iloc[-12 + i] * growth for i in range(h)])


def holt_damped(monthly: pd.Series, daily: pd.Series, h: int) -> np.ndarray:
    return fit_forecast(monthly.to_numpy(), h, trend=True, damped=True)


def holt_winters_monthly(monthly: pd.Series, daily: pd.Series, h: int) -> np.ndarray:
    return fit_forecast(monthly.to_numpy(), h, trend=True, damped=True, m=12, seasonal="mul")


# ---- daily models (summed into calendar months) -----------------------------

def ets_daily_weekly(monthly: pd.Series, daily: pd.Series, h: int) -> np.ndarray:
    start, n = _horizon_days(monthly.index[-1], h)
    hist = daily.iloc[-730:]
    fc = np.maximum(fit_forecast(hist.to_numpy(), n, trend=True, damped=True, m=7, seasonal="add"), 0)
    return _days_to_months(fc, start, h)


def _harmonic_design(idx: pd.DatetimeIndex, t0: pd.Timestamp, yearly: bool) -> np.ndarray:
    t = (idx - t0).days.to_numpy(dtype=float) / 365.25
    cols = [np.ones(len(idx)), t]
    dow = idx.dayofweek.to_numpy()
    for d in range(1, 7):
        cols.append((dow == d).astype(float))
    if yearly:
        doy = 2 * np.pi * idx.dayofyear.to_numpy() / 365.25
        for k in range(1, 5):
            cols += [np.sin(k * doy), np.cos(k * doy)]
    return np.column_stack(cols)


def harmonic_regression_daily(monthly: pd.Series, daily: pd.Series, h: int) -> np.ndarray:
    """Least squares on trend + day-of-week + yearly Fourier terms (dynamic harmonic regression)."""
    yearly = len(daily) >= 365
    t0 = daily.index[0]
    X = _harmonic_design(daily.index, t0, yearly)
    y = daily.to_numpy(dtype=float)
    # Small ridge penalty keeps Fourier terms stable with only ~2 years of data.
    lam = 1e-3 * len(y)
    reg = np.eye(X.shape[1]) * lam
    reg[0, 0] = 0
    beta = np.linalg.solve(X.T @ X + reg, X.T @ y)
    start, n = _horizon_days(monthly.index[-1], h)
    fidx = pd.date_range(start, periods=n, freq="D")
    fc = np.maximum(_harmonic_design(fidx, t0, yearly) @ beta, 0)
    return _days_to_months(fc, start, h)


CANDIDATES: list[ModelSpec] = [
    ModelSpec("naive", "Naive (last month)", "Baseline", 2, False,
              "Repeats the last complete month. The simplest benchmark every other model must beat.", naive),
    ModelSpec("seasonal_naive", "Seasonal naive (same month last year)", "Baseline", 13, False,
              "Uses the same month one year earlier. Captures yearly seasonality with no fitting.", seasonal_naive),
    ModelSpec("moving_average", "3-month moving average", "Baseline", 3, False,
              "Average of the last three months. Smooths noise but ignores seasonality.", moving_average),
    ModelSpec("seasonal_naive_growth", "Seasonal naive x recent growth", "Seasonal", 15, False,
              "Same month last year, scaled by how the last 3 months compare with the same 3 months a year earlier.",
              seasonal_naive_growth),
    ModelSpec("holt_damped", "Holt damped trend (ETS)", "Exponential smoothing", 8, False,
              "Exponential smoothing of level and a trend that flattens out. No seasonality.", holt_damped),
    ModelSpec("holt_winters_monthly", "Holt-Winters (12-month season)", "Exponential smoothing", 24, False,
              "Level, damped trend and a 12-month seasonal pattern. Needs at least two full years.",
              holt_winters_monthly),
    ModelSpec("ets_daily_weekly", "Daily Holt-Winters (weekly season)", "Exponential smoothing", 3, True,
              "Forecasts each day with a weekly pattern, then adds the days into calendar months.", ets_daily_weekly),
    ModelSpec("harmonic_regression_daily", "Dynamic harmonic regression (daily)", "Regression", 6, True,
              "Daily regression on trend, day-of-week and yearly sine/cosine waves, summed into calendar months.",
              harmonic_regression_daily),
]

NOT_USED = [
    {"name": "SARIMA", "reason": "A seasonal ARIMA with a 12-month season needs several full years to estimate "
     "its seasonal terms reliably; the monthly history here is too short, and daily SARIMA with yearly "
     "seasonality is too slow for an interactive app."},
    {"name": "Prophet", "reason": "Not installed: it needs a compiled Stan backend that is heavy for free "
     "hosting. The dynamic harmonic regression covers the same idea (trend + weekly + yearly waves)."},
]
