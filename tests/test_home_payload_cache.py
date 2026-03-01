"""Cache behavior tests for HomeAnalyticsService payload builders."""

from __future__ import annotations

import pytest

from services.home_analytics_service import HomeAnalyticsService


class _StubCachedHomeRepo:
    def __init__(self) -> None:
        self.config_calls = 0
        self.funnel_calls = 0
        self.bidstream_summary_calls = 0
        self.endpoints_for_bidder_calls = 0
        self.observed_endpoint_rows_calls = 0
        self.home_seat_coverage_calls = 0
        self.bidstream_coverage_calls = 0
        self.bidder_lookup_calls = 0
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
                "total_publishers": 10,
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
                "total_countries": 3,
            }
        ]

    async def get_publisher_count(self, _days: int, _buyer_id: str | None):
        self.publisher_count_calls += 1
        return 10

    async def get_country_count(self, _days: int, _buyer_id: str | None):
        self.country_count_calls += 1
        return 3

    def get_window_bounds(self, days: int):
        del days
        return ("2026-02-23", "2026-03-01")

    async def get_bidstream_summary(self, _days: int, _buyer_id: str | None):
        self.bidstream_summary_calls += 1
        return {
            "total_bids": 100,
            "total_bids_in_auction": 60,
            "total_auctions_won": 30,
        }

    async def get_bidder_id_for_buyer(self, _buyer_id: str):
        self.bidder_lookup_calls += 1
        return "bidder-1"

    async def get_endpoints_for_bidder(self, _bidder_id: str | None):
        self.endpoints_for_bidder_calls += 1
        return [
            {
                "endpoint_id": "ep-1",
                "url": "https://ep1.example",
                "trading_location": "US_WEST",
                "maximum_qps": 100,
            }
        ]

    async def get_observed_endpoint_rows(self, _bidder_id: str | None):
        self.observed_endpoint_rows_calls += 1
        return [
            {
                "endpoint_id": "ep-1",
                "url": "https://ep1.example",
                "trading_location": "US_WEST",
                "current_qps": 40,
                "observed_at": None,
            }
        ]

    async def get_home_seat_coverage(self, _days: int, _buyer_id: str | None):
        self.home_seat_coverage_calls += 1
        return {"min_date": "2026-02-23", "max_date": "2026-03-01", "days_with_data": 7, "row_count": 7}

    async def get_bidstream_coverage(self, _days: int, _buyer_id: str | None):
        self.bidstream_coverage_calls += 1
        return {"min_date": "2026-02-23", "max_date": "2026-03-01", "days_with_data": 7, "row_count": 7}


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
    assert repo.publisher_count_calls == 0
    assert repo.country_count_calls == 0
    assert second["funnel"]["total_reached_queries"] == 1000


@pytest.mark.asyncio
async def test_endpoint_efficiency_payload_uses_ttl_cache_when_enabled() -> None:
    HomeAnalyticsService.clear_payload_caches()
    repo = _StubCachedHomeRepo()
    service = HomeAnalyticsService(repo=repo)
    service._cache_enabled = True

    first = await service.get_endpoint_efficiency_payload(days=7, buyer_id="buyer-1")
    first["summary"]["allocated_qps"] = 1
    second = await service.get_endpoint_efficiency_payload(days=7, buyer_id="buyer-1")

    assert repo.funnel_calls == 1
    assert repo.bidstream_summary_calls == 1
    assert repo.endpoints_for_bidder_calls == 1
    assert repo.observed_endpoint_rows_calls == 1
    assert repo.home_seat_coverage_calls == 1
    assert repo.bidstream_coverage_calls == 1
    assert second["summary"]["allocated_qps"] == 100
