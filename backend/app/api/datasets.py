"""Data Hub + Data Quality endpoints."""
from __future__ import annotations

import hashlib
import logging
import re

import pandas as pd
from fastapi import APIRouter, File, Query, UploadFile

from salesiq.datahub.detect import detect_columns, detect_frequency, to_datetime
from salesiq.datahub.ingest import IngestError, read_csv_bytes
from salesiq.datahub.sample import SAMPLE_ID
from salesiq.quality.prepare import quality_report
from salesiq.schema import CleaningOptions, ColumnMapping

from ..config import settings
from ..errors import ApiError
from ..schemas import PrepareIn
from ..services.workspace import store

router = APIRouter(prefix="/api/datasets", tags=["Data Hub"])
log = logging.getLogger("salesiq.api.datasets")


@router.get("/sample", summary="Open the built-in real demo dataset (Online Retail II)")
def open_sample():
    return store.sample().summary()


@router.post("/upload", summary="Upload a sales CSV (kept in memory only)")
async def upload(file: UploadFile = File(...)):
    name = re.sub(r"[^\w.\- ]", "_", file.filename or "upload.csv")[:80]
    if not name.lower().endswith((".csv", ".txt", ".tsv")):
        raise ApiError(415, "unsupported_type", "Please upload a .csv file (export from Excel as CSV).")
    limit = int(settings.max_upload_mb * 1024 * 1024)
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise ApiError(413, "file_too_large", f"The file is larger than {settings.max_upload_mb:g} MB.")
    try:
        result = read_csv_bytes(raw, max_rows=settings.max_upload_rows + 1)
    except IngestError as exc:
        raise ApiError(422, "unreadable_csv", str(exc)) from exc
    frame = result.frame
    truncated = len(frame) > settings.max_upload_rows
    if truncated:
        frame = frame.iloc[: settings.max_upload_rows]
    detection = detect_columns(frame)
    read_info = {"delimiter": result.delimiter, "encoding": result.encoding, "skipped_bad_lines": result.skipped_lines,
                 "rows": int(len(frame)), "columns": int(frame.shape[1]), "truncated_to_rows": settings.max_upload_rows if truncated else None}
    # Same file -> same id, so the browser can transparently re-send it if a
    # serverless instance restarted and forgot it.
    ws_id = "u" + hashlib.sha256(raw).hexdigest()[:15]
    ws = store.add_upload(name, frame, detection, read_info, ws_id)
    log.info("Upload %s: %s rows, %s cols", ws.id, len(frame), frame.shape[1])
    out = ws.summary()
    out["preview"] = ws.raw_preview
    return out


@router.get("/{dataset_id}", summary="Dataset profile, mapping, cleaning steps and quality")
def profile(dataset_id: str):
    ws = store.get(dataset_id)
    out = ws.summary()
    out["preview"] = ws.raw_preview
    if ws.status == "ready":
        out["frequency"] = detect_frequency(ws.prepared.sales["day"])
    return out


@router.post("/{dataset_id}/quality-check", summary="Preview the quality report for a mapping before cleaning")
def quality_check(dataset_id: str, body: PrepareIn):
    ws = store.get(dataset_id)
    if ws.raw is None:
        raise ApiError(409, "raw_released", "This dataset is already prepared.")
    from salesiq.datahub.detect import validate_mapping
    mapping = ColumnMapping.from_dict(body.mapping.model_dump())
    problems = validate_mapping(ws.raw, mapping)
    if problems:
        raise ApiError(422, "invalid_mapping", "The column mapping cannot be used.", problems)
    return quality_report(ws.raw, mapping)


@router.post("/{dataset_id}/prepare", summary="Confirm the mapping and run cleaning")
def prepare_dataset(dataset_id: str, body: PrepareIn):
    ws = store.get(dataset_id)
    mapping = ColumnMapping.from_dict(body.mapping.model_dump())
    opts = CleaningOptions(drop_duplicates=body.options.drop_duplicates,
                           separate_returns=body.options.separate_returns,
                           cancellation_prefix=body.options.cancellation_prefix or None)
    ws = store.prepare(ws, mapping, opts)
    return ws.summary()


@router.get("/{dataset_id}/rows", summary="Page through the cleaned sales table")
def rows(dataset_id: str, page: int = Query(1, ge=1), size: int = Query(25, ge=5, le=200),
         table: str = Query("sales", pattern="^(sales|returns)$")):
    ws = store.get(dataset_id)
    p = ws.require_ready()
    frame = p.sales if table == "sales" else p.returns
    total = len(frame)
    chunk = frame.iloc[(page - 1) * size: page * size].drop(columns=["day"], errors="ignore").copy()
    if "date" in chunk:
        chunk["date"] = chunk["date"].dt.strftime("%Y-%m-%d %H:%M")
    chunk = chunk.astype(object).where(pd.notna(chunk), None)
    return {"table": table, "page": page, "size": size, "total": int(total),
            "pages": int((total + size - 1) // size), "columns": list(chunk.columns),
            "rows": chunk.to_dict("records")}


@router.delete("/{dataset_id}", summary="Reset: forget this dataset and its cached results")
def reset(dataset_id: str):
    store.delete(dataset_id)
    return {"ok": True, "dataset_id": dataset_id,
            "note": "Cached analysis cleared." if dataset_id == SAMPLE_ID else "Upload removed from memory."}
