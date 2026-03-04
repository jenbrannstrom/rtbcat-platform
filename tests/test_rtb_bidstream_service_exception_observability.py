"""Exception observability fallback tests for RtbBidstreamService."""

from __future__ import annotations

import logging

import pytest

from services.rtb_bidstream_service import RtbBidstreamService


class _RepoBillingLookupFails:
    async def get_bidder_id_for_buyer(self, buyer_id: str):
        del buyer_id
        raise RuntimeError("seat lookup failed")

    async def get_billing_ids_for_bidder(self, bidder_id: str | None):
        del bidder_id
        return ["ignored"]


class _RepoCreativeBidTotalsFail:
    async def table_exists(self, table_name: str):
        del table_name
        return True

    async def get_precompute_row_count(self, table_name: str, days: int, filters=None, params=None):
        del table_name, days, filters, params
        return 1

    async def get_creative_win_breakdown(self, days: int, buyer_id: str | None, limit: int):
        del days, buyer_id, limit
        return [{"creative_id": "cr-1", "reached": 10, "impressions": 2}]

    async def get_creative_count(self, days: int, buyer_id: str | None):
        del days, buyer_id
        return 1

    async def get_creative_bid_totals(self, creative_ids: list[str], days: int, buyer_id: str | None):
        del creative_ids, days, buyer_id
        raise RuntimeError("bid totals failed")


class _RepoBidFilteringFails:
    async def table_exists(self, table_name: str):
        del table_name
        return True

    async def get_bid_filtering_for_creatives(
        self,
        creative_ids: list[str],
        days: int,
        buyer_id: str | None = None,
    ):
        del creative_ids, days, buyer_id
        raise RuntimeError("bid filtering failed")


@pytest.mark.asyncio
async def test_get_valid_billing_ids_for_buyer_logs_warning_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = RtbBidstreamService(repo=_RepoBillingLookupFails())
    with caplog.at_level(logging.WARNING):
        result = await service.get_valid_billing_ids_for_buyer("1487810529")
    assert result == []
    assert "Failed to get billing IDs for buyer scope in RTB service" in caplog.text


@pytest.mark.asyncio
async def test_get_creative_win_performance_logs_warning_when_bid_totals_fail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = RtbBidstreamService(repo=_RepoCreativeBidTotalsFail())
    with caplog.at_level(logging.WARNING):
        result = await service.get_creative_win_performance(days=7, limit=5, buyer_id="1487810529")
    assert result["creatives"][0]["bids"] == 0
    assert "Could not fetch creative bid totals for win route" in caplog.text


@pytest.mark.asyncio
async def test_get_bid_filtering_logs_warning_and_returns_empty_on_repo_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = RtbBidstreamService(repo=_RepoBidFilteringFails())
    with caplog.at_level(logging.WARNING):
        result = await service._get_bid_filtering(["cr-1"], days=7, buyer_id="1487810529")
    assert result == []
    assert "Could not fetch bid filtering data" in caplog.text
