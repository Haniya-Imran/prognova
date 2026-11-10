"""Business Insights & Reports endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, Response

from salesiq.analytics.filters import Filters
from salesiq.insights.generate import generate
from salesiq.reports import build

from ..errors import ApiError
from ..services import jobs
from ..services.workspace import store

router = APIRouter(prefix="/api", tags=["Insights & Reports"])
BRAND = "Prognova"


def _currency(ws) -> str:
    return {"GBP": "£", "USD": "$", "EUR": "€"}.get(ws.meta.get("currency", ""), "")


@router.get("/insights/{dataset_id}", summary="Data-driven observations and recommendations")
def insights(dataset_id: str, target: str = Query("net_revenue", pattern="^(net_revenue|gross_revenue|units)$")):
    ws = store.get(dataset_id)
    eda = ws.get_eda()
    fc = jobs.run_sync(ws, target, Filters())
    return {"dataset_id": dataset_id, "insights": generate(eda, fc if fc.get("status") == "ok" else None, _currency(ws)),
            "forecast_status": fc.get("status"), "forecast_error": fc.get("error")}


def _filters(raw: str | None) -> Filters:
    if not raw:
        return Filters()
    try:
        return Filters.from_dict(json.loads(raw))
    except (ValueError, TypeError) as exc:
        raise ApiError(400, "bad_filters", "filters must be JSON.") from exc


def _download(content: str, filename: str, media: str) -> Response:
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/reports/{dataset_id}/{kind}.html", summary="Download an HTML report: eda, dashboard or forecast")
def html_report(dataset_id: str, kind: str, filters: str | None = None,
                target: str = Query("net_revenue", pattern="^(net_revenue|gross_revenue|units)$")):
    if kind not in ("eda", "dashboard", "forecast"):
        raise ApiError(404, "unknown_report", "Report must be eda, dashboard or forecast.")
    ws = store.get(dataset_id)
    eda = ws.get_eda()
    f = _filters(filters)
    fc = jobs.run_sync(ws, target, f if kind != "eda" else Filters())
    fc = fc if fc.get("status") == "ok" else None
    dash = ws.get_dashboard(f, None) if kind == "dashboard" else None
    ins = generate(eda, fc, _currency(ws)) if kind != "dashboard" else None
    page = build.html_report(kind, ws.meta, eda, dash, fc, ins, BRAND)
    return HTMLResponse(page, headers={"Content-Disposition": f'attachment; filename="{kind}-report.html"'})


@router.get("/reports/{dataset_id}/{kind}.csv", summary="Download CSV: forecast, backtest, models, monthly, dashboard")
def csv_report(dataset_id: str, kind: str, filters: str | None = None,
               target: str = Query("net_revenue", pattern="^(net_revenue|gross_revenue|units)$")):
    ws = store.get(dataset_id)
    f = _filters(filters)
    if kind in ("forecast", "backtest", "models"):
        fc = jobs.run_sync(ws, target, f)
        if fc.get("status") != "ok":
            raise ApiError(422, "no_forecast", (fc.get("error") or {}).get("message", "No forecast available."))
        content = {"forecast": build.forecast_csv, "backtest": build.backtest_csv, "models": build.models_csv}[kind](fc)
    elif kind == "monthly":
        content = build.monthly_csv(ws.get_eda())
    elif kind == "dashboard":
        content = build.dashboard_csv(ws.get_dashboard(f, None))
    else:
        raise ApiError(404, "unknown_report", "CSV must be forecast, backtest, models, monthly or dashboard.")
    return _download(content, f"{kind}.csv", "text/csv")
