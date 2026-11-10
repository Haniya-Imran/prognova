"""Module G - downloadable reports (CSV and self-contained HTML)."""
from __future__ import annotations

import html
import io
import json
from datetime import datetime, timezone

import pandas as pd


def forecast_csv(fc: dict) -> str:
    rows = [{"month": r["month"], "forecast": r["forecast"], "lower_80": r["lower_80"], "upper_80": r["upper_80"],
             "lower_95": r["lower_95"], "upper_95": r["upper_95"],
             "same_month_last_year": r["same_month_last_year"]} for r in fc["forecast"]]
    buf = io.StringIO()
    buf.write(f"# target,{fc['target_label']}\n# model,{fc['selected']['name']}\n"
              f"# trained_through,{fc['trained_through']}\n# backtest_wape_pct,{fc['selected']['metrics']['wape']}\n"
              f"# note,Forecasts are estimates not guarantees. Ranges come from backtest errors.\n")
    pd.DataFrame(rows).to_csv(buf, index=False)
    return buf.getvalue()


def backtest_csv(fc: dict) -> str:
    return pd.DataFrame(fc["validation"]).to_csv(index=False)


def models_csv(fc: dict) -> str:
    rows = []
    for c in fc["candidates"]:
        m = c.get("metrics") or {}
        rows.append({"rank": c.get("rank"), "model": c["name"], "family": c["family"], "eligible": c["eligible"],
                     "reason": c["reason"], "wape_pct": m.get("wape"), "mae": m.get("mae"), "rmse": m.get("rmse"),
                     "smape_pct": m.get("smape"), "mape_pct": m.get("mape"), "selected": c.get("selected")})
    df = pd.DataFrame(rows)
    df["rank"] = df["rank"].astype("Int64")
    return df.to_csv(index=False)


def dashboard_csv(dash: dict) -> str:
    t = dash["trend"]
    return pd.DataFrame({k: v for k, v in t.items()}).to_csv(index=False)


def monthly_csv(eda: dict) -> str:
    return pd.DataFrame(eda["time"]["monthly"]).to_csv(index=False)


_CSS = """
body{font-family:Georgia,'Times New Roman',serif;color:#2a1a24;max-width:980px;margin:32px auto;padding:0 20px;line-height:1.5}
h1{font-size:30px;margin:0 0 4px}h2{font-size:21px;margin:34px 0 8px;border-bottom:2px solid #e8d6df;padding-bottom:6px}
.meta{color:#6b5462;font-size:14px}table{border-collapse:collapse;width:100%;font:14px/1.4 system-ui,sans-serif;margin:8px 0}
th,td{padding:7px 9px;border-bottom:1px solid #eee;text-align:left}th{background:#f7eef2}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.kpi{border:1px solid #e8d6df;border-radius:10px;padding:10px 12px;font-family:system-ui,sans-serif}.kpi b{display:block;font-size:20px}
.kpi span{font-size:12px;color:#6b5462}.ins{border-left:4px solid #8a3d64;padding:6px 12px;margin:10px 0;font-family:system-ui,sans-serif;font-size:14px}
.ins b{font-size:15px}.note{font:13px system-ui,sans-serif;color:#6b5462}.chart{height:360px}
"""


def _num(v, nd=0):
    if v is None:
        return "—"
    return f"{v:,.{nd}f}"


def _table(rows: list[dict], cols: list[tuple[str, str, bool]]) -> str:
    head = "".join(f"<th class='{'n' if n else ''}'>{html.escape(t)}</th>" for _, t, n in cols)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(
            f"<td class='{'n' if n else ''}'>{_num(r.get(k), 1 if 'pct' in k else 0) if n else html.escape(str(r.get(k, '')))}</td>"
            for k, _, n in cols) + "</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _plot(div_id: str, traces: list, layout: dict) -> str:
    return (f"<div id='{div_id}' class='chart'></div><script>if(window.Plotly)Plotly.newPlot('{div_id}',"
            f"{json.dumps(traces)},{json.dumps(layout)},{{responsive:true,displaylogo:false}});</script>")


