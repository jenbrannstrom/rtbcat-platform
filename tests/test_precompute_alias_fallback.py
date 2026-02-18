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


class StubConfigBreakdownRepo:
    """Repo stub for config-breakdown window fallback tests."""

    def __init__(self, rows_for_30d: bool = True) -> None:
        self.rows_for_30d = rows_for_30d
        self.size_days_requested: list[int] = []

    async def table_exists(self, _table_name: str) -> bool:
        return True

    async def get_precompute_row_count(self, _table_name: str, _days: int, _filters=None, _params=None) -> int:
        # Force status.has_rows=False to exercise fallback path.
        return 0

    async def get_config_breakdown_size(
        self,
        _billing_id: str,
        days: int,
        _buyer_account_id: str | None = None,
        _limit: int = 50,
    ) -> list[dict]:
        self.size_days_requested.append(days)
        if days >= 30 and self.rows_for_30d:
            return [
                {
                    "name": "300x250",
                    "total_reached": 1200,
                    "total_impressions": 300,
                    "total_spend_micros": 1500000,
                }
            ]
        return []


@pytest.mark.asyncio
async def test_rtb_config_breakdown_falls_back_to_30d_when_7d_empty() -> None:
    repo = StubConfigBreakdownRepo(rows_for_30d=True)
    svc = RtbBidstreamService(repo=repo)

    payload = await svc.get_config_breakdown(
        billing_id="158610251694",
        breakdown_type="size",
        days=7,
        buyer_account_id="1487810529",
    )

    assert repo.size_days_requested == [7, 30]
    assert payload["fallback_applied"] is True
    assert payload["fallback_reason"] == "no_rows_7d_used_30d"
    assert payload["requested_days"] == 7
    assert payload["effective_days"] == 30
    assert payload["data_state"] == "degraded"
    assert len(payload["breakdown"]) == 1


@pytest.mark.asyncio
async def test_rtb_config_breakdown_no_fallback_when_30d_empty() -> None:
    repo = StubConfigBreakdownRepo(rows_for_30d=False)
    svc = RtbBidstreamService(repo=repo)

    payload = await svc.get_config_breakdown(
        billing_id="158610251694",
        breakdown_type="size",
        days=30,
        buyer_account_id="1487810529",
    )

    assert repo.size_days_requested == []
    assert payload["data_state"] == "unavailable"
    assert payload["fallback_applied"] is False
    assert payload["requested_days"] == 30
    assert payload["effective_days"] == 30
    assert payload["fallback_reason"] == "no_rows_for_window"
