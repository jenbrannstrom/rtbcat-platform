"""Cache behavior tests for HomeAnalyticsService payload builders."""

from __future__ import annotations

import pytest

from services.home_analytics_service import HomeAnalyticsService


class _StubCachedHomeRepo:
    def __init__(self) -> None:
        self.config_calls = 0
        self.funnel_calls = 0
        self.publisher_rows_calls = 0
        self.geo_rows_calls = 0
        self.publisher_count_calls = 0
        self.country_count_calls = 0

    async def get_config_rows(self, _days: int, _buyer_id: str | None):
        self.config_calls += 1
        return [
            {
                "billing_id": "cfg-1",
                "total_reached": 100,
                "total_impressions": 25,
                "total_bids_in_auction": 50,
                "total_auctions_won": 20,
                "overall_total_reached": 100,
                "overall_total_impressions": 25,
            }
        ]

    async def get_funnel_row(self, _days: int, _buyer_id: str | None):
        self.funnel_calls += 1
        return {
            "total_reached": 1000,
            "total_impressions": 250,
            "total_bids": 600,
            "total_successful_responses": 500,
            "total_bid_requests": 1200,
        }

    async def get_publisher_rows(self, _days: int, _buyer_id: str | None, _limit: int):
        self.publisher_rows_calls += 1
        return [
            {
                "publisher_id": "pub-1",
                "publisher_name": "Pub",
                "reached": 200,
                "impressions": 50,
                "total_bids": 130,
                "auctions_won": 40,
            }
        ]

    async def get_geo_rows(self, _days: int, _buyer_id: str | None, _limit: int):
        self.geo_rows_calls += 1
        return [
            {
                "country": "US",
                "reached": 300,
                "impressions": 80,
                "total_bids": 170,
                "auctions_won": 60,
            }
        ]

    async def get_publisher_count(self, _days: int, _buyer_id: str | None):
        self.publisher_count_calls += 1
        return 10

    async def get_country_count(self, _days: int, _buyer_id: str | None):
        self.country_count_calls += 1
        return 3


@pytest.mark.asyncio
async def test_config_payload_uses_ttl_cache_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    HomeAnalyticsService.clear_payload_caches()
    repo = _StubCachedHomeRepo()
    service = HomeAnalyticsService(repo=repo)
    service._cache_enabled = True

    async def stub_status(
        _table_name: str,
        _days: int,
        filters: list[str] | None = None,
        params: list[str] | None = None,
    ) -> dict:
        del filters, params
        return {"table": "pretarg_daily", "exists": True, "has_rows": True, "row_count": 1}

    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", stub_status)

    first = await service.get_config_payload(days=7, buyer_id="buyer-1")
    first["configs"][0]["reached"] = 9999
    second = await service.get_config_payload(days=7, buyer_id="buyer-1")

    assert repo.config_calls == 1
    assert second["configs"][0]["reached"] == 100


@pytest.mark.asyncio
async def test_funnel_payload_uses_ttl_cache_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    HomeAnalyticsService.clear_payload_caches()
    repo = _StubCachedHomeRepo()
    service = HomeAnalyticsService(repo=repo)
    service._cache_enabled = True

    async def stub_status(
        table_name: str,
        _days: int,
        filters: list[str] | None = None,
        params: list[str] | None = None,
    ) -> dict:
        del filters, params
        return {"table": table_name, "exists": True, "has_rows": True, "row_count": 1}

    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", stub_status)

    first = await service.get_funnel_payload(days=7, buyer_id="buyer-1", limit=30)
    first["funnel"]["total_reached_queries"] = 1
    second = await service.get_funnel_payload(days=7, buyer_id="buyer-1", limit=30)

    assert repo.funnel_calls == 1
    assert repo.publisher_rows_calls == 1
    assert repo.geo_rows_calls == 1
    assert repo.publisher_count_calls == 1
    assert repo.country_count_calls == 1
    assert second["funnel"]["total_reached_queries"] == 1000
