"""Session workspaces: one per dataset, kept in memory with results cached.

Uploaded business data never touches disk. Upload workspaces expire after a
period of inactivity (WORKSPACE_TTL_MINUTES) and the oldest is evicted when the
limit is reached. The built-in sample is loaded from the processed Parquet.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

import pandas as pd

from salesiq.analytics.dashboard import dashboard
from salesiq.analytics.filters import Filters
from salesiq.datahub import sample as sample_mod
from salesiq.datahub.detect import validate_mapping
from salesiq.eda.explore import run_eda
from salesiq.quality.prepare import PreparedData, prepare
from salesiq.schema import CleaningOptions, ColumnMapping

from ..config import settings
from ..errors import ApiError

log = logging.getLogger("salesiq.workspace")


@dataclass
class Workspace:
    id: str
    name: str
    source: str                       # "sample" | "upload"
    meta: dict
    raw: pd.DataFrame | None = None   # uploads only, until prepared
    detection: dict | None = None
    read_info: dict | None = None
    mapping: dict | None = None
    prepared: PreparedData | None = None
    raw_columns: list[str] = field(default_factory=list)
    raw_preview: list[dict] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    touched: float = field(default_factory=time.time)
    eda: dict | None = None
    dash_cache: "OrderedDict[tuple, dict]" = field(default_factory=OrderedDict)
    forecasts: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def status(self) -> str:
        return "ready" if self.prepared is not None else "needs_mapping"

    def require_ready(self) -> PreparedData:
        if self.prepared is None:
            raise ApiError(409, "not_prepared", "Confirm the column mapping first (Data Hub step 2).")
        return self.prepared

    def summary(self) -> dict:
        p = self.prepared
        out = {"id": self.id, "name": self.name, "source": self.source, "status": self.status,
               "meta": self.meta, "mapping": self.mapping, "raw_columns": self.raw_columns,
               "read_info": self.read_info, "detection": self.detection}
        if p is not None:
            dims = {d: bool(p.available.get(d)) for d in ("product", "category", "region", "store", "customer")}
            out.update({
                "rows": int(len(p.sales)), "return_rows": int(len(p.returns)),
                "date_min": p.sales["day"].min().strftime("%Y-%m-%d") if len(p.sales) else None,
                "date_max": p.sales["day"].max().strftime("%Y-%m-%d") if len(p.sales) else None,
                "available": p.available, "dimensions": dims, "has_time_of_day": p.has_time_of_day,
                "steps": p.steps, "quality": p.quality,
            })
        return out

    # ---- cached computations -------------------------------------------
    def get_eda(self) -> dict:
        p = self.require_ready()
        with self.lock:
            if self.eda is None:
                t = time.time()
                self.eda = run_eda(p.sales, p.returns, p.quality, self.raw_columns, p.has_time_of_day)
                log.info("EDA for %s computed in %.2fs", self.id, time.time() - t)
            return self.eda

    def get_dashboard(self, f: Filters, grain: str | None) -> dict:
        p = self.require_ready()
        key = f.key() + (grain,)
        with self.lock:
            if key in self.dash_cache:
                self.dash_cache.move_to_end(key)
                return self.dash_cache[key]
        result = dashboard(p.sales, p.returns, f, grain, p.has_time_of_day)
        with self.lock:
            self.dash_cache[key] = result
            while len(self.dash_cache) > 40:
                self.dash_cache.popitem(last=False)
        return result


class WorkspaceStore:
    def __init__(self) -> None:
        self._items: "OrderedDict[str, Workspace]" = OrderedDict()
        self._lock = threading.Lock()
        self._sample_lock = threading.Lock()

    # ---- sample ---------------------------------------------------------
    def sample(self) -> Workspace:
        with self._sample_lock:
            ws = self._items.get(sample_mod.SAMPLE_ID)
            if ws is not None:
                ws.touched = time.time()
                return ws
            t = time.time()
            prepared, meta = sample_mod.load_prepared()
            ws = Workspace(id=sample_mod.SAMPLE_ID, name=sample_mod.SAMPLE_META["name"], source="sample",
                           meta=dict(sample_mod.SAMPLE_META), prepared=prepared,
                           mapping=sample_mod.SAMPLE_MAPPING.as_dict(), raw_columns=meta["raw_columns"],
                           raw_preview=meta["raw_preview"])
            with self._lock:
                self._items[ws.id] = ws
            log.info("Sample dataset loaded in %.2fs (%s rows)", time.time() - t, f"{len(prepared.sales):,}")
            return ws

    # ---- uploads --------------------------------------------------------
    def add_upload(self, name: str, raw: pd.DataFrame, detection: dict, read_info: dict,
                   ws_id: str | None = None) -> Workspace:
        self.cleanup()
        ws = Workspace(id=ws_id or uuid.uuid4().hex[:12], name=name, source="upload",
                       meta={"name": name, "description": "Uploaded by you. Kept in server memory only for this session.",
                             "currency": "", "limitations": []},
                       raw=raw, detection=detection, read_info=read_info,
                       mapping=detection["mapping"], raw_columns=list(raw.columns),
                       raw_preview=raw.head(20).fillna("").to_dict("records"))
        with self._lock:
            uploads = [k for k, v in self._items.items() if v.source == "upload"]
            self._items.pop(ws.id, None)
            uploads = [k for k in uploads if k != ws.id]
            while len(uploads) >= settings.max_workspaces:
                old = uploads.pop(0)
                self._items.pop(old, None)
                log.info("Evicted workspace %s", old)
            self._items[ws.id] = ws
        return ws

    def prepare(self, ws: Workspace, mapping: ColumnMapping, options: CleaningOptions) -> Workspace:
        if ws.source == "sample":
            raise ApiError(400, "sample_fixed", "The sample dataset is already prepared.")
        if ws.raw is None:
            raise ApiError(409, "raw_released", "This upload was already prepared. Upload the file again to remap it.")
        problems = validate_mapping(ws.raw, mapping)
        if problems:
            raise ApiError(422, "invalid_mapping", "The column mapping cannot be used.", problems)
        prepared = prepare(ws.raw, mapping, options)
        if prepared.sales.empty:
            raise ApiError(422, "no_valid_rows", "No valid sales rows remain after cleaning.", prepared.steps)
        with ws.lock:
            ws.prepared, ws.mapping = prepared, mapping.as_dict()
            ws.eda, ws.forecasts = None, {}
            ws.dash_cache.clear()
            ws.raw = None  # free memory; the canonical table is all we need now
        return ws

    # ---- lookup ---------------------------------------------------------
    def get(self, ws_id: str) -> Workspace:
        if ws_id == sample_mod.SAMPLE_ID:
            return self.sample()
        self.cleanup()
        with self._lock:
            ws = self._items.get(ws_id)
        if ws is None:
            raise ApiError(404, "dataset_not_found",
                           "This dataset is no longer in memory (it expires after inactivity or a server restart). "
                           "Please upload it again.")
        ws.touched = time.time()
        return ws

    def delete(self, ws_id: str) -> bool:
        if ws_id == sample_mod.SAMPLE_ID:
            ws = self.sample()
            with ws.lock:
                ws.eda, ws.forecasts = None, {}
                ws.dash_cache.clear()
            return True
        with self._lock:
            return self._items.pop(ws_id, None) is not None

    def cleanup(self) -> None:
        limit = time.time() - settings.workspace_ttl_minutes * 60
        with self._lock:
            for k in [k for k, v in self._items.items() if v.source == "upload" and v.touched < limit]:
                self._items.pop(k, None)
                log.info("Expired workspace %s", k)


store = WorkspaceStore()
