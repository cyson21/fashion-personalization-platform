import pytest

from fashion_personalization.models import EventStatus, EventType
from fashion_personalization.service import build_demo_service
from fashion_personalization.store import IdempotencyConflict


def test_event_ingestion_is_idempotent() -> None:
    service = build_demo_service()
    before = service.admin_report().processed_events

    first = service.record_event(
        user_id="u-300",
        product_id="sku-bag-005",
        event_type=EventType.CLICK,
        idempotency_key="same-click",
    )
    second = service.record_event(
        user_id="u-300",
        product_id="sku-bag-005",
        event_type=EventType.CLICK,
        idempotency_key="same-click",
    )

    assert first.event_id == second.event_id
    assert service.admin_report().processed_events == before + 1


def test_idempotency_key_conflict_is_rejected() -> None:
    service = build_demo_service()
    service.record_event(
        user_id="u-300",
        product_id="sku-bag-005",
        event_type=EventType.CLICK,
        idempotency_key="conflict-key",
    )

    with pytest.raises(IdempotencyConflict):
        service.record_event(
            user_id="u-300",
            product_id="sku-knit-002",
            event_type=EventType.CLICK,
            idempotency_key="conflict-key",
        )


def test_idempotency_key_conflict_includes_payload_fingerprint() -> None:
    service = build_demo_service()
    service.record_event(
        user_id="u-301",
        product_id="sku-bag-005",
        event_type=EventType.CLICK,
        idempotency_key="payload-conflict-key",
        payload={"size": "FREE"},
    )

    with pytest.raises(IdempotencyConflict):
        service.record_event(
            user_id="u-301",
            product_id="sku-bag-005",
            event_type=EventType.CLICK,
            idempotency_key="payload-conflict-key",
            payload={"size": "M"},
        )


def test_unknown_product_moves_to_dead_letter_after_retry_budget() -> None:
    service = build_demo_service()

    event = service.record_event(
        user_id="u-400",
        product_id="missing-sku",
        event_type=EventType.CLICK,
        idempotency_key="bad-product",
    )
    assert event.status == EventStatus.FAILED

    service.process_pending_events()
    service.process_pending_events()

    assert service.store.get_event(event.event_id).status == EventStatus.DEAD_LETTER
    assert service.admin_report().dead_letter_events == 1
    assert service.admin_report().failed_events == 0


def test_dead_letter_can_be_requeued_with_new_idempotency_key() -> None:
    service = build_demo_service()
    event = service.record_event(
        user_id="u-500",
        product_id="missing-sku",
        event_type=EventType.CLICK,
        idempotency_key="bad-product-retry-source",
    )
    service.store.mark_event(event.event_id, EventStatus.DEAD_LETTER, attempts=3, error="unknown product")

    retry = service.retry_dead_letter(event_id=event.event_id, idempotency_key="bad-product-retry-1")

    assert retry.event_id != event.event_id
    assert retry.status == EventStatus.PENDING
    assert service.store.get_event(event.event_id).status == EventStatus.REQUEUED
    assert service.admin_report().dead_letter_events == 0
    assert service.admin_report().requeued_events == 1


def test_dead_letter_retry_rejects_original_idempotency_key() -> None:
    service = build_demo_service()
    event = service.record_event(
        user_id="u-501",
        product_id="missing-sku",
        event_type=EventType.CLICK,
        idempotency_key="bad-product-original-key",
    )
    service.store.mark_event(event.event_id, EventStatus.DEAD_LETTER, attempts=3, error="unknown product")

    with pytest.raises(IdempotencyConflict):
        service.retry_dead_letter(event_id=event.event_id, idempotency_key="bad-product-original-key")
