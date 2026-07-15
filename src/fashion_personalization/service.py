from __future__ import annotations

import itertools
from importlib import resources
from typing import Any

from fashion_personalization.batch import RecommendationBatchWorkflow
from fashion_personalization.catalog import load_products_from_json, search_products
from fashion_personalization.events import EventProcessor
from fashion_personalization.models import (
    AdminReport,
    BatchReport,
    EventStatus,
    EventType,
    Product,
    Recommendation,
    RecommendationSnapshot,
    SearchQuery,
    UserEvent,
)
from fashion_personalization.recommendation import rank_products
from fashion_personalization.store import InMemoryStore


class PersonalizationService:
    def __init__(self, store: InMemoryStore | None = None) -> None:
        self.store = store or InMemoryStore()
        self.processor = EventProcessor(self.store)
        self.batch = RecommendationBatchWorkflow(self.store)
        self._event_sequence = itertools.count(1)

    def load_catalog(self, products: list[Product]) -> None:
        self.store.upsert_products(products)

    def search(self, query: SearchQuery) -> list[Product]:
        return search_products(self.store.list_products(), query)

    def record_event(
        self,
        *,
        user_id: str,
        product_id: str,
        event_type: EventType,
        idempotency_key: str,
        payload: dict[str, Any] | None = None,
        process_now: bool = True,
    ) -> UserEvent:
        event = UserEvent(
            event_id=f"evt-{next(self._event_sequence):06d}",
            idempotency_key=idempotency_key,
            user_id=user_id,
            product_id=product_id,
            event_type=event_type,
            payload=payload or {},
        )
        stored_event, inserted = self.store.add_event(event)
        if inserted and process_now:
            self.processor.process(stored_event)
        return stored_event

    def process_pending_events(self) -> int:
        return self.processor.process_pending()

    def retry_dead_letter(self, *, event_id: str, idempotency_key: str) -> UserEvent:
        return self.processor.requeue_dead_letter(event_id, idempotency_key)

    def recommend_now(self, user_id: str, limit: int = 5, *, create_profile: bool = True) -> list[Recommendation]:
        profile = self.store.get_or_create_profile(user_id) if create_profile else self.store.get_profile(user_id)
        if profile is None:
            return []
        return rank_products(profile, self.store.list_products(), limit=limit)

    def run_batch(self, batch_id: str, min_events: int = 1) -> BatchReport:
        return self.batch.refresh_snapshots(batch_id=batch_id, min_events=min_events)

    def get_snapshot(self, user_id: str) -> RecommendationSnapshot | None:
        return self.store.get_snapshot(user_id)

    def admin_report(self) -> AdminReport:
        return self.store.admin_report()

    def dead_letters(self) -> list[UserEvent]:
        return self.store.list_events(EventStatus.DEAD_LETTER)


def build_demo_service() -> PersonalizationService:
    catalog_text = resources.files("fashion_personalization.data").joinpath("catalog.json").read_text(encoding="utf-8")
    service = PersonalizationService()
    service.load_catalog(load_products_from_json(catalog_text))
    service.record_event(
        user_id="u-100",
        product_id="sku-denim-001",
        event_type=EventType.VIEW,
        idempotency_key="seed-1",
        payload={"size": "M"},
    )
    service.record_event(
        user_id="u-100",
        product_id="sku-denim-001",
        event_type=EventType.ADD_TO_CART,
        idempotency_key="seed-2",
        payload={"size": "M"},
    )
    service.record_event(
        user_id="u-100",
        product_id="sku-knit-002",
        event_type=EventType.CLICK,
        idempotency_key="seed-3",
        payload={"size": "M"},
    )
    service.record_event(
        user_id="u-200",
        product_id="sku-dress-004",
        event_type=EventType.PURCHASE,
        idempotency_key="seed-4",
        payload={"size": "S"},
    )
    service.run_batch("demo-batch-001")
    return service
