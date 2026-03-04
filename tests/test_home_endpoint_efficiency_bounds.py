"""Regression tests for endpoint-efficiency win-rate bounds and observed QPS.

Incidents:
- delivery_win_rate_pct exceeded 100% (impressions > reached).
- Observed QPS showed "—" when endpoint feed data was transiently missing.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from services.home_analytics_service import HomeAnalyticsService, _safe_rate


# ---------------------------------------------------------------------------
# Stub repos
# ---------------------------------------------------------------------------

class _StubRepoWithObservedQps:
    """Repo where endpoint feed data IS available."""

    async def get_funnel_row(self, _days, _buyer_id):
        return {
            "total_reached": 1000,
            "total_impressions": 1500,  # > reached -> delivery_win_rate was 150%
            "total_bids": 800,
            "total_successful_responses": 600,
            "total_bid_requests": 1200,
        }

    async def get_bidstream_summary(self, _days, _buyer_id):
        return {
            "total_bids": 500,
            "total_bids_in_auction": 400,
            "total_auctions_won": 300,
        }

    async def get_bidder_id_for_buyer(self, _buyer_id):
        return "bidder-1"

    async def get_home_seat_coverage(self, _days, _buyer_id):
        return {"days_with_data": 7, "row_count": 7, "min_date": "2026-02-25", "max_date": "2026-03-03"}

    async def get_bidstream_coverage(self, _days, _buyer_id):
        return {"days_with_data": 7, "row_count": 7, "min_date": "2026-02-25", "max_date": "2026-03-03"}

    async def get_endpoints_for_bidder(self, _bidder_id):
        return [
            {"endpoint_id": "ep-1", "url": "https://example.com/bid", "trading_location": "SG", "maximum_qps": 10000},
        ]

    async def get_observed_endpoint_rows(self, _bidder_id):
        return [
            {"endpoint_id": "ep-1", "url": "https://example.com/bid", "trading_location": "SG", "current_qps": 42.5, "observed_at": datetime.datetime(2026, 3, 3, 12, 0)},
        ]

    def get_window_bounds(self, days):
        return "2026-02-25", "2026-03-03"


class _StubRepoNoObservedQps:
    """Repo where endpoint feed data is NOT available."""

    async def get_funnel_row(self, _days, _buyer_id):
        return {
            "total_reached": 1000,
            "total_impressions": 250,
            "total_bids": 800,
            "total_successful_responses": 600,
            "total_bid_requests": 1200,
        }

    async def get_bidstream_summary(self, _days, _buyer_id):
        return {"total_bids": 0, "total_bids_in_auction": 0, "total_auctions_won": 0}

    async def get_bidder_id_for_buyer(self, _buyer_id):
        return "bidder-1"

    async def get_home_seat_coverage(self, _days, _buyer_id):
        return {"days_with_data": 0, "row_count": 0}

    async def get_bidstream_coverage(self, _days, _buyer_id):
        return {"days_with_data": 0, "row_count": 0}

    async def get_endpoints_for_bidder(self, _bidder_id):
        return []

    async def get_observed_endpoint_rows(self, _bidder_id):
        return []

    def get_window_bounds(self, days):
        return "2026-02-25", "2026-03-03"


async def _stub_status(table_name, _days, filters=None, params=None):
    del filters, params
    return {"table": table_name, "exists": True, "has_rows": True, "row_count": 10}


# ---------------------------------------------------------------------------
# Tests: delivery_win_rate_pct bounded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delivery_win_rate_pct_clamped_when_impressions_exceed_reached(monkeypatch):
    """delivery_win_rate_pct must not exceed 100% even when imps > reached."""
    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", _stub_status)
    service = HomeAnalyticsService(repo=_StubRepoWithObservedQps())
    payload = await service.get_endpoint_efficiency_payload(days=7, buyer_id="buyer-1")

    assert payload["summary"]["delivery_win_rate_pct"] <= 100.0
    assert payload["summary"]["delivery_win_rate_pct"] >= 0.0
    # Also check backward-compat alias
    assert payload["summary"]["win_rate_pct"] <= 100.0


# ---------------------------------------------------------------------------
# Tests: observed_query_rate_qps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_observed_qps_populated_when_feed_data_available(monkeypatch):
    """When endpoint feed has data, observed_query_rate_qps must be a number."""
    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", _stub_status)
    service = HomeAnalyticsService(repo=_StubRepoWithObservedQps())
    payload = await service.get_endpoint_efficiency_payload(days=7, buyer_id="buyer-1")

    assert payload["summary"]["observed_query_rate_qps"] is not None
    assert payload["summary"]["observed_query_rate_qps"] == 42.5
    assert payload["summary"]["endpoint_delivery_state"] == "available"


@pytest.mark.asyncio
async def test_observed_qps_null_when_no_feed_data(monkeypatch):
    """When no feed data, observed_query_rate_qps must be None (not 0)."""
    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", _stub_status)
    service = HomeAnalyticsService(repo=_StubRepoNoObservedQps())
    payload = await service.get_endpoint_efficiency_payload(days=7, buyer_id="buyer-1")

    assert payload["summary"]["observed_query_rate_qps"] is None
    assert payload["summary"]["endpoint_delivery_state"] == "missing"


@pytest.mark.asyncio
async def test_endpoint_delivery_missing_alert_when_no_feed(monkeypatch):
    """ENDPOINT_DELIVERY_MISSING alert fires when observed rows are empty."""
    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", _stub_status)
    service = HomeAnalyticsService(repo=_StubRepoNoObservedQps())
    payload = await service.get_endpoint_efficiency_payload(days=7, buyer_id="buyer-1")

    alert_codes = [a["code"] for a in payload["alerts"]]
    assert "ENDPOINT_DELIVERY_MISSING" in alert_codes


@pytest.mark.asyncio
async def test_no_delivery_missing_alert_when_feed_present(monkeypatch):
    """No ENDPOINT_DELIVERY_MISSING alert when observed data exists."""
    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", _stub_status)
    service = HomeAnalyticsService(repo=_StubRepoWithObservedQps())
    payload = await service.get_endpoint_efficiency_payload(days=7, buyer_id="buyer-1")

    alert_codes = [a["code"] for a in payload["alerts"]]
    assert "ENDPOINT_DELIVERY_MISSING" not in alert_codes


@pytest.mark.asyncio
async def test_endpoint_efficiency_payload_contract(monkeypatch):
    """Key fields exist in the payload for frontend consumption."""
    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", _stub_status)
    service = HomeAnalyticsService(repo=_StubRepoWithObservedQps())
    payload = await service.get_endpoint_efficiency_payload(days=7, buyer_id="buyer-1")

    s = payload["summary"]
    assert "observed_query_rate_qps" in s
    assert "delivery_win_rate_pct" in s
    assert "win_rate_pct" in s
    assert "allocated_qps" in s
    assert "endpoint_delivery_state" in s
    assert "qps_utilization_pct" in s
    assert "allocation_overshoot_x" in s
    assert "endpoint_reconciliation" in payload
    assert "alerts" in payload
    assert "funnel_breakout" in payload
