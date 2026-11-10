"""Forecasting Lab endpoints. Runs as a background job; the client polls."""
from __future__ import annotations

from fastapi import APIRouter

from salesiq.analytics.filters import Filters

from ..errors import ApiError
from ..schemas import ForecastIn
from ..services import jobs
from ..services.workspace import store

router = APIRouter(prefix="/api/forecast", tags=["Forecasting Lab"])


@router.post("/{dataset_id}/run", summary="Start (or reuse) a 3-month forecast job")
def run(dataset_id: str, body: ForecastIn):
    ws = store.get(dataset_id)
    ws.require_ready()
    if body.target == "units" and not ws.prepared.available.get("quantity"):
        raise ApiError(422, "no_quantity", "This dataset has no quantity column, so units cannot be forecast.")
    job = jobs.submit_forecast(ws, body.target, Filters.from_dict(body.filters.model_dump()))
    return job.as_dict()


@router.get("/jobs/{job_id}", summary="Status and result of a forecast job")
def status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise ApiError(404, "job_not_found", "This forecast job no longer exists. Run the forecast again.")
    return job.as_dict()
