from fashion_personalization.models import EventType
from fashion_personalization.service import build_demo_service


def test_batch_refresh_writes_materialized_snapshots() -> None:
    service = build_demo_service()

    report = service.run_batch("batch-test-001")
    snapshot = service.get_snapshot("u-100")

    assert report.users_scanned >= 2
    assert report.snapshots_written >= 2
    assert report.users_scanned == report.snapshots_written + report.skipped_users
    assert report.source_event_count_total >= 4
    assert report.event_watermark_at_run is not None
    assert report.latest_snapshot_generated_at is not None
    assert report.stale_snapshot_users == 0
    assert snapshot is not None
    assert snapshot.source_event_count >= 3
    assert snapshot.recommendations


def test_batch_can_skip_cold_start_users() -> None:
    service = build_demo_service()
    service.record_event(
        user_id="u-cold",
        product_id="sku-bag-005",
        event_type=EventType.VIEW,
        idempotency_key="cold-1",
    )

    report = service.run_batch("batch-test-002", min_events=2)

    assert report.skipped_users >= 1
    assert service.get_snapshot("u-cold") is None


def test_admin_report_exposes_operational_counts() -> None:
    service = build_demo_service()
    service.run_batch("batch-test-003")

    report = service.admin_report()

    assert report.products == 6
    assert report.users >= 2
    assert report.processed_events >= 4
    assert report.failed_events == 0
    assert report.dead_letter_events == 0
    assert report.snapshots >= 2
    assert report.latest_batch_id == "batch-test-003"
    assert report.latest_batch_generated_at is not None
    assert report.event_watermark is not None
    assert report.batch_age_seconds is not None
    assert report.batch_event_lag_seconds == 0
