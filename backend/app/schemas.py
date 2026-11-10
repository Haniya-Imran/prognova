"""Request bodies validated by FastAPI (responses are documented JSON dicts)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class MappingIn(BaseModel):
    date: Optional[str] = None
    revenue: Optional[str] = None
    quantity: Optional[str] = None
    unit_price: Optional[str] = None
    order_id: Optional[str] = None
    product: Optional[str] = None
    category: Optional[str] = None
    region: Optional[str] = None
    store: Optional[str] = None
    customer: Optional[str] = None


class CleaningIn(BaseModel):
    drop_duplicates: bool = True
    separate_returns: bool = True
    cancellation_prefix: Optional[str] = Field(default=None, max_length=5)


class PrepareIn(BaseModel):
    mapping: MappingIn
    options: CleaningIn = CleaningIn()


class FiltersIn(BaseModel):
    start: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    product: list[str] = Field(default_factory=list, max_length=200)
    category: list[str] = Field(default_factory=list, max_length=200)
    region: list[str] = Field(default_factory=list, max_length=200)
    store: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("start", "end")
    @classmethod
    def _real_date(cls, v):
        if v:
            from datetime import date
            try:
                date.fromisoformat(v)
            except ValueError as exc:
                raise ValueError(f"{v} is not a real calendar date") from exc
        return v

    @field_validator("end")
    @classmethod
    def _order(cls, v, info):
        start = info.data.get("start")
        if v and start and v < start:
            raise ValueError("end must be on or after start")
        return v


class DashboardIn(BaseModel):
    filters: FiltersIn = FiltersIn()
    grain: Optional[Literal["day", "week", "month"]] = None


class ForecastIn(BaseModel):
    target: Literal["net_revenue", "gross_revenue", "units"] = "net_revenue"
    filters: FiltersIn = FiltersIn()
