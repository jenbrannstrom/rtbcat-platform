"""Tests for canonical/legacy precompute table alias fallback behavior."""

from __future__ import annotations

import pytest

from services.analytics_service import AnalyticsService
from services.rtb_bidstream_service import RtbBidstreamService


class StubAnalyticsRepo:
    """Minimal repo stub for AnalyticsService precompute-status tests."""

    def __init__(self) -> None:
        self.row_count_table_names: list[str] = []

    async def table_exists(self, table_name: str) -> bool:
        # Simulate env where canonical view is missing but legacy table exists.
        return table_name == "home_seat_daily"

    async def get_precompute_row_count(
        self,
        table_name: str,
        _days: int,
        _filters=None,
        _params=None,
    ) -> int:
        self.row_count_table_names.append(table_name)
        return 5


class StubRtbRepo:
    """Minimal repo stub for RtbBidstreamService precompute-status tests."""

    def __init__(self, existing_tables: set[str], row_count: int = 0) -> None:
        self._existing_tables = existing_tables
        self._row_count = row_count
        self.row_count_table_names: list[str] = []

    async def table_exists(self, table_name: str) -> bool:
        return table_name in self._existing_tables

    async def get_precompute_row_count(
        self,
        table_name: str,
        _days: int,
        _filters=None,
        _params=None,
    ) -> int:
        self.row_count_table_names.append(table_name)
        return self._row_count


@pytest.mark.asyncio
async def test_analytics_service_falls_back_to_legacy_precompute_table() -> None:
    repo = StubAnalyticsRepo()
    svc = AnalyticsService(repo=repo)

    status = await svc.get_precompute_status("seat_daily", days=7)

    assert status.table == "seat_daily"
    assert status.exists is True
    assert status.has_rows is True
    assert status.row_count == 5
    assert repo.row_count_table_names == ["home_seat_daily"]


@pytest.mark.asyncio
async def test_rtb_service_falls_back_to_legacy_precompute_table() -> None:
    repo = StubRtbRepo(existing_tables={"config_creative_daily"}, row_count=12)
    svc = RtbBidstreamService(repo=repo)

    status = await svc.get_precompute_status("pretarg_creative_daily", days=7)

    assert status.table == "pretarg_creative_daily"
    assert status.exists is True
    assert status.has_rows is True
    assert status.row_count == 12
    assert repo.row_count_table_names == ["config_creative_daily"]


@pytest.mark.asyncio
async def test_rtb_service_returns_missing_when_no_alias_exists() -> None:
    repo = StubRtbRepo(existing_tables=set(), row_count=9)
    svc = RtbBidstreamService(repo=repo)

    status = await svc.get_precompute_status("pretarg_geo_daily", days=7)

    assert status.table == "pretarg_geo_daily"
    assert status.exists is False
    assert status.has_rows is False
    assert status.row_count == 0
    assert repo.row_count_table_names == []
