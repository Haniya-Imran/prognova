"""Module D/E - shared filter logic for KPIs and the dashboard."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

import pandas as pd

FILTER_DIMS = ("product", "category", "region", "store")


@dataclass
class Filters:
    start: Optional[str] = None   # inclusive, YYYY-MM-DD
    end: Optional[str] = None     # inclusive, YYYY-MM-DD
    product: list[str] = field(default_factory=list)
    category: list[str] = field(default_factory=list)
    region: list[str] = field(default_factory=list)
    store: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict | None) -> "Filters":
        d = d or {}
        return cls(start=d.get("start") or None, end=d.get("end") or None,
                   **{k: list(d.get(k) or []) for k in FILTER_DIMS})

    def key(self) -> tuple:
        return (self.start, self.end) + tuple(tuple(sorted(getattr(self, k))) for k in FILTER_DIMS)

    def as_dict(self) -> dict:
        return asdict(self)

    def without_dates(self) -> "Filters":
        return Filters(None, None, *(list(getattr(self, k)) for k in FILTER_DIMS))


def apply_dims(frame: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    for dim in FILTER_DIMS:
        values = getattr(f, dim)
        if values and dim in frame:
            mask &= frame[dim].isin(values)
    return frame[mask]


def apply_dates(frame: pd.DataFrame, start, end) -> pd.DataFrame:
    if frame.empty:
        return frame
    day = frame["day"] if "day" in frame else frame["date"].dt.normalize()
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= day >= pd.Timestamp(start)
    if end is not None:
        mask &= day <= pd.Timestamp(end)
    return frame[mask]


def apply(frame: pd.DataFrame, f: Filters) -> pd.DataFrame:
    return apply_dates(apply_dims(frame, f), f.start, f.end)


def resolve_period(sales: pd.DataFrame, f: Filters) -> tuple[pd.Timestamp, pd.Timestamp]:
    lo, hi = sales["day"].min(), sales["day"].max()
    start = max(pd.Timestamp(f.start), lo) if f.start else lo
    end = min(pd.Timestamp(f.end), hi) if f.end else hi
    return start, end
