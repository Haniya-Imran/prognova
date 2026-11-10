"""Module F - Forecasting Lab orchestration: compare, select, refit, forecast."""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .backtesting import eligible, make_folds, run_backtest
from .evaluation import metrics
from .models import CANDIDATES, NOT_USED
from .series import TARGETS, build_series

HORIZON = 3
MIN_MONTHS = 6
Z80, Z95 = 1.2816, 1.96


class InsufficientHistory(ValueError):
    pass


def _r(x, nd=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def run_forecast(sales: pd.DataFrame, returns: pd.DataFrame, target: str = "net_revenue",
                 horizon: int = HORIZON) -> dict:
    t0 = time.time()
    ps = build_series(sales, returns, target)
    n = len(ps.monthly)
    history = [{"month": m.strftime("%Y-%m"), "value": _r(v)} for m, v in ps.monthly.items()]
    base = {
        "target": ps.target, "target_label": TARGETS[ps.target], "horizon_months": horizon,
        "granularity": ps.granularity, "history": history, "dropped_partial_months": ps.dropped_partial,
        "complete_months": n, "not_used": NOT_USED,
    }
    if n < MIN_MONTHS:
        raise InsufficientHistory(
            f"Only {n} complete month(s) of history. At least {MIN_MONTHS} complete months are needed to "
            f"test models on past data and forecast {horizon} months honestly.")

    folds = make_folds(n, horizon, ps.monthly.index)
    if len(folds) < 2:
        raise InsufficientHistory("Not enough history to run at least two backtest windows.")

    candidates, results = [], {}
    for spec in CANDIDATES:
        ok, why = eligible(spec, ps, folds)
        entry = {"key": spec.key, "name": spec.name, "family": spec.family, "description": spec.description,
                 "eligible": ok, "reason": why}
        if ok:
            try:
                bt = run_backtest(spec, ps, folds, horizon)
                rows = bt["rows"]
                m = metrics([r["actual"] for r in rows], [r["predicted"] for r in rows])
                by_h = {}
                for hh in range(1, horizon + 1):
                    sub = [r for r in rows if r["horizon"] == hh]
                    by_h[str(hh)] = _r(metrics([r["actual"] for r in sub], [r["predicted"] for r in sub])["wape"])
                entry["metrics"] = {k: (_r(v) if isinstance(v, (int, float)) and k != "n" else v) for k, v in m.items()}
                entry["wape_by_horizon"] = by_h
                results[spec.key] = {"spec": spec, "rows": rows, "metrics": m}
            except Exception as exc:  # a model that fails is reported, not hidden
                entry["eligible"] = False
                entry["reason"] = f"Failed during backtest: {type(exc).__name__}"
        candidates.append(entry)

    if not results:
        raise InsufficientHistory("No model could be evaluated on this history.")

    ranked = sorted(results.values(), key=lambda r: (r["metrics"]["wape"], r["metrics"]["rmse"]))
    best = ranked[0]
    spec = best["spec"]
    baselines = [r for r in results.values() if r["spec"].family == "Baseline"]
    best_base = min(baselines, key=lambda r: r["metrics"]["wape"]) if baselines else None
    for c in candidates:
        c["rank"] = next((i + 1 for i, r in enumerate(ranked) if r["spec"].key == c["key"]), None)
        c["selected"] = c["key"] == spec.key

    # Refit on all complete months and forecast the next calendar months.
    point = np.asarray(spec.fn(ps.monthly, ps.daily, horizon), dtype=float)
    point = np.maximum(point, 0)
    months = pd.date_range(ps.monthly.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")

    # Prediction intervals from the selected model's own out-of-sample errors at each horizon.
    rows = best["rows"]
    forecast_rows = []
    coverage_hits, coverage_total = 0, 0
    for i, (m, p) in enumerate(zip(months, point)):
        sub = [r for r in rows if r["horizon"] == i + 1 and r["predicted"] > 0]
        rel = np.array([(r["actual"] - r["predicted"]) / r["predicted"] for r in sub])
        sigma = float(np.sqrt(np.mean(rel ** 2))) if len(rel) else float("nan")
        lo80, hi80 = max(p * (1 - Z80 * sigma), 0), p * (1 + Z80 * sigma)
        lo95, hi95 = max(p * (1 - Z95 * sigma), 0), p * (1 + Z95 * sigma)
        for r in sub:
            coverage_total += 1
            coverage_hits += int(r["predicted"] * (1 - Z80 * sigma) <= r["actual"] <= r["predicted"] * (1 + Z80 * sigma))
        last_year = ps.monthly.get(m - pd.DateOffset(years=1))
        forecast_rows.append({
            "month": m.strftime("%Y-%m"), "label": m.strftime("%B %Y"), "forecast": _r(p),
            "lower_80": _r(lo80), "upper_80": _r(hi80), "lower_95": _r(lo95), "upper_95": _r(hi95),
            "relative_error_sd": _r(sigma * 100), "same_month_last_year": _r(last_year),
            "change_vs_last_year_pct": _r((p / last_year - 1) * 100) if last_year and last_year > 0 else None,
        })

    total = float(point.sum())
    last3 = float(ps.monthly.iloc[-horizon:].sum())
    prev_year_same = [ps.monthly.get(m - pd.DateOffset(years=1)) for m in months]
    prev_year_total = float(sum(prev_year_same)) if all(v is not None for v in prev_year_same) else None
    vs_last3 = (total / last3 - 1) * 100 if last3 > 0 else None
    vs_year = (total / prev_year_total - 1) * 100 if prev_year_total else None
    if vs_year is not None:
        direction = "up" if vs_year > 3 else "down" if vs_year < -3 else "flat"
    else:
        direction = "up" if (vs_last3 or 0) > 3 else "down" if (vs_last3 or 0) < -3 else "flat"

    improvement = None
    if best_base and best_base["spec"].key != spec.key and best_base["metrics"]["wape"]:
        improvement = (1 - best["metrics"]["wape"] / best_base["metrics"]["wape"]) * 100

    reason = (f"{spec.name} had the lowest weighted error (WAPE {best['metrics']['wape']:.1f}%) across "
              f"{len(folds)} rolling backtest windows of {horizon} months each.")
    if improvement is not None:
        reason += (f" That is {improvement:.0f}% less error than the best simple baseline "
                   f"({best_base['spec'].name}, WAPE {best_base['metrics']['wape']:.1f}%).")
    elif best_base and best_base["spec"].key == spec.key:
        reason += " No more complex model beat this simple baseline, so the simple one is kept."

    validation = [{"origin": r["origin"], "month": r["month"], "horizon": r["horizon"],
                   "actual": _r(r["actual"]), "predicted": _r(r["predicted"])} for r in rows]
    trained_through = ps.monthly.index[-1].strftime("%B %Y")
    limitations = [
        "A forecast is an estimate, not a guaranteed result. Real sales can fall outside the ranges.",
        f"Prediction ranges come from {len(folds)} past backtest windows, so they are rough, not exact probabilities.",
        "The model only knows past sales. It cannot see new promotions, price changes, stock-outs or market shocks.",
    ]
    if n < 24:
        limitations.append(f"Only {n} complete months exist, so yearly seasonality has been seen at most "
                           f"{n // 12} time(s).")
    cov = coverage_hits / coverage_total * 100 if coverage_total else None
    if cov is not None and cov < 72:
        limitations.append(f"In the backtest only {cov:.0f}% of real months fell inside the 80% range, so the "
                           "ranges are on the narrow side. Treat them as optimistic.")
    if ps.dropped_partial:
        limitations.append("Left out partial month(s): " + ", ".join(ps.dropped_partial) +
                           ". Forecasts start after the last complete month.")

    base.update({
        "status": "ok",
        "trained_through": trained_through,
        "frequency_note": (
            f"Models are tested on monthly totals. Daily models forecast each day and add the days up "
            f"into whole calendar months, so the {horizon} forecast values are exactly "
            f"{', '.join(r['label'] for r in forecast_rows)}."),
        "backtest": {"folds": len(folds), "first_origin": folds[0].train_end.strftime("%Y-%m"),
                     "last_origin": folds[-1].train_end.strftime("%Y-%m"), "horizon": horizon,
                     "method": "Rolling origin: train on all months up to the origin, forecast the next "
                               f"{horizon} months, move the origin one month forward, repeat."},
        "candidates": candidates,
        "selected": {"key": spec.key, "name": spec.name, "description": spec.description, "reason": reason,
                     "metrics": {k: (_r(v) if isinstance(v, float) else v) for k, v in best["metrics"].items()},
                     "improvement_over_baseline_pct": _r(improvement)},
        "forecast": forecast_rows,
        "summary": {"total": _r(total), "total_lower_80": _r(sum(r["lower_80"] for r in forecast_rows)),
                    "total_upper_80": _r(sum(r["upper_80"] for r in forecast_rows)),
                    "last_3_months_actual": _r(last3), "change_vs_last_3_months_pct": _r(vs_last3),
                    "same_period_last_year": _r(prev_year_total), "change_vs_last_year_pct": _r(vs_year),
                    "direction": direction},
        "interval_method": ("80% and 95% ranges = forecast x (1 +/- z x spread of the selected model's "
                            "relative errors at that horizon in the backtest)."),
        "interval_backtest_coverage_80_pct": _r(coverage_hits / coverage_total * 100) if coverage_total else None,
        "validation": validation,
        "limitations": limitations,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runtime_seconds": round(time.time() - t0, 2),
    })
    return base
