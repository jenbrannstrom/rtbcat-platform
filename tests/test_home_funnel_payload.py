"""Behavior tests for /analytics/home/funnel payload assembly."""

from __future__ import annotations

import pytest

from services.home_analytics_service import HomeAnalyticsService


class _StubHomeFunnelRepo:
    async def get_funnel_row(self, _days: int, _buyer_id: str | None):
        return {
            "total_reached": 1000,
            "total_impressions": 250,
            "total_bids": 700,
            "total_successful_responses": 600,
            "total_bid_requests": 1200,
        }

    async def get_publisher_rows(self, _days: int, _buyer_id: str | None, _limit: int):
        return [
            {
                "publisher_id": "pub-1",
                "publisher_name": "Example Pub",
                "reached": 400,
                "impressions": 100,
                "total_bids": 250,
                "auctions_won": 90,
            }
        ]

    async def get_geo_rows(self, _days: int, _buyer_id: str | None, _limit: int):
        return [
            {
                "country": "US",
                "reached": 600,
                "impressions": 150,
                "total_bids": 450,
                "auctions_won": 130,
            }
        ]

    async def get_publisher_count(self, _days: int, _buyer_id: str | None):
        return 12

    async def get_country_count(self, _days: int, _buyer_id: str | None):
        return 5


@pytest.mark.asyncio
async def test_home_funnel_returns_unavailable_when_seat_precompute_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = HomeAnalyticsService(repo=_StubHomeFunnelRepo())

    async def stub_status(
        table_name: str,
        _days: int,
        filters: list[str] | None = None,
        params: list[str] | None = None,
    ) -> dict:
        del filters, params
        return {"table": table_name, "exists": True, "has_rows": False, "row_count": 0}

    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", stub_status)

    payload = await service.get_funnel_payload(days=7, buyer_id="buyer-1", limit=30)

    assert payload["has_data"] is False
    assert payload["data_state"] == "unavailable"
    assert payload["fallback_reason"] == "no_precompute_rows"
    assert payload["publishers"] == []
    assert payload["geos"] == []


@pytest.mark.asyncio
async def test_home_funnel_returns_expected_aggregates_when_data_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = HomeAnalyticsService(repo=_StubHomeFunnelRepo())

    async def stub_status(
        table_name: str,
        _days: int,
        filters: list[str] | None = None,
        params: list[str] | None = None,
    ) -> dict:
        del filters, params
        return {"table": table_name, "exists": True, "has_rows": True, "row_count": 10}

    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", stub_status)

    payload = await service.get_funnel_payload(days=7, buyer_id="buyer-1", limit=30)

    assert payload["has_data"] is True
    assert payload["data_state"] == "healthy"
    assert payload["funnel"]["total_reached_queries"] == 1000
    assert payload["funnel"]["total_impressions"] == 250
    assert payload["funnel"]["win_rate"] == 25.0
    assert payload["funnel"]["waste_rate"] == 75.0
    assert payload["data_sources"]["publisher_count"] == 12
    assert payload["data_sources"]["country_count"] == 5
    assert payload["publishers"][0]["publisher_id"] == "pub-1"
    assert payload["geos"][0]["country"] == "US"
