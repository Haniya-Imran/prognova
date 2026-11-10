"""Module G - Business insights.

Each insight carries the numbers it is based on and the assumption behind any
recommendation. Insights are only produced when the data supports them.
"""
from __future__ import annotations

import pandas as pd


def _fmt(v: float, cur: str = "") -> str:
    a = abs(v)
    s = f"{a / 1e6:.2f}M" if a >= 1e6 else f"{a / 1e3:.1f}K" if a >= 1e4 else f"{a:,.0f}"
    return f"{'-' if v < 0 else ''}{cur}{s}"


def _pct(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.1f}%"


def generate(eda: dict, forecast: dict | None, currency: str = "") -> list[dict]:
    out: list[dict] = []
    t = eda["time"]
    months = [m for m in t["monthly"] if m["complete"]]

    # 1. Recent trend vs a year earlier.
    if len(months) >= 15:
        recent = months[-3:]
        prior = months[-15:-12]
        now, before = sum(m["revenue"] for m in recent), sum(m["revenue"] for m in prior)
        if before:
            g = (now / before - 1) * 100
            direction = "grew" if g > 2 else "fell" if g < -2 else "held steady"
            out.append({
                "id": "recent_trend", "type": "trend", "severity": "positive" if g > 2 else "warning" if g < -2 else "neutral",
                "title": f"Sales {direction} {_pct(g)} year on year in the latest 3 months",
                "detail": (f"{recent[0]['month']} to {recent[-1]['month']}: {_fmt(now, currency)} vs "
                           f"{_fmt(before, currency)} in the same months a year earlier."),
                "evidence": {"recent": now, "year_before": before, "change_pct": g},
                "recommendation": None, "assumption": None,
            })
    # 2. Year to date comparison.
    by_year: dict[int, dict[int, float]] = {}
    for m in months:
        y, mm = int(m["month"][:4]), int(m["month"][5:])
        by_year.setdefault(y, {})[mm] = m["revenue"]
    years = sorted(by_year)
    if len(years) >= 2:
        last, prev = years[-1], years[-2]
        common = sorted(set(by_year[last]) & set(by_year[prev]))
        if len(common) >= 3:
            a, b = sum(by_year[last][x] for x in common), sum(by_year[prev][x] for x in common)
            g = (a / b - 1) * 100
            out.append({
                "id": "ytd", "type": "trend", "severity": "positive" if g > 0 else "warning",
                "title": f"{last} is {_pct(g)} vs {prev} for the same {len(common)} months",
                "detail": f"Months compared: {pd.Timestamp(2000, common[0], 1):%b} to {pd.Timestamp(2000, common[-1], 1):%b}. "
                          f"{_fmt(a, currency)} vs {_fmt(b, currency)}.",
                "evidence": {"current": a, "previous": b, "change_pct": g},
                "recommendation": None, "assumption": None,
            })
    # 3. Seasonality.
    idx = t["seasonality_index"]["index"]
    names = t["seasonality_index"]["month"]
    valid = [(n, v) for n, v in zip(names, idx) if v is not None]
    if len(valid) == 12 and len(months) >= 13:
        hi = sorted(valid, key=lambda kv: -kv[1])[:3]
        lo = sorted(valid, key=lambda kv: kv[1])[:3]
        out.append({
            "id": "seasonality", "type": "seasonality", "severity": "info",
            "title": f"Strong year-end season: {', '.join(n for n, _ in hi)} are the busiest months",
            "detail": (f"Seasonal index (100 = average month): " + ", ".join(f"{n} {v:.0f}" for n, v in hi) +
                       ". Quietest: " + ", ".join(f"{n} {v:.0f}" for n, v in lo) + "."),
            "evidence": {"high": hi, "low": lo},
            "recommendation": (f"Build stock and staff capacity before the busy months ("
                               f"{', '.join(sorted((n for n, _ in hi), key=names.index))}); "
                               f"plan promotions for the quieter months ({', '.join(n for n, _ in lo)})."),
            "assumption": "Assumes next year follows the same seasonal shape as the years in the data.",
        })
    # 4. Weekday pattern.
    wd = t["weekday"]
    vals = [(d, v, n) for d, v, n in zip(wd["day"], wd["avg_revenue_per_selling_day"], wd["selling_days"]) if v and n >= 10]
    closed = [d for d, n in zip(wd["day"], wd["selling_days"]) if n < 5]
    if len(vals) >= 3:
        best = max(vals, key=lambda x: x[1])
        worst = min(vals, key=lambda x: x[1])
        detail = (f"{best[0]} averages {_fmt(best[1], currency)} per selling day vs {_fmt(worst[1], currency)} on {worst[0]}.")
        if closed:
            detail += f" Almost no sales are recorded on {', '.join(closed)}."
        out.append({"id": "weekday", "type": "pattern", "severity": "info",
                    "title": f"{best[0]} is the strongest trading day, {worst[0]} the weakest", "detail": detail,
                    "evidence": {"best": best, "worst": worst, "closed_days": closed},
                    "recommendation": f"Schedule campaigns and email sends to land before {best[0]}.",
                    "assumption": "Day-of-week averages use only days with at least one sale."})
    if t.get("hour"):
        h = t["hour"]
        i = max(range(len(h["revenue"])), key=lambda k: h["revenue"][k] or 0)
        out.append({"id": "hour", "type": "pattern", "severity": "info",
                    "title": f"Orders peak around {h['hours'][i]}",
                    "detail": "Revenue by order hour shows trading concentrated in working hours.",
                    "evidence": {"peak_hour": h["hours"][i]}, "recommendation": None, "assumption": None})
    # 5. Concentration.
    reg = eda["dimensions"].get("region")
    if reg and reg["top"]:
        top = reg["top"][0]
        if top["share_pct"] >= 50:
            out.append({"id": "region_concentration", "type": "risk", "severity": "warning",
                        "title": f"{top['name']} brings {top['share_pct']:.0f}% of revenue",
                        "detail": f"{reg['count']} regions sell, but sales depend heavily on one market.",
                        "evidence": {"region": top["name"], "share_pct": top["share_pct"]},
                        "recommendation": "Test growth in the next-largest markets to reduce dependence on one region.",
                        "assumption": None})
        movers = [r for r in reg["top"][1:10] if r.get("growth_pct") is not None]
        if movers:
            up = max(movers, key=lambda r: r["growth_pct"])
            dn = min(movers, key=lambda r: r["growth_pct"])
            out.append({"id": "region_movers", "type": "region", "severity": "info",
                        "title": f"Among top markets, {up['name']} grew most ({_pct(up['growth_pct'])}); "
                                 f"{dn['name']} fell most ({_pct(dn['growth_pct'])})",
                        "detail": f"Growth basis: {reg['growth_basis']}.",
                        "evidence": {"up": up, "down": dn},
                        "recommendation": f"Review what changed with customers in {dn['name']}.",
                        "assumption": "Small markets can swing a lot from a few large orders."})
    prod = eda["dimensions"].get("product")
    if prod and prod["top"]:
        movers = [r for r in prod["top"] if r.get("growth_pct") is not None]
        if movers:
            dn = min(movers, key=lambda r: r["growth_pct"])
            up = max(movers, key=lambda r: r["growth_pct"])
            out.append({"id": "product_movers", "type": "product", "severity": "warning" if dn["growth_pct"] < -20 else "info",
                        "title": f"Top seller '{dn['name']}' is down {abs(dn['growth_pct']):.0f}% year on year",
                        "detail": (f"Growth basis: {prod['growth_basis']}. Fastest grower among the top "
                                   f"{len(prod['top'])}: '{up['name']}' ({_pct(up['growth_pct'])})."),
                        "evidence": {"down": dn, "up": up},
                        "recommendation": f"Check price, stock availability and listing of '{dn['name']}'.",
                        "assumption": "A drop can come from stock-outs or a replacement product, not only weaker demand."})
    # 6. Returns.
    ret = eda.get("returns")
    tot = eda["overview"]["totals"]
    if ret and tot.get("return_rate_pct") is not None:
        out.append({"id": "returns", "type": "returns", "severity": "warning" if tot["return_rate_pct"] > 5 else "info",
                    "title": f"Returns and cancellations equal {tot['return_rate_pct']:.1f}% of gross sales",
                    "detail": f"{ret['lines']:,} return lines worth {_fmt(ret['total_returns'], currency)}."
                              + (f" Largest: '{ret['top_returned_products'][0]['name']}'." if ret.get("top_returned_products") else ""),
                    "evidence": {"rate_pct": tot["return_rate_pct"]},
                    "recommendation": "Look at the most-returned products for quality or description problems.",
                    "assumption": "Some very large cancellations are order-entry corrections, not customer returns."})
    # 7. Forecast.
    if forecast and forecast.get("status") == "ok":
        s = forecast["summary"]
        f = forecast["forecast"]
        title = (f"Next 3 months forecast: {_fmt(s['total'], currency)} "
                 f"(range {_fmt(s['total_lower_80'], currency)}-{_fmt(s['total_upper_80'], currency)})")
        bits = []
        if s.get("change_vs_last_year_pct") is not None:
            bits.append(f"{_pct(s['change_vs_last_year_pct'])} vs the same months last year")
        if s.get("change_vs_last_3_months_pct") is not None:
            bits.append(f"{_pct(s['change_vs_last_3_months_pct'])} vs the last 3 months")
        peak = max(f, key=lambda r: r["forecast"])
        low = min(f, key=lambda r: r["forecast"])
        note = ""
        if forecast["selected"]["key"] == "seasonal_naive":
            g = next((c for c in forecast["candidates"] if c["key"] == "seasonal_naive_growth" and c.get("metrics")), None)
            note = " The chosen model repeats last year's months."
            if g:
                note += (f" A version that adds recent growth was tested but was less accurate "
                         f"(WAPE {g['metrics']['wape']:.1f}%), so growth is not added.")
        out.append({"id": "forecast", "type": "forecast", "severity": "info", "title": title,
                    "detail": (f"{'; '.join(bits)}. Highest month expected: {peak['label']}; lowest: {low['label']}. "
                               f"Model: {forecast['selected']['name']} (backtest WAPE "
                               f"{forecast['selected']['metrics']['wape']:.1f}%)." + note),
                    "evidence": {"summary": s},
                    "recommendation": (f"Plan stock and cash for a drop from {peak['label']} into {low['label']}; "
                                       "use the lower end of the range for commitments you cannot reverse."),
                    "assumption": "The forecast assumes the coming months behave like past ones. It is an estimate, not a guarantee."})
    return out
