"""Forecast jobs.

On serverless hosting (Vercel) one request may land on a different instance than
the next, so a job is computed inside the request that starts it and returned
already finished. The job record and result cache still prevent re-training the
same model for the same dataset and settings on a warm instance.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

from salesiq.analytics.filters import Filters, apply_dims
from salesiq.forecasting.engine import InsufficientHistory, run_forecast

from .workspace import Workspace

log = logging.getLogger("salesiq.jobs")


@dataclass
class Job:
    id: str
    dataset_id: str
    key: tuple
    status: str = "queued"          # queued | running | done | failed
    stage: str = "Queued"
    result: dict | None = None
    error: dict | None = None
    started: float = field(default_factory=time.time)
    finished: float | None = None

    def as_dict(self) -> dict:
        return {"job_id": self.id, "dataset_id": self.dataset_id, "status": self.status, "stage": self.stage,
                "result": self.result, "error": self.error,
                "elapsed_seconds": round((self.finished or time.time()) - self.started, 1)}


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def forecast_key(target: str, f: Filters) -> tuple:
    return (target,) + f.without_dates().key()


def submit_forecast(ws: Workspace, target: str, f: Filters) -> Job:
    key = forecast_key(target, f)
    with _lock:
        cached = ws.forecasts.get(key)
        if cached is not None:  # already computed for this dataset and these settings
            job = Job(uuid.uuid4().hex[:12], ws.id, key, "done", "Loaded from cache", result=cached, finished=time.time())
            _jobs[job.id] = job
            return job
        for j in _jobs.values():
            if j.dataset_id == ws.id and j.key == key and j.status in ("queued", "running"):
                return j
        job = Job(uuid.uuid4().hex[:12], ws.id, key)
        _jobs[job.id] = job

    def work():
        job.status, job.stage = "running", "Building monthly and daily series"
        try:
            p = ws.require_ready()
            sales = apply_dims(p.sales, f)
            returns = apply_dims(p.returns, f) if len(p.returns) else p.returns
            if sales.empty:
                raise InsufficientHistory("No sales match these filters.")
            job.stage = "Backtesting candidate models"
            result = run_forecast(sales, returns, target)
            result["filters"] = {k: v for k, v in f.without_dates().as_dict().items() if v}
            ws.forecasts[key] = result
            job.result, job.status, job.stage = result, "done", "Finished"
        except InsufficientHistory as exc:
            job.status, job.stage = "failed", "Not enough history"
            job.error = {"code": "insufficient_history", "message": str(exc)}
        except ValueError as exc:
            job.status, job.stage = "failed", "Invalid request"
            job.error = {"code": "invalid_request", "message": str(exc)}
        except Exception:  # pragma: no cover - logged for operators
            log.exception("Forecast job %s failed", job.id)
            job.status, job.stage = "failed", "Error"
            job.error = {"code": "internal_error", "message": "The forecast could not be completed."}
        finally:
            job.finished = time.time()
            _prune()

    work()
    return job


def get(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def _prune() -> None:
    cutoff = time.time() - 3600
    with _lock:
        for k in [k for k, j in _jobs.items() if j.finished and j.finished < cutoff]:
            _jobs.pop(k, None)


def run_sync(ws: Workspace, target: str, f: Filters) -> dict:
    """Used by reports/insights: reuse the cache, else compute now."""
    job = submit_forecast(ws, target, f)
    if job.status != "done":
        return {"status": "failed", "error": job.error or {"message": "Timed out"}}
    return job.result