def html_report(kind: str, meta: dict, eda: dict | None, dash: dict | None, fc: dict | None,
                insights: list[dict] | None, brand: str = "Prognova") -> str:
    now = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    cur = meta.get("currency") or ""
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{html.escape(brand)} - {html.escape(kind.title())} report</title><style>{_CSS}</style>"
             "<script src='https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js'></script></head><body>",
             f"<h1>{html.escape(kind.title())} report</h1><div class='meta'>{html.escape(brand)} · Dataset: "
             f"{html.escape(meta.get('name', ''))} · Generated {now}</div>"
             "<p class='note'>Charts need an internet connection (Plotly from a CDN). All tables work offline. "
             "Revenue means sales value, not profit.</p>"]
    if dash and kind == "dashboard":
        k = dash["kpis"]
        c = k["current"]
        f = dash["filters"]
        active = [f"{d}: {', '.join(f[d][:5])}{'…' if len(f[d]) > 5 else ''}" for d in ("region", "product", "category", "store") if f.get(d)]
        parts.append(f"<p class='note'>Period {k['period']['start']} to {k['period']['end']}. Filters: "
                     f"{html.escape('; '.join(active) or 'none')}</p><div class='kpis'>")
        for label, key in (("Gross revenue", "gross_revenue"), ("Net revenue", "net_revenue"), ("Orders", "orders"),
                           ("Units", "units"), ("Avg order value", "avg_order_value"), ("Customers", "customers")):
            if c.get(key) is not None:
                g = k["growth"].get(key, {}).get("vs_previous_period_pct")
                gtxt = f"{g:+.1f}% vs previous period" if g is not None else "no earlier period to compare"
                parts.append(f"<div class='kpi'><span>{label}</span><b>{_num(c[key])}</b><span>{gtxt}</span></div>")
        parts.append("</div><h2>Trend</h2>")
        t = dash["trend"]
        parts.append(_plot("trend", [{"x": t["period"], "y": t["revenue"], "type": "scatter", "mode": "lines",
                                      "line": {"color": "#8a3d64"}, "name": "Revenue"}],
                           {"margin": {"t": 10}, "yaxis": {"title": f"Revenue {cur}"}}))
        if dash.get("top_products"):
            parts.append("<h2>Top products</h2>" + _table(dash["top_products"], [("name", "Product", False), ("revenue", "Revenue", True), ("units", "Units", True), ("share_pct", "Share %", True)]))
        if dash.get("regions"):
            parts.append("<h2>Regions</h2>" + _table(dash["regions"], [("name", "Region", False), ("revenue", "Revenue", True), ("orders", "Orders", True), ("share_pct", "Share %", True)]))
    if eda and kind == "eda":
        o = eda["overview"]
        parts.append("<h2>Dataset overview</h2>" + _table([
            {"k": "Raw rows", "v": o["raw_rows"]}, {"k": "Columns", "v": o["raw_columns"]},
            {"k": "Clean sales lines", "v": o["clean_rows"]}, {"k": "Return lines", "v": o["return_rows"]},
            {"k": "Duplicate rows removed", "v": o["duplicate_rows"]}, {"k": "Missing cells (raw)", "v": o["missing_cells"]},
        ], [("k", "Measure", False), ("v", "Value", True)]) + f"<p class='note'>Dates {o['date_min']} to {o['date_max']}.</p>")
        m = eda["time"]["monthly"]
        parts.append("<h2>Monthly revenue</h2>" + _plot("monthly", [{"x": [r["month"] for r in m], "y": [r["revenue"] for r in m],
                     "type": "bar", "marker": {"color": "#8a3d64"}}], {"margin": {"t": 10}}))
        parts.append(_table(m, [("month", "Month", False), ("revenue", "Revenue", True), ("mom_pct", "MoM %", True), ("yoy_pct", "YoY %", True)]))
        si = eda["time"]["seasonality_index"]
        parts.append("<h2>Seasonality index</h2><p class='note'>" + html.escape(si["note"]) + "</p>" +
                     _table([{"m": a, "i": b} for a, b in zip(si["month"], si["index"])], [("m", "Month", False), ("i", "Index", True)]))
        for dim in ("product", "region", "category", "store"):
            d = eda["dimensions"].get(dim)
            if d:
                parts.append(f"<h2>Top {dim}s</h2>" + _table(d["top"], [("name", dim.title(), False), ("revenue", "Revenue", True), ("share_pct", "Share %", True), ("growth_pct", "Growth %", True)]) +
                             f"<p class='note'>Growth: {html.escape(d['growth_basis'])}.</p>")
    if fc and kind in ("forecast", "eda", "dashboard") and fc.get("status") == "ok":
        parts.append(f"<h2>Next {fc['horizon_months']} months forecast</h2><p class='note'>{html.escape(fc['target_label'])}. "
                     f"Model: {html.escape(fc['selected']['name'])}. {html.escape(fc['selected']['reason'])}</p>")
        hist = fc["history"]
        traces = [{"x": [h["month"] for h in hist], "y": [h["value"] for h in hist], "type": "scatter", "name": "Actual", "line": {"color": "#3d1a2e"}},
                  {"x": [r["month"] for r in fc["forecast"]], "y": [r["forecast"] for r in fc["forecast"]], "type": "scatter", "name": "Forecast",
                   "line": {"color": "#c0567f", "dash": "dash"},
                   "error_y": {"type": "data", "symmetric": False,
                               "array": [r["upper_80"] - r["forecast"] for r in fc["forecast"]],
                               "arrayminus": [r["forecast"] - r["lower_80"] for r in fc["forecast"]]}}]
        parts.append(_plot("fc", traces, {"margin": {"t": 10}}))
        parts.append(_table(fc["forecast"], [("label", "Month", False), ("forecast", "Forecast", True), ("lower_80", "Low (80%)", True), ("upper_80", "High (80%)", True), ("same_month_last_year", "Same month last year", True)]))
        parts.append("<h2>Model comparison (backtest)</h2>" + _table(
            [{"name": c["name"], "wape": (c.get("metrics") or {}).get("wape"), "mae": (c.get("metrics") or {}).get("mae"),
              "status": "Selected" if c.get("selected") else ("Compared" if c["eligible"] else c["reason"])} for c in fc["candidates"]],
            [("name", "Model", False), ("wape", "WAPE %", True), ("mae", "MAE", True), ("status", "Status", False)]))
        parts.append("<h2>Limitations</h2><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in fc["limitations"]) + "</ul>")
    if insights:
        parts.append("<h2>Business insights</h2>")
        for i in insights:
            rec = f"<br><i>Suggested action:</i> {html.escape(i['recommendation'])}" if i.get("recommendation") else ""
            ass = f"<br><span class='note'>Assumption: {html.escape(i['assumption'])}</span>" if i.get("assumption") else ""
            parts.append(f"<div class='ins'><b>{html.escape(i['title'])}</b><br>{html.escape(i['detail'])}{rec}{ass}</div>")
    src = meta.get("source_url")
    if src:
        parts.append(f"<h2>Source</h2><p class='note'>{html.escape(meta.get('citation', ''))} License: {html.escape(meta.get('license', ''))}. "
                     f"<a href='{html.escape(src)}'>{html.escape(src)}</a></p>")
    parts.append("</body></html>")
    return "".join(parts)
