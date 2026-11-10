"""Shared fixtures.

Small hand-made CSVs here are *test inputs only*, used to check that each rule
does exactly what it says. They are never shown in the app as sales data.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PRELOAD_SAMPLE", "false")


@pytest.fixture
def tiny_csv() -> bytes:
    return (
        "Order ID,Order Date,Product,Region,Qty,Unit Price\n"
        "A1,2024-01-02,Lamp,North,2,10.00\n"
        "A1,2024-01-02,Chair,North,1,50.00\n"
        "A2,2024-01-03,Lamp,South,1,10.00\n"
        "A2,2024-01-03,Lamp,South,1,10.00\n"       # exact duplicate of the line above
        "A3,2024-01-05,Chair,South,-1,50.00\n"     # return
        "A4,not a date,Chair,South,1,50.00\n"      # unusable date
        "A5,2024-01-06,Desk,,1,0\n"                # zero value, missing region
    ).encode()


def _synthetic_daily(months: int = 30, seed: int = 0) -> pd.DataFrame:
    """Deterministic synthetic sales with weekly + yearly pattern, used to test the forecasting machinery."""
    rng = np.random.default_rng(seed)
    days = pd.date_range("2021-01-01", periods=months * 31, freq="D")
    days = days[days < pd.Timestamp("2021-01-01") + pd.DateOffset(months=months)]
    base = 1000 + 2 * np.arange(len(days))
    season = 1 + 0.4 * np.sin(2 * np.pi * (days.dayofyear - 240) / 365.25)
    weekly = np.where(days.dayofweek >= 5, 0.6, 1.0)
    rev = base * season * weekly * rng.lognormal(0, 0.05, len(days))
    return pd.DataFrame({"date": days, "order_id": [f"O{i}" for i in range(len(days))],
                         "product": rng.choice(["P1", "P2", "P3"], len(days)),
                         "region": rng.choice(["East", "West"], len(days)),
                         "quantity": rng.integers(1, 5, len(days)).astype(float), "revenue": rev})


@pytest.fixture
def synthetic_csv() -> bytes:
    df = _synthetic_daily()
    buf = io.StringIO()
    df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_csv(buf, index=False)
    return buf.getvalue().encode()


@pytest.fixture
def synthetic_frame() -> pd.DataFrame:
    return _synthetic_daily()
