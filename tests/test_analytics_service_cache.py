"""Cache behavior tests for AnalyticsService spend-stats path."""

from __future__ import annotations

import pytest

from services.analytics_service import AnalyticsService


class _StubAnalyticsRepo:
    def __init__(self) -> None:
        self.precompute_count_calls = 0
        self.spend_by_buyer_calls = 0
        self.row_count = 12
        self.spend_row = {
            "total_impressions": 1000,
            "total_spend_micros": 2_500_000,
        }

    async def table_exists(self, table_name: str) -> bool:
        del table_name
        return True

    async def get_precompute_row_count(
        self,
        table_name: str,
        days: int,
        filters=None,
        params=None,
    ) -> int:
        del table_name, days, filters, params
        self.precompute_count_calls += 1
        return self.row_count

    async def get_spend_stats_by_buyer(self, days: int, buyer_id: str):
        del days, buyer_id
        self.spend_by_buyer_calls += 1
        return dict(self.spend_row)


@pytest.mark.asyncio
async def test_get_spend_stats_uses_ttl_cache_for_same_inputs() -> None:
    AnalyticsService.clear_spend_stats_cache()
    repo = _StubAnalyticsRepo()
    service = AnalyticsService(repo=repo)

    first = await service.get_spend_stats(days=7, buyer_id="buyer-1")
    first.precompute_status["rtb_app_daily"]["row_count"] = 999999
    second = await service.get_spend_stats(days=7, buyer_id="buyer-1")

    assert repo.precompute_count_calls == 1
    assert repo.spend_by_buyer_calls == 1
    assert second.precompute_status["rtb_app_daily"]["row_count"] == 12


@pytest.mark.asyncio
async def test_get_spend_stats_cache_key_scopes_by_filter_tuple() -> None:
    AnalyticsService.clear_spend_stats_cache()
    repo = _StubAnalyticsRepo()
    service = AnalyticsService(repo=repo)

    await service.get_spend_stats(days=7, buyer_id="buyer-1")
    await service.get_spend_stats(days=14, buyer_id="buyer-1")

    assert repo.precompute_count_calls == 2
    assert repo.spend_by_buyer_calls == 2


@pytest.mark.asyncio
async def test_clear_spend_stats_cache_forces_recompute() -> None:
    AnalyticsService.clear_spend_stats_cache()
    repo = _StubAnalyticsRepo()
    service = AnalyticsService(repo=repo)

    await service.get_spend_stats(days=7, buyer_id="buyer-1")
    assert repo.spend_by_buyer_calls == 1

    AnalyticsService.clear_spend_stats_cache()
    await service.get_spend_stats(days=7, buyer_id="buyer-1")

    assert repo.spend_by_buyer_calls == 2
