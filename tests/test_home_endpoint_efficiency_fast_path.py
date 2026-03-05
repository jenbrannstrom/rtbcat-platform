"""Fast-path regression tests for endpoint-efficiency payload assembly."""

from __future__ import annotations

import pytest

from services.home_analytics_service import HomeAnalyticsService


class _FastPathRepo:
    def __init__(self) -> None:
        self.fast_funnel_calls = 0
        self.fast_bidstream_calls = 0
        self.fast_bidstream_coverage_calls = 0

    async def get_funnel_with_coverage(self, _days: int, _buyer_id: str | None):
        self.fast_funnel_calls += 1
        return {
            "total_reached": 1000,
            "total_impressions": 250,
            "total_bids": 600,
            "total_successful_responses": 500,
            "total_bid_requests": 1200,
            "min_date": "2026-02-27",
            "max_date": "2026-03-05",
            "days_with_data": 7,
            "row_count": 7,
        }

    async def get_bidstream_summary_precomputed(self, _days: int, _buyer_id: str | None):
        self.fast_bidstream_calls += 1
        return {
            "total_bids": 600,
            "total_bids_in_auction": 400,
            "total_auctions_won": 300,
        }

    async def get_bidstream_coverage_from_completeness(self, _days: int, _buyer_id: str | None):
        self.fast_bidstream_coverage_calls += 1
        return {
            "min_date": "2026-02-27",
            "max_date": "2026-03-05",
            "days_with_data": 7,
            "row_count": 7,
        }

    async def get_bidder_id_for_buyer(self, _buyer_id: str):
        return "bidder-1"

    async def get_endpoints_for_bidder(self, _bidder_id: str | None):
        return []

    async def get_observed_endpoint_rows(self, _bidder_id: str | None):
        return []

    def get_window_bounds(self, _days: int):
        return ("2026-02-27", "2026-03-05")

    # Legacy methods must not be called when fast path exists.
    async def get_funnel_row(self, _days: int, _buyer_id: str | None):
        raise AssertionError("legacy get_funnel_row should not be called")

    async def get_home_seat_coverage(self, _days: int, _buyer_id: str | None):
        raise AssertionError("legacy get_home_seat_coverage should not be called")

    async def get_bidstream_summary(self, _days: int, _buyer_id: str | None):
        raise AssertionError("legacy get_bidstream_summary should not be called")

    async def get_bidstream_coverage(self, _days: int, _buyer_id: str | None):
        raise AssertionError("legacy get_bidstream_coverage should not be called")


@pytest.mark.asyncio
async def test_endpoint_efficiency_prefers_fast_repo_paths() -> None:
    repo = _FastPathRepo()
    service = HomeAnalyticsService(repo=repo)

    payload = await service.get_endpoint_efficiency_payload(days=7, buyer_id="1487810529")

    assert repo.fast_funnel_calls == 1
    assert repo.fast_bidstream_calls == 1
    assert repo.fast_bidstream_coverage_calls == 1

    summary = payload["summary"]
    assert summary["bids"] == 600
    assert summary["bids_in_auction"] == 400
    assert summary["auctions_won"] == 300

    coverage = payload["data_coverage"]["rtb_bidstream"]
    assert coverage["days_with_data"] == 7
    assert coverage["start_date"] == "2026-02-27"
    assert coverage["end_date"] == "2026-03-05"
