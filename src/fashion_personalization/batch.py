from __future__ import annotations

from fashion_personalization.models import BatchReport, EventStatus, RecommendationSnapshot, utc_now
from fashion_personalization.recommendation import rank_products
from fashion_personalization.store import InMemoryStore


class RecommendationBatchWorkflow:
    def __init__(self, store: InMemoryStore, default_limit: int = 5) -> None:
        self.store = store
        self.default_limit = default_limit

    def refresh_snapshots(self, *, batch_id: str, min_events: int = 1) -> BatchReport:
        products = self.store.list_products()
        event_watermark = self.store.event_watermark()
        users_scanned = 0
        snapshots_written = 0
        skipped_users = 0

        for profile in self.store.list_profiles():
            users_scanned += 1
            if profile.event_count < min_events:
                skipped_users += 1
                continue
            recommendations = rank_products(profile, products, limit=self.default_limit)
            snapshot = RecommendationSnapshot(
                user_id=profile.user_id,
                recommendations=tuple(recommendations),
                generated_at=utc_now(),
                source_event_count=profile.event_count,
            )
            self.store.save_snapshot(snapshot)
            snapshots_written += 1

        stale_snapshot_users = 0
        latest_snapshot_generated_at = None
        for profile in self.store.list_profiles():
            snapshot = self.store.get_snapshot(profile.user_id)
            if snapshot is None:
                if profile.event_count >= min_events:
                    stale_snapshot_users += 1
                continue
            latest_snapshot_generated_at = (
                snapshot.generated_at
                if latest_snapshot_generated_at is None
                else max(latest_snapshot_generated_at, snapshot.generated_at)
            )
            if snapshot.source_event_count < profile.event_count:
                stale_snapshot_users += 1

        report = BatchReport(
            batch_id=batch_id,
            users_scanned=users_scanned,
            snapshots_written=snapshots_written,
            skipped_users=skipped_users,
            failed_events=len(self.store.list_events(EventStatus.FAILED)),
            dead_letter_events=len(self.store.list_events(EventStatus.DEAD_LETTER)),
            pending_events=len(self.store.list_events(EventStatus.PENDING)),
            source_event_count_total=sum(profile.event_count for profile in self.store.list_profiles()),
            event_watermark_at_run=event_watermark,
            latest_snapshot_generated_at=latest_snapshot_generated_at,
            stale_snapshot_users=stale_snapshot_users,
            generated_at=utc_now(),
        )
        self.store.add_batch_report(report)
        return report
