"""Regression tests for geo/publisher win_rate bounds in home analytics.

Incident: Geo QPS page showed win_rate > 100% because the old formula
used impressions/reached — but impressions can exceed reached_queries
(multiple impressions per query).  Fix: prefer auctions_won/bids,
fallback to imps/reached, always clamp to [0, 100].
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from services.home_analytics_service import HomeAnalyticsService, _safe_rate


# ---------------------------------------------------------------------------
# _safe_rate unit tests
# ---------------------------------------------------------------------------

class TestSafeRate:
    def test_normal_rate(self):
        assert _safe_rate(25, 100) == 25.0

    def test_zero_denominator(self):
        assert _safe_rate(10, 0) == 0.0

    def test_negative_denominator(self):
        assert _safe_rate(10, -5) == 0.0

    def test_negative_numerator(self):
        assert _safe_rate(-10, 100) == 0.0

    def test_clamps_at_100(self):
        # impressions > reached is the exact incident scenario
        assert _safe_rate(200, 100) == 100.0

    def test_string_inputs(self):
        assert _safe_rate("25", "100") == 25.0

    def test_decimal_inputs(self):
        assert _safe_rate(Decimal("25"), Decimal("100")) == 25.0

    def test_none_numerator(self):
        assert _safe_rate(None, 100) == 0.0

    def test_none_denominator(self):
        assert _safe_rate(10, None) == 0.0

    def test_both_none(self):
        assert _safe_rate(None, None) == 0.0

    def test_nan_string(self):
        assert _safe_rate("abc", 100) == 0.0

    def test_empty_string(self):
        assert _safe_rate("", 100) == 0.0

    def test_result_is_float(self):
        result = _safe_rate(Decimal("50"), Decimal("200"))
        assert isinstance(result, float)

    def test_very_small_denominator(self):
        # Should not produce Infinity
        result = _safe_rate(1, 0.0000001)
        assert result == 100.0  # clamped

    def test_zero_numerator(self):
        assert _safe_rate(0, 100) == 0.0


# ---------------------------------------------------------------------------
# Integration: geo rows never exceed 100% win_rate
# ---------------------------------------------------------------------------

class _StubRepoHighImpressions:
    """Simulates DB rows where impressions > reached (the incident trigger)."""

    async def get_funnel_row(self, _days, _buyer_id):
        return {
            "total_reached": 1000,
            "total_impressions": 1500,  # > reached!
            "total_bids": 800,
            "total_successful_responses": 600,
            "total_bid_requests": 1200,
        }

    async def get_publisher_rows(self, _days, _buyer_id, _limit):
        return [
            {
                "publisher_id": "pub-1",
                "publisher_name": "High Imps Pub",
                "reached": 400,
                "impressions": 600,  # > reached!
                "total_bids": 350,
                "auctions_won": 200,
                "total_publishers": 1,
            }
        ]

    async def get_geo_rows(self, _days, _buyer_id, _limit):
        return [
            {
                "country": "US",
                "reached": 600,
                "impressions": 900,  # > reached!
                "total_bids": 450,
                "auctions_won": 300,
                "total_countries": 2,
            },
            {
                "country": "DE",
                "reached": 400,
                "impressions": 600,  # > reached!
                "total_bids": 0,  # no bids -> fallback formula
                "auctions_won": 0,
                "total_countries": 2,
            },
        ]


class _StubRepoStringValues:
    """Simulates DB rows with string/Decimal values (Postgres driver quirk)."""

    async def get_funnel_row(self, _days, _buyer_id):
        return {
            "total_reached": Decimal("1000"),
            "total_impressions": Decimal("250"),
            "total_bids": Decimal("700"),
            "total_successful_responses": Decimal("600"),
            "total_bid_requests": Decimal("1200"),
        }

    async def get_publisher_rows(self, _days, _buyer_id, _limit):
        return [
            {
                "publisher_id": "pub-1",
                "publisher_name": "Decimal Pub",
                "reached": Decimal("400"),
                "impressions": Decimal("100"),
                "total_bids": Decimal("250"),
                "auctions_won": Decimal("90"),
                "total_publishers": 1,
            }
        ]

    async def get_geo_rows(self, _days, _buyer_id, _limit):
        return [
            {
                "country": "JP",
                "reached": Decimal("800"),
                "impressions": Decimal("200"),
                "total_bids": Decimal("600"),
                "auctions_won": Decimal("180"),
                "total_countries": 1,
            }
        ]


class _StubRepoNullValues:
    """Simulates DB rows with NULL values."""

    async def get_funnel_row(self, _days, _buyer_id):
        return {
            "total_reached": None,
            "total_impressions": None,
            "total_bids": None,
            "total_successful_responses": None,
            "total_bid_requests": None,
        }

    async def get_publisher_rows(self, _days, _buyer_id, _limit):
        return [
            {
                "publisher_id": "pub-1",
                "publisher_name": None,
                "reached": None,
                "impressions": None,
                "total_bids": None,
                "auctions_won": None,
                "total_publishers": 0,
            }
        ]

    async def get_geo_rows(self, _days, _buyer_id, _limit):
        return [
            {
                "country": "XX",
                "reached": None,
                "impressions": None,
                "total_bids": None,
                "auctions_won": None,
                "total_countries": 0,
            }
        ]


async def _stub_status(table_name, _days, filters=None, params=None):
    del filters, params
    return {"table": table_name, "exists": True, "has_rows": True, "row_count": 10}


@pytest.mark.asyncio
async def test_geo_win_rate_clamped_when_impressions_exceed_reached(monkeypatch):
    """The exact incident: impressions > reached must not produce >100%."""
    monkeypatch.setattr(
        "services.home_analytics_service._get_precompute_status", _stub_status
    )
    service = HomeAnalyticsService(repo=_StubRepoHighImpressions())
    payload = await service.get_funnel_payload(days=7, buyer_id=None, limit=30)

    for geo in payload["geos"]:
        assert 0 <= geo["win_rate"] <= 100, (
            f"geo {geo['country']} win_rate={geo['win_rate']} out of bounds"
        )

    # US: has bids, so win_rate = auctions_won/bids = 300/450 * 100 ≈ 66.67
    us_geo = next(g for g in payload["geos"] if g["country"] == "US")
    assert us_geo["win_rate"] == pytest.approx(66.67, abs=0.01)

    # DE: no bids, fallback to imps/reached = 600/400 = 150% → clamped to 100
    de_geo = next(g for g in payload["geos"] if g["country"] == "DE")
    assert de_geo["win_rate"] == 100.0


@pytest.mark.asyncio
async def test_publisher_win_rate_clamped_when_impressions_exceed_reached(monkeypatch):
    monkeypatch.setattr(
        "services.home_analytics_service._get_precompute_status", _stub_status
    )
    service = HomeAnalyticsService(repo=_StubRepoHighImpressions())
    payload = await service.get_funnel_payload(days=7, buyer_id=None, limit=30)

    for pub in payload["publishers"]:
        assert 0 <= pub["win_rate"] <= 100, (
            f"publisher {pub['publisher_id']} win_rate={pub['win_rate']} out of bounds"
        )

    # pub-1: has bids=350, wins=200 → 200/350*100 ≈ 57.14
    pub = payload["publishers"][0]
    assert pub["win_rate"] == pytest.approx(57.14, abs=0.01)


@pytest.mark.asyncio
async def test_funnel_win_rate_clamped(monkeypatch):
    monkeypatch.setattr(
        "services.home_analytics_service._get_precompute_status", _stub_status
    )
    service = HomeAnalyticsService(repo=_StubRepoHighImpressions())
    payload = await service.get_funnel_payload(days=7, buyer_id=None, limit=30)

    assert 0 <= payload["funnel"]["win_rate"] <= 100


@pytest.mark.asyncio
async def test_geo_win_rate_with_decimal_inputs(monkeypatch):
    """Postgres can return Decimal types; must not crash."""
    monkeypatch.setattr(
        "services.home_analytics_service._get_precompute_status", _stub_status
    )
    service = HomeAnalyticsService(repo=_StubRepoStringValues())
    payload = await service.get_funnel_payload(days=7, buyer_id=None, limit=30)

    for geo in payload["geos"]:
        assert isinstance(geo["win_rate"], float)
        assert 0 <= geo["win_rate"] <= 100

    # JP: wins=180, bids=600 → 30.0%
    jp = payload["geos"][0]
    assert jp["win_rate"] == 30.0


@pytest.mark.asyncio
async def test_geo_win_rate_with_null_inputs(monkeypatch):
    """All-null rows must produce 0% win_rate, not crash."""
    monkeypatch.setattr(
        "services.home_analytics_service._get_precompute_status", _stub_status
    )
    service = HomeAnalyticsService(repo=_StubRepoNullValues())
    payload = await service.get_funnel_payload(days=7, buyer_id=None, limit=30)

    for geo in payload["geos"]:
        assert geo["win_rate"] == 0
    for pub in payload["publishers"]:
        assert pub["win_rate"] == 0
    assert payload["funnel"]["win_rate"] == 0


@pytest.mark.asyncio
async def test_payload_contract_stable(monkeypatch):
    """Key name is still 'win_rate', not renamed."""
    monkeypatch.setattr(
        "services.home_analytics_service._get_precompute_status", _stub_status
    )
    service = HomeAnalyticsService(repo=_StubRepoHighImpressions())
    payload = await service.get_funnel_payload(days=7, buyer_id=None, limit=30)

    assert "win_rate" in payload["funnel"]
    assert "win_rate" in payload["geos"][0]
    assert "win_rate" in payload["publishers"][0]
