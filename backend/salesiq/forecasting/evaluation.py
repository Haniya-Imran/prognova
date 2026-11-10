"""Module F - forecast accuracy metrics."""
from __future__ import annotations

import numpy as np


def metrics(actual, predicted) -> dict:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    e = a - p
    abs_sum = np.abs(a).sum()
    out = {
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(e ** 2))),
        "wape": float(np.abs(e).sum() / abs_sum * 100) if abs_sum > 0 else None,
        "bias_pct": float(-e.sum() / abs_sum * 100) if abs_sum > 0 else None,  # + means over-forecast
        "n": int(len(a)),
    }
    denom = np.abs(a) + np.abs(p)
    out["smape"] = float(np.mean(np.where(denom > 0, 2 * np.abs(e) / np.where(denom > 0, denom, 1), 0)) * 100)
    # MAPE is misleading when any actual is near zero: only report it when all actuals are
    # at least 5% of the average level.
    level = np.mean(np.abs(a)) if len(a) else 0
    if level > 0 and np.all(np.abs(a) >= 0.05 * level):
        out["mape"] = float(np.mean(np.abs(e) / np.abs(a)) * 100)
        out["mape_note"] = None
    else:
        out["mape"] = None
        out["mape_note"] = "Not reported: some actual values are zero or close to zero."
    return out
