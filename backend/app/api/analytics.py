"""EDA Studio, Sales Analytics and Dashboard endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from salesiq.analytics.dashboard import dimension_values
from salesiq.analytics.filters import Filters

from ..errors import ApiError
from ..schemas import DashboardIn
from ..services.workspace import store

router = APIRouter(prefix="/api/analytics", tags=["EDA & Dashboard"])


@router.get("/{dataset_id}/eda", summary="Full exploratory analysis (computed once, then cached)")
def eda(dataset_id: str):
    return store.get(dataset_id).get_eda()


@router.post("/{dataset_id}/dashboard", summary="KPIs + chart data for the chosen filters")
def dashboard(dataset_id: str, body: DashboardIn):
    ws = store.get(dataset_id)
    return ws.get_dashboard(Filters.from_dict(body.filters.model_dump()), body.grain)


@router.get("/{dataset_id}/dimensions/{dim}", summary="Filter options for a dimension, biggest first")
def dimensions(dataset_id: str, dim: str, q: str = Query("", max_length=60), limit: int = Query(50, ge=1, le=500)):
    if dim not in ("product", "category", "region", "store"):
        raise ApiError(400, "bad_dimension", "Dimension must be product, category, region or store.")
    p = store.get(dataset_id).require_ready()
    return {"dimension": dim, "available": dim in p.sales, "values": dimension_values(p.sales, dim, q, limit)}
