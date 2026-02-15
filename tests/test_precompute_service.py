"""Precompute service tests for canonical/legacy table-name compatibility."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from services.precompute_service import PrecomputeService


class StubPrecomputeRepo:
    """Minimal async stub for PrecomputeService tests."""

    def __init__(self, table_dates: dict[str, str | None]) -> None:
        now_iso = datetime.utcnow().isoformat()
        self._refresh_rows = [
            {"cache_name": cache_name, "refreshed_at": now_iso}
            for cache_name in PrecomputeService.REQUIRED_CACHES
        ]
        self._table_dates = table_dates
        self.requested_table_names: list[str] = []

    async def get_cache_refresh_times(self) -> list[dict[str, Any]]:
        return self._refresh_rows

    async def get_latest_metric_dates(self, table_names: list[str]) -> dict[str, str | None]:
        self.requested_table_names = list(table_names)
        return {table_name: self._table_dates.get(table_name) for table_name in table_names}


@pytest.mark.asyncio
async def test_health_prefers_canonical_serving_views() -> None:
    source_date = "2026-02-12"
    table_dates: dict[str, str | None] = {PrecomputeService.RAW_FACT_TABLE: source_date}
    for legacy_name, canonical_name in PrecomputeService.SERVING_TABLE_ALIASES:
        table_dates[legacy_name] = "2026-02-09"
        table_dates[canonical_name] = source_date

    repo = StubPrecomputeRepo(table_dates=table_dates)
    service = PrecomputeService(repo=repo)
    status = await service.get_health_status(max_age_hours=48)

    assert status.date_parity_ok is True
    for legacy_name, canonical_name in PrecomputeService.SERVING_TABLE_ALIASES:
        assert canonical_name in repo.requested_table_names
        assert legacy_name in repo.requested_table_names
        assert status.serving_metric_dates[legacy_name] == source_date
        assert status.serving_lag_days[legacy_name] == 0


@pytest.mark.asyncio
async def test_health_falls_back_to_legacy_tables_when_views_missing() -> None:
    source_date = "2026-02-12"
    table_dates: dict[str, str | None] = {PrecomputeService.RAW_FACT_TABLE: source_date}
    for legacy_name, _canonical_name in PrecomputeService.SERVING_TABLE_ALIASES:
        table_dates[legacy_name] = source_date

    repo = StubPrecomputeRepo(table_dates=table_dates)
    service = PrecomputeService(repo=repo)
    status = await service.get_health_status(max_age_hours=48)

    assert status.date_parity_ok is True
    for legacy_name, canonical_name in PrecomputeService.SERVING_TABLE_ALIASES:
        assert canonical_name in repo.requested_table_names
        assert status.serving_metric_dates[legacy_name] == source_date
        assert status.serving_lag_days[legacy_name] == 0
