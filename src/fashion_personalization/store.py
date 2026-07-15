from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Iterable

from fashion_personalization.models import (
    AdminReport,
    BatchReport,
    EventStatus,
    Product,
    RecommendationSnapshot,
    UserEvent,
    UserProfile,
    utc_now,
)


class IdempotencyConflict(ValueError):
    pass


class DuplicateEventId(ValueError):
    pass


class InMemoryStore:
    """Repository boundary used by tests, CLI, and the optional API adapter."""

    def __init__(self) -> None:
        self._products: dict[str, Product] = {}
        self._profiles: dict[str, UserProfile] = {}
        self._events: dict[str, UserEvent] = {}
        self._idempotency_index: dict[str, str] = {}
        self._snapshots: dict[str, RecommendationSnapshot] = {}
        self._batch_reports: list[BatchReport] = []
        self._retry_sequences: dict[str, int] = {}

    def upsert_products(self, products: Iterable[Product]) -> None:
        for product in products:
            self._products[product.product_id] = product

    def get_product(self, product_id: str) -> Product | None:
        return self._products.get(product_id)

    def list_products(self) -> list[Product]:
        return list(self._products.values())

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        profile = self._profiles.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self._profiles[user_id] = profile
        return profile

    def get_profile(self, user_id: str) -> UserProfile | None:
        return self._profiles.get(user_id)

    def list_profiles(self) -> list[UserProfile]:
        return list(self._profiles.values())

    def add_event(self, event: UserEvent) -> tuple[UserEvent, bool]:
        if event.event_id in self._events:
            raise DuplicateEventId(f"duplicate event_id: {event.event_id}")
        existing_id = self._idempotency_index.get(event.idempotency_key)
        if existing_id:
            existing = self._events[existing_id]
            if existing.fingerprint() != event.fingerprint():
                raise IdempotencyConflict(
                    "idempotency_key is already used for a different event fingerprint"
                )
            return existing, False
        self._events[event.event_id] = event
        self._idempotency_index[event.idempotency_key] = event.event_id
        return event, True

    def get_event_by_idempotency_key(self, idempotency_key: str) -> UserEvent | None:
        event_id = self._idempotency_index.get(idempotency_key)
        if event_id is None:
            return None
        return self._events[event_id]

    def get_event(self, event_id: str) -> UserEvent | None:
        return self._events.get(event_id)

    def list_events(self, status: EventStatus | None = None) -> list[UserEvent]:
        events = list(self._events.values())
        if status is None:
            return events
        return [event for event in events if event.status == status]

    def mark_event(
        self,
        event_id: str,
        status: EventStatus,
        *,
        attempts: int | None = None,
        error: str | None = None,
        resolved_by_event_id: str | None = None,
    ) -> UserEvent:
        event = self._events[event_id]
        if attempts is not None:
            event.attempts = attempts
        event.status = status
        event.error = error
        if resolved_by_event_id is not None:
            event.resolved_by_event_id = resolved_by_event_id
        return event

    def clone_event_for_retry(self, event_id: str, idempotency_key: str) -> UserEvent:
        original = self._events[event_id]
        existing_retry = self.get_event_by_idempotency_key(idempotency_key)
        if existing_retry is not None:
            if existing_retry.retry_source_event_id == event_id:
                return existing_retry
            raise IdempotencyConflict("retry idempotency_key is already used")

        retry_sequence = self._retry_sequences.get(event_id, 0) + 1
        self._retry_sequences[event_id] = retry_sequence
        retry_event = replace(
            original,
            event_id=f"{original.event_id}-retry-{retry_sequence}",
            idempotency_key=idempotency_key,
            attempts=0,
            status=EventStatus.PENDING,
            error=None,
            retry_source_event_id=original.event_id,
            resolved_by_event_id=None,
        )
        stored_event, _ = self.add_event(retry_event)
        self.mark_event(
            event_id,
            EventStatus.REQUEUED,
            attempts=original.attempts,
            error=original.error,
            resolved_by_event_id=stored_event.event_id,
        )
        return retry_event

    def save_snapshot(self, snapshot: RecommendationSnapshot) -> None:
        self._snapshots[snapshot.user_id] = snapshot

    def get_snapshot(self, user_id: str) -> RecommendationSnapshot | None:
        return self._snapshots.get(user_id)

    def list_snapshots(self) -> list[RecommendationSnapshot]:
        return list(self._snapshots.values())

    def add_batch_report(self, report: BatchReport) -> None:
        self._batch_reports.append(report)

    def latest_batch_report(self) -> BatchReport | None:
        if not self._batch_reports:
            return None
        return self._batch_reports[-1]

    def admin_report(self) -> AdminReport:
        latest = self.latest_batch_report()
        event_watermark = self.event_watermark()
        latest_batch_generated_at = latest.generated_at if latest else None
        batch_age_seconds = (
            (utc_now() - latest.generated_at).total_seconds()
            if latest is not None
            else None
        )
        batch_event_lag_seconds = None
        if latest_batch_generated_at is not None and event_watermark is not None:
            batch_event_lag_seconds = max(
                0.0,
                (event_watermark - latest_batch_generated_at).total_seconds(),
            )
        return AdminReport(
            products=len(self._products),
            users=len(self._profiles),
            processed_events=len(self.list_events(EventStatus.PROCESSED)),
            pending_events=len(self.list_events(EventStatus.PENDING)),
            failed_events=len(self.list_events(EventStatus.FAILED)),
            dead_letter_events=len(self.list_events(EventStatus.DEAD_LETTER)),
            requeued_events=len(self.list_events(EventStatus.REQUEUED)),
            snapshots=len(self._snapshots),
            latest_batch_id=latest.batch_id if latest else None,
            latest_batch_generated_at=latest_batch_generated_at,
            event_watermark=event_watermark,
            batch_age_seconds=batch_age_seconds,
            batch_event_lag_seconds=batch_event_lag_seconds,
        )

    def event_watermark(self) -> datetime | None:
        processed = self.list_events(EventStatus.PROCESSED)
        if not processed:
            return None
        return max(event.created_at for event in processed)
