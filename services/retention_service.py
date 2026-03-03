"""Business logic for retention configuration and jobs."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from storage.postgres_repositories.retention_repo import RetentionRepository


class RetentionService:
    """Service layer for retention workflows."""

    def __init__(self, repo: RetentionRepository | None = None) -> None:
        self._repo = repo or RetentionRepository()

    async def get_config(self, seat_id: str | None = None) -> dict[str, Any]:
        config = await self._repo.get_retention_config(seat_id)
        if config:
            return config
        return {
            "raw_retention_days": 90,
            "summary_retention_days": 365,
            "auto_aggregate_after_days": 30,
        }

    async def set_config(
        self,
        raw_retention_days: int,
        summary_retention_days: int,
        auto_aggregate_after_days: int,
        seat_id: str | None = None,
    ) -> None:
        await self._repo.set_retention_config(
            raw_retention_days=raw_retention_days,
            summary_retention_days=summary_retention_days,
            auto_aggregate_after_days=auto_aggregate_after_days,
            seat_id=seat_id,
        )

    async def get_storage_stats(self, seat_id: str | None = None) -> dict[str, Any]:
        raw = await self._repo.get_raw_stats(seat_id)
        summary = await self._repo.get_summary_stats(seat_id)
        conversion_events = await self._repo.get_conversion_event_stats(seat_id)
        conversion_failures = await self._repo.get_conversion_failure_stats(seat_id)
        conversion_joins = await self._repo.get_conversion_join_stats(seat_id)
        return {
            "raw_rows": raw.get("cnt", 0) or 0,
            "raw_earliest_date": str(raw.get("earliest")) if raw.get("earliest") else None,
            "raw_latest_date": str(raw.get("latest")) if raw.get("latest") else None,
            "summary_rows": summary.get("cnt", 0) or 0,
            "summary_earliest_date": str(summary.get("earliest")) if summary.get("earliest") else None,
            "summary_latest_date": str(summary.get("latest")) if summary.get("latest") else None,
            "conversion_event_rows": conversion_events.get("cnt", 0) or 0,
            "conversion_event_earliest_ts": (
                str(conversion_events.get("earliest")) if conversion_events.get("earliest") else None
            ),
            "conversion_event_latest_ts": (
                str(conversion_events.get("latest")) if conversion_events.get("latest") else None
            ),
            "conversion_failure_rows": conversion_failures.get("cnt", 0) or 0,
            "conversion_failure_earliest_ts": (
                str(conversion_failures.get("earliest")) if conversion_failures.get("earliest") else None
            ),
            "conversion_failure_latest_ts": (
                str(conversion_failures.get("latest")) if conversion_failures.get("latest") else None
            ),
            "conversion_join_rows": conversion_joins.get("cnt", 0) or 0,
            "conversion_join_earliest_ts": (
                str(conversion_joins.get("earliest")) if conversion_joins.get("earliest") else None
            ),
            "conversion_join_latest_ts": (
                str(conversion_joins.get("latest")) if conversion_joins.get("latest") else None
            ),
        }

    async def run_retention_job(self, seat_id: str | None = None) -> dict[str, Any]:
        config = await self.get_config(seat_id)
        stats = {
            "aggregated_rows": 0,
            "deleted_raw_rows": 0,
            "deleted_summary_rows": 0,
            "deleted_conversion_event_rows": 0,
            "deleted_conversion_failure_rows": 0,
            "deleted_conversion_join_rows": 0,
        }

        aggregate_cutoff = (
            datetime.now() - timedelta(days=config["auto_aggregate_after_days"])
        ).strftime("%Y-%m-%d")
        await self._repo.aggregate_old_data(aggregate_cutoff, seat_id)

        delete_cutoff = (
            datetime.now() - timedelta(days=config["raw_retention_days"])
        ).strftime("%Y-%m-%d")
        stats["deleted_raw_rows"] = await self._repo.delete_raw_before(delete_cutoff, seat_id)
        stats["deleted_conversion_join_rows"] = await self._repo.delete_conversion_joins_before(
            delete_cutoff, seat_id
        )
        stats["deleted_conversion_event_rows"] = await self._repo.delete_conversion_events_before(
            delete_cutoff, seat_id
        )
        stats["deleted_conversion_failure_rows"] = await self._repo.delete_conversion_failures_before(
            delete_cutoff, seat_id
        )

        if config["summary_retention_days"] > 0:
            summary_cutoff = (
                datetime.now() - timedelta(days=config["summary_retention_days"])
            ).strftime("%Y-%m-%d")
            stats["deleted_summary_rows"] = await self._repo.delete_summary_before(summary_cutoff, seat_id)

        return stats
