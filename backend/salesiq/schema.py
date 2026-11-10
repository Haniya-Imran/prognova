"""Canonical column names shared by every stage of the workspace."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

# Canonical roles a source column can play.
ROLES = (
    "date",
    "revenue",
    "quantity",
    "unit_price",
    "order_id",
    "product",
    "category",
    "region",
    "store",
    "customer",
)

REQUIRED_HELP = (
    "A date column is required, plus either a revenue/sales column "
    "or both a quantity and a unit price column."
)


@dataclass
class ColumnMapping:
    """Which source column fills each canonical role (None = not available)."""

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

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ColumnMapping":
        clean = {k: (v or None) for k, v in (data or {}).items() if k in ROLES}
        return cls(**clean)

    def used_columns(self) -> list[str]:
        return [v for v in self.as_dict().values() if v]


@dataclass
class CleaningOptions:
    drop_duplicates: bool = True
    # Treat negative quantity / revenue lines as returns (kept apart, not deleted).
    separate_returns: bool = True
    # Prefix in order_id that marks a cancellation (Online Retail uses "C").
    cancellation_prefix: Optional[str] = None
    # Product codes that are not merchandise (postage, fees, adjustments).
    non_merchandise_codes: list[str] = field(default_factory=list)
    non_merchandise_prefixes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)
