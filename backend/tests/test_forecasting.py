"""Forecasting Lab tests: splitting, leakage, baselines, metrics, intervals."""
import numpy as np
import pandas as pd
import pytest

from salesiq.datahub.sample import load_prepared
from salesiq.forecasting import models as M
from salesiq.forecasting.backtesting import make_folds
from salesiq.forecasting.engine import InsufficientHistory, run_forecast
from salesiq.forecasting.evaluation import metrics
from salesiq.forecasting.series import build_series


def _prep(frame):
    s = frame.copy()
    s["day"] = s["date"].dt.normalize()
    return s, pd.DataFrame(columns=s.columns)


def test_folds_are_chronological():
    idx = pd.date_range("2020-01-01", periods=24, freq="MS")
    folds = make_folds(24, 3, idx)
    assert len(folds) >= 6
    for f in folds:
        assert f.train_end < f.test_months[0]
        assert len(f.test_months) == 3
    origins = [f.origin for f in folds]
    assert origins == sorted(origins)


def test_no_future_leakage(synthetic_frame):
    """Changing values after an origin must not change that origin's forecast."""
    sales, ret = _prep(synthetic_frame)
    ps = build_series(sales, ret, "gross_revenue")
    k = 20
    train_m = ps.monthly.iloc[:k]
    cut = train_m.index[-1] + pd.offsets.MonthEnd(0)
    train_d = ps.daily[ps.daily.index <= cut]
    before = M.harmonic_regression_daily(train_m, train_d, 3)
    tampered = sales.copy()
    tampered.loc[tampered["date"] > cut, "revenue"] *= 50
    ps2 = build_series(tampered, ret, "gross_revenue")
    after = M.harmonic_regression_daily(ps2.monthly.iloc[:k], ps2.daily[ps2.daily.index <= cut], 3)
    assert np.allclose(before, after)


def test_baselines():
    idx = pd.date_range("2020-01-01", periods=15, freq="MS")
    m = pd.Series(np.arange(1, 16, dtype=float), index=idx)
    assert M.naive(m, None, 3).tolist() == [15, 15, 15]
    assert M.seasonal_naive(m, None, 3).tolist() == [4, 5, 6]
    assert M.moving_average(m, None, 3).tolist() == [14, 14, 14]


def test_daily_models_return_calendar_months(synthetic_frame):
    sales, ret = _prep(synthetic_frame)
    ps = build_series(sales, ret, "gross_revenue")
    out = M.ets_daily_weekly(ps.monthly, ps.daily, 3)
    assert len(out) == 3 and (out > 0).all()


def test_metrics_and_mape_guard():
    m = metrics([100, 200, 300], [110, 190, 300])
    assert m["mae"] == pytest.approx(20 / 3)
    assert m["wape"] == pytest.approx(20 / 600 * 100)
    assert m["mape"] is not None
    z = metrics([0, 100, 100], [5, 100, 100])
    assert z["mape"] is None and z["mape_note"]


def test_forecast_on_synthetic_beats_or_matches_baseline(synthetic_frame):
    sales, ret = _prep(synthetic_frame)
    r = run_forecast(sales, ret, "gross_revenue")
    assert r["status"] == "ok" and len(r["forecast"]) == 3
    months = [f["month"] for f in r["forecast"]]
    assert months == ["2023-07", "2023-08", "2023-09"]  # the 3 calendar months after the last complete one
    for f in r["forecast"]:
        assert f["lower_95"] <= f["lower_80"] <= f["forecast"] <= f["upper_80"] <= f["upper_95"]
    sel = next(c for c in r["candidates"] if c["selected"])
    assert sel["rank"] == 1
    base = min(c["metrics"]["wape"] for c in r["candidates"] if c.get("metrics") and c["family"] == "Baseline")
    assert sel["metrics"]["wape"] <= base


def test_insufficient_history(synthetic_frame):
    sales, ret = _prep(synthetic_frame[synthetic_frame["date"] < "2021-04-01"])
    with pytest.raises(InsufficientHistory):
        run_forecast(sales, ret, "gross_revenue")


def test_sample_forecast_end_to_end():
    p, _ = load_prepared()
    r = run_forecast(p.sales, p.returns, "net_revenue")
    assert r["trained_through"] == "November 2011"
    assert "Dec 2011" in r["dropped_partial_months"]
    assert [f["month"] for f in r["forecast"]] == ["2011-12", "2012-01", "2012-02"]
    elig = {c["key"]: c["eligible"] for c in r["candidates"]}
    assert elig["holt_winters_monthly"] is False  # needs 24 months in every window
    assert r["backtest"]["folds"] >= 6
    total = sum(f["forecast"] for f in r["forecast"])
    assert r["summary"]["total"] == pytest.approx(total, rel=1e-6)


def test_numpy_holt_winters_learns_seasonality():
    """The in-house smoothing (used instead of statsmodels) must pick up a clear 12-month pattern."""
    from salesiq.forecasting.ets import fit_forecast
    season = np.array([80, 70, 90, 85, 95, 100, 98, 102, 120, 140, 180, 150], float)
    y = np.concatenate([season * (1 + 0.05 * k) for k in range(3)])
    fc = fit_forecast(y, 12, trend=True, damped=True, m=12, seasonal="mul")
    assert np.argmax(fc) == 10          # November peak recovered
    assert np.argmin(fc) == 1           # February low recovered
    assert np.all(np.abs(fc / (season * 1.15) - 1) < 0.15)


def test_holt_damped_follows_trend():
    from salesiq.forecasting.ets import fit_forecast
    y = 100 + 5 * np.arange(20, dtype=float)
    fc = fit_forecast(y, 3, trend=True, damped=True)
    assert fc[0] > y[-1] and fc[2] > fc[0]
