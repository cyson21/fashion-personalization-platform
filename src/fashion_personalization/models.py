from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    VIEW = "view"
    CLICK = "click"
    ADD_TO_CART = "add_to_cart"
    PURCHASE = "purchase"
    DISLIKE = "dislike"


class EventStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    REQUEUED = "requeued"


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    brand: str
    category: str
    price: int
    tags: tuple[str, ...]
    sizes: tuple[str, ...]
    stock: int
    margin_rate: float
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def available(self) -> bool:
        return self.stock > 0


@dataclass
class UserProfile:
    user_id: str
    preferred_brands: dict[str, float] = field(default_factory=dict)
    preferred_categories: dict[str, float] = field(default_factory=dict)
    preferred_tags: dict[str, float] = field(default_factory=dict)
    size_preferences: dict[str, float] = field(default_factory=dict)
    target_price: float | None = None
    target_price_weight: float = 0.0
    negative_product_ids: set[str] = field(default_factory=set)
    event_count: int = 0
    updated_at: datetime = field(default_factory=utc_now)

    def touch(self) -> None:
        self.event_count += 1
        self.updated_at = utc_now()


@dataclass
class UserEvent:
    event_id: str
    idempotency_key: str
    user_id: str
    product_id: str
    event_type: EventType
    created_at: datetime = field(default_factory=utc_now)
    payload: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    status: EventStatus = EventStatus.PENDING
    error: str | None = None
    retry_source_event_id: str | None = None
    resolved_by_event_id: str | None = None

    def fingerprint(self) -> tuple[str, str, EventType, tuple[tuple[str, str], ...]]:
        payload_fingerprint = tuple(
            sorted((str(key), str(value)) for key, value in self.payload.items() if value is not None)
        )
        return (self.user_id, self.product_id, self.event_type, payload_fingerprint)


@dataclass(frozen=True)
class Recommendation:
    product_id: str
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationSnapshot:
    user_id: str
    recommendations: tuple[Recommendation, ...]
    generated_at: datetime
    source_event_count: int


@dataclass(frozen=True)
class BatchReport:
    batch_id: str
    users_scanned: int
    snapshots_written: int
    skipped_users: int
    failed_events: int
    dead_letter_events: int
    pending_events: int
    source_event_count_total: int
    event_watermark_at_run: datetime | None
    latest_snapshot_generated_at: datetime | None
    stale_snapshot_users: int
    generated_at: datetime


@dataclass(frozen=True)
class SearchQuery:
    keyword: str | None = None
    category: str | None = None
    size: str | None = None
    max_price: int | None = None
    in_stock_only: bool = True


@dataclass(frozen=True)
class AdminReport:
    products: int
    users: int
    processed_events: int
    pending_events: int
    failed_events: int
    dead_letter_events: int
    requeued_events: int
    snapshots: int
    latest_batch_id: str | None
    latest_batch_generated_at: datetime | None
    event_watermark: datetime | None
    batch_age_seconds: float | None
    batch_event_lag_seconds: float | None
