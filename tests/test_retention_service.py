"""Unit tests for retention service conversion cleanup coverage."""

from __future__ import annotations

import pytest

from services.retention_service import RetentionService


class _StubRetentionRepo:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, str | None]] = []

    async def get_retention_config(self, seat_id: str | None = None) -> dict:
        return {
            "raw_retention_days": 90,
            "summary_retention_days": 365,
            "auto_aggregate_after_days": 30,
        }

    async def get_raw_stats(self, seat_id: str | None = None) -> dict:
        return {"cnt": 10, "earliest": "2026-01-01", "latest": "2026-03-01"}

    async def get_summary_stats(self, seat_id: str | None = None) -> dict:
        return {"cnt": 5, "earliest": "2026-01-01", "latest": "2026-03-01"}

    async def get_conversion_event_stats(self, seat_id: str | None = None) -> dict:
        return {"cnt": 42, "earliest": "2026-02-01T00:00:00+00:00", "latest": "2026-03-03T00:00:00+00:00"}

    async def get_conversion_failure_stats(self, seat_id: str | None = None) -> dict:
        return {"cnt": 7, "earliest": "2026-02-15T00:00:00+00:00", "latest": "2026-03-03T00:00:00+00:00"}

    async def get_conversion_join_stats(self, seat_id: str | None = None) -> dict:
        return {"cnt": 19, "earliest": "2026-02-10T00:00:00+00:00", "latest": "2026-03-03T00:00:00+00:00"}

    async def get_conversion_raw_event_stats(self, seat_id: str | None = None) -> dict:
        return {"cnt": 61, "earliest": "2026-02-20T00:00:00+00:00", "latest": "2026-03-03T00:00:00+00:00"}

    async def aggregate_old_data(self, cutoff_date: str, seat_id: str | None = None) -> None:
        self.calls.append(("aggregate_old_data", cutoff_date, seat_id))

    async def delete_raw_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        self.calls.append(("delete_raw_before", cutoff_date, seat_id))
        return 11

    async def delete_conversion_joins_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        self.calls.append(("delete_conversion_joins_before", cutoff_date, seat_id))
        return 3

    async def delete_conversion_events_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        self.calls.append(("delete_conversion_events_before", cutoff_date, seat_id))
        return 13

    async def delete_conversion_failures_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        self.calls.append(("delete_conversion_failures_before", cutoff_date, seat_id))
        return 2

    async def delete_conversion_raw_events_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        self.calls.append(("delete_conversion_raw_events_before", cutoff_date, seat_id))
        return 5

    async def delete_summary_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        self.calls.append(("delete_summary_before", cutoff_date, seat_id))
        return 17


@pytest.mark.asyncio
async def test_get_storage_stats_includes_conversion_tables() -> None:
    repo = _StubRetentionRepo()
    service = RetentionService(repo=repo)

    stats = await service.get_storage_stats(seat_id="1111111111")

    assert stats["raw_rows"] == 10
    assert stats["summary_rows"] == 5
    assert stats["conversion_event_rows"] == 42
    assert stats["conversion_failure_rows"] == 7
    assert stats["conversion_join_rows"] == 19
    assert stats["conversion_raw_event_rows"] == 61
    assert stats["conversion_event_latest_ts"] == "2026-03-03T00:00:00+00:00"
    assert stats["conversion_failure_latest_ts"] == "2026-03-03T00:00:00+00:00"
    assert stats["conversion_join_latest_ts"] == "2026-03-03T00:00:00+00:00"
    assert stats["conversion_raw_event_latest_ts"] == "2026-03-03T00:00:00+00:00"


@pytest.mark.asyncio
async def test_run_retention_job_deletes_conversion_tables() -> None:
    repo = _StubRetentionRepo()
    service = RetentionService(repo=repo)

    result = await service.run_retention_job(seat_id="1111111111")

    assert result["deleted_raw_rows"] == 11
    assert result["deleted_conversion_join_rows"] == 3
    assert result["deleted_conversion_event_rows"] == 13
    assert result["deleted_conversion_failure_rows"] == 2
    assert result["deleted_summary_rows"] == 17
    assert result["deleted_conversion_raw_event_rows"] == 5

    called_names = [name for name, _, _ in repo.calls]
    assert "delete_conversion_joins_before" in called_names
    assert "delete_conversion_events_before" in called_names
    assert "delete_conversion_failures_before" in called_names
    assert "delete_conversion_raw_events_before" in called_names
