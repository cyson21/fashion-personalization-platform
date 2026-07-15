from __future__ import annotations

from fashion_personalization.models import EventStatus, UserEvent
from fashion_personalization.recommendation import apply_event_to_profile
from fashion_personalization.store import InMemoryStore


class EventProcessingError(RuntimeError):
    pass


class EventProcessor:
    def __init__(self, store: InMemoryStore, max_attempts: int = 3) -> None:
        self.store = store
        self.max_attempts = max_attempts

    def process_pending(self) -> int:
        processed = 0
        retryable = [
            *self.store.list_events(EventStatus.PENDING),
            *self.store.list_events(EventStatus.FAILED),
        ]
        for event in list(retryable):
            self.process(event)
            if event.status == EventStatus.PROCESSED:
                processed += 1
        return processed

    def process(self, event: UserEvent) -> UserEvent:
        event.attempts += 1
        product = self.store.get_product(event.product_id)
        if product is None:
            return self._fail(event, f"unknown product: {event.product_id}")

        try:
            profile = self.store.get_or_create_profile(event.user_id)
            apply_event_to_profile(profile, product, event)
        except Exception as exc:  # pragma: no cover - defensive boundary
            return self._fail(event, str(exc))

        return self.store.mark_event(event.event_id, EventStatus.PROCESSED, attempts=event.attempts, error=None)

    def requeue_dead_letter(self, event_id: str, idempotency_key: str) -> UserEvent:
        event = self.store.get_event(event_id)
        if event is None:
            raise EventProcessingError(f"unknown event: {event_id}")
        if event.status != EventStatus.DEAD_LETTER:
            raise EventProcessingError(f"event is not dead-lettered: {event_id}")
        return self.store.clone_event_for_retry(event_id, idempotency_key)

    def _fail(self, event: UserEvent, error: str) -> UserEvent:
        status = EventStatus.DEAD_LETTER if event.attempts >= self.max_attempts else EventStatus.FAILED
        return self.store.mark_event(event.event_id, status, attempts=event.attempts, error=error)
