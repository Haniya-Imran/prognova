"""Module F - rolling-origin (time-aware) backtesting.

For each origin the model only sees months *before* the origin. It forecasts
the next ``h`` months, which are then compared with what really happened.
No random splits, and no information from the test months reaches training.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import ModelSpec
from .series import PreparedSeries


@dataclass
class Fold:
    origin: int                  # number of months in training
    train_end: pd.Timestamp      # last training month (month start)
    test_months: pd.DatetimeIndex


def make_folds(n_months: int, h: int, monthly_index: pd.DatetimeIndex, max_folds: int = 12) -> list[Fold]:
    """Choose origins so every fold has ``h`` real test months.

    With enough data the first origin keeps 15 (or 13) months of training, so yearly
    models can be tested fairly. With less, training starts from 3 months.
    """
    if n_months >= 15 + h + 5:      # keeps >= 6 windows and lets growth-adjusted models run
        min_train = 15
    elif n_months >= h + 13 + 1:
        min_train = 13
    else:
        min_train = max(3, n_months - h - 3)
    origins = list(range(min_train, n_months - h + 1))[-max_folds:]
    return [Fold(o, monthly_index[o - 1], monthly_index[o:o + h]) for o in origins]


def eligible(spec: ModelSpec, ps: PreparedSeries, folds: list[Fold]) -> tuple[bool, str]:
    if spec.needs_daily and ps.granularity != "daily":
        return False, f"Needs daily records; this data is {ps.granularity}."
    shortest = min(f.origin for f in folds) if folds else len(ps.monthly)
    if shortest < spec.min_months:
        return False, (f"Needs {spec.min_months} months of history; the earliest backtest window has "
                       f"{shortest}.")
    return True, "Eligible"


def run_backtest(spec: ModelSpec, ps: PreparedSeries, folds: list[Fold], h: int) -> dict:
    rows = []
    for f in folds:
        train_m = ps.monthly.iloc[:f.origin]
        cut = f.train_end + pd.offsets.MonthEnd(0)
        train_d = ps.daily[ps.daily.index <= cut]
        # Guard: training data must end strictly before the first test month.
        assert train_m.index[-1] < f.test_months[0] and train_d.index[-1] < f.test_months[0]
        pred = np.asarray(spec.fn(train_m, train_d, h), dtype=float)
        actual = ps.monthly.iloc[f.origin:f.origin + h].to_numpy()
        for i, (m, a, p) in enumerate(zip(f.test_months, actual, pred)):
            rows.append({"origin": f.train_end.strftime("%Y-%m"), "month": m.strftime("%Y-%m"),
                         "horizon": i + 1, "actual": float(a), "predicted": float(p)})
    return {"rows": rows}
