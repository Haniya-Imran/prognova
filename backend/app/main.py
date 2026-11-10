"""FastAPI entry point for the Prognova Sales Intelligence Workspace API."""
from __future__ import annotations

import logging
import threading
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import salesiq

from . import errors
from .api import analytics, datasets, forecast, insights
from .config import settings
from .responses import SafeJSONResponse
from .services.workspace import store

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("salesiq.api")

_sample_ready = threading.Event()


def _warm() -> None:
    try:
        from salesiq.analytics.filters import Filters
        from .services import jobs
        ws = store.sample()
        ws.get_eda()
        jobs.submit_forecast(ws, "net_revenue", Filters())  # warms the cache
    except Exception:  # pragma: no cover
        log.exception("Sample warm-up failed")
    finally:
        _sample_ready.set()


@asynccontextmanager
async def lifespan(_app):
    if settings.preload_sample:
        threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
    title=settings.app_name,
    version=salesiq.__version__,
    description=("Data Hub -> Data Quality -> EDA Studio -> Sales Analytics -> Dashboard -> Forecasting Lab -> "
                 "Insights & Reports. No login: every endpoint is public and session data lives in memory."),
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)
errors.install(app)


@app.middleware("http")
async def timing(request: Request, call_next):
    t = time.time()
    response = await call_next(request)
    ms = (time.time() - t) * 1000
    if request.url.path != "/health":
        log.info("%s %s -> %s in %.0fms", request.method, request.url.path, response.status_code, ms)
    return response


for r in (datasets.router, analytics.router, forecast.router, insights.router):
    app.include_router(r)


@app.get("/health", tags=["System"], summary="Liveness check")
@app.get("/api/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": salesiq.__version__, "sample_loaded": _sample_ready.is_set()}


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.app_name, "docs": "/api/docs", "health": "/api/health"}
