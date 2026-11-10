"""Small, dependency-free exponential smoothing (Holt / Holt-Winters).

Written with NumPy only so the API fits inside a serverless function (no SciPy,
no statsmodels). Smoothing parameters are fitted by minimising the in-sample
one-step squared error with a bounded Nelder-Mead search.
"""
from __future__ import annotations

import numpy as np


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def nelder_mead(f, x0, iters: int = 300, step: float = 0.8, tol: float = 1e-8):
    """Minimise ``f`` from ``x0`` (unconstrained). Returns the best point found."""
    n = len(x0)
    pts = [np.asarray(x0, float)]
    for i in range(n):
        p = np.array(x0, float)
        p[i] += step
        pts.append(p)
    vals = [f(p) for p in pts]
    for _ in range(iters):
        order = np.argsort(vals)
        pts = [pts[i] for i in order]
        vals = [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) <= tol * (abs(vals[0]) + tol):
            break
        centroid = np.mean(pts[:-1], axis=0)
        xr = centroid + (centroid - pts[-1])
        fr = f(xr)
        if fr < vals[0]:
            xe = centroid + 2 * (centroid - pts[-1])
            fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = centroid + 0.5 * (pts[-1] - centroid)
            fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                for i in range(1, len(pts)):
                    pts[i] = pts[0] + 0.5 * (pts[i] - pts[0])
                    vals[i] = f(pts[i])
    return pts[int(np.argmin(vals))]


def _run(y, alpha, beta, phi, gamma, m, seasonal, trend):
    """One pass of the smoothing recursions. Returns (sse, level, slope, season)."""
    n = len(y)
    if m:
        k = min(len(y) // m, 2) or 1
        first = y[: m * k].reshape(k, m) if len(y) >= m * k else y[:m].reshape(1, -1)
        lvl = float(first[0].mean())
        if seasonal == "mul":
            season = list(first.mean(axis=0) / max(lvl, 1e-9))
        else:
            season = list(first.mean(axis=0) - lvl)
        slope = float((first[-1].mean() - first[0].mean()) / (m * max(k - 1, 1))) if trend else 0.0
    else:
        lvl = float(y[0])
        slope = float(y[1] - y[0]) if (trend and n > 1) else 0.0
        season = []
    sse = 0.0
    for t in range(n):
        s = season[t % m] if m else (1.0 if seasonal == "mul" else 0.0)
        base = lvl + phi * slope
        pred = base * s if seasonal == "mul" else base + s
        err = y[t] - pred
        sse += err * err
        if seasonal == "mul":
            new_lvl = alpha * (y[t] / max(s, 1e-9)) + (1 - alpha) * base
        else:
            new_lvl = alpha * (y[t] - s) + (1 - alpha) * base
        if trend:
            slope = beta * (new_lvl - lvl) + (1 - beta) * phi * slope
        if m:
            if seasonal == "mul":
                season[t % m] = gamma * (y[t] / max(new_lvl, 1e-9)) + (1 - gamma) * s
            else:
                season[t % m] = gamma * (y[t] - new_lvl) + (1 - gamma) * s
        lvl = new_lvl
    return sse, lvl, slope, season


def fit_forecast(y, h: int, trend: bool = True, damped: bool = True, m: int = 0, seasonal: str | None = None) -> np.ndarray:
    """Fit ETS(A, Ad, A/M) style smoothing and forecast ``h`` steps ahead."""
    y = np.asarray(y, dtype=float)
    seasonal = seasonal if m else None
    if seasonal == "mul" and (y <= 0).any():
        seasonal = "add"

    def unpack(x):
        a = 0.01 + 0.98 * _sigmoid(x[0])
        b = (0.01 + 0.98 * _sigmoid(x[1])) * a if trend else 0.0
        p = (0.8 + 0.18 * _sigmoid(x[2])) if (trend and damped) else 1.0
        g = (0.01 + 0.98 * _sigmoid(x[3])) * (1 - a) if m else 0.0
        return a, b, p, g

    def loss(x):
        a, b, p, g = unpack(x)
        return _run(y, a, b, p, g, m, seasonal, trend)[0]

    best = nelder_mead(loss, [0.0, -1.0, 1.0, -1.0], iters=250 if len(y) < 200 else 120)
    a, b, p, g = unpack(best)
    _, lvl, slope, season = _run(y, a, b, p, g, m, seasonal, trend)
    out = np.empty(h)
    n = len(y)
    damp = 0.0
    for i in range(1, h + 1):
        damp += p ** i if trend else 0.0
        base = lvl + damp * slope
        if m:
            s = season[(n + i - 1) % m]
            out[i - 1] = base * s if seasonal == "mul" else base + s
        else:
            out[i - 1] = base
    return out
