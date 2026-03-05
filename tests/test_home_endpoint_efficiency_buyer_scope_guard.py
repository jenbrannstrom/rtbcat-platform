"""Regression tests for buyer-scoped endpoint-efficiency query bounding."""

from __future__ import annotations

import pytest

from services.home_analytics_service import HomeAnalyticsService


class _CountingRepo:
    def __init__(self, bidder_id: str | None) -> None:
        self._bidder_id = bidder_id
        self.bidder_lookup_calls = 0
        self.endpoints_calls = 0
        self.observed_calls = 0

    async def get_funnel_row(self, _days: int, _buyer_id: str | None):
        return {
            "total_reached": 100,
            "total_impressions": 10,
            "total_bid_requests": 120,
        }

    async def get_bidstream_summary(self, _days: int, _buyer_id: str | None):
        return {
            "total_bids": 100,
            "total_bids_in_auction": 80,
            "total_auctions_won": 20,
        }

    async def get_bidder_id_for_buyer(self, _buyer_id: str):
        self.bidder_lookup_calls += 1
        return self._bidder_id

    async def get_home_seat_coverage(self, _days: int, _buyer_id: str | None):
        return {"days_with_data": 7, "row_count": 7, "min_date": "2026-02-27", "max_date": "2026-03-05"}

    async def get_bidstream_coverage(self, _days: int, _buyer_id: str | None):
        return {"days_with_data": 7, "row_count": 7, "min_date": "2026-02-27", "max_date": "2026-03-05"}

    async def get_endpoints_for_bidder(self, _bidder_id: str | None):
        self.endpoints_calls += 1
        return []

    async def get_observed_endpoint_rows(self, _bidder_id: str | None):
        self.observed_calls += 1
        return []

    def get_window_bounds(self, _days: int):
        return "2026-02-27", "2026-03-05"


@pytest.mark.asyncio
async def test_buyer_scope_guard_skips_unfiltered_endpoint_queries_when_bidder_missing() -> None:
    repo = _CountingRepo(bidder_id=None)
    service = HomeAnalyticsService(repo=repo)

    payload = await service.get_endpoint_efficiency_payload(days=7, buyer_id="1487810529")

    assert repo.bidder_lookup_calls == 1
    assert repo.endpoints_calls == 0
    assert repo.observed_calls == 0
    assert payload["endpoint_reconciliation"]["counts"]["catscan_endpoints"] == 0
    assert payload["summary"]["observed_query_rate_qps"] is None


@pytest.mark.asyncio
async def test_unscoped_calls_keep_existing_behavior() -> None:
    repo = _CountingRepo(bidder_id=None)
    service = HomeAnalyticsService(repo=repo)

    await service.get_endpoint_efficiency_payload(days=7, buyer_id=None)

    assert repo.bidder_lookup_calls == 0
    assert repo.endpoints_calls == 1
    assert repo.observed_calls == 1
