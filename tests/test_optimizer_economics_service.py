"""Tests for optimizer economics service."""

from __future__ import annotations

import pytest

from services.optimizer_economics_service import OptimizerEconomicsService


@pytest.mark.asyncio
async def test_get_effective_cpm_with_hosting_cost(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        if "FROM rtb_daily" in sql:
            return {"spend_micros": 2_500_000, "impressions": 500_000}
        if "FROM system_settings" in sql:
            return {"value": "3000"}
        return None

    monkeypatch.setattr("services.optimizer_economics_service.pg_query_one", _stub_query_one)
    service = OptimizerEconomicsService()
    payload = await service.get_effective_cpm(
        buyer_id="1111111111",
        start_date="2026-02-20",
        end_date="2026-02-26",
    )

    assert payload["buyer_id"] == "1111111111"
    assert payload["impressions"] == 500_000
    assert payload["media_spend_usd"] == 2.5
    assert payload["monthly_hosting_cost_usd"] == 3000.0
    assert payload["cost_context_ready"] is True
    assert payload["media_cpm_usd"] == 0.005
    assert payload["infra_cpm_usd"] is not None
    assert payload["effective_cpm_usd"] is not None


@pytest.mark.asyncio
async def test_get_effective_cpm_without_hosting_cost(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        if "FROM rtb_daily" in sql:
            return {"spend_micros": 1_000_000, "impressions": 100_000}
        if "FROM system_settings" in sql:
            return None
        return None

    monkeypatch.setattr("services.optimizer_economics_service.pg_query_one", _stub_query_one)
    service = OptimizerEconomicsService()
    payload = await service.get_effective_cpm(
        buyer_id="1111111111",
        days=14,
    )

    assert payload["media_spend_usd"] == 1.0
    assert payload["monthly_hosting_cost_usd"] is None
    assert payload["infra_cpm_usd"] is None
    assert payload["effective_cpm_usd"] is None
    assert payload["cost_context_ready"] is False


@pytest.mark.asyncio
async def test_get_assumed_value_returns_score(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        if "SUM(spend_micros)" in sql and "FROM rtb_daily" in sql and "reached_queries" in sql:
            return {
                "spend_micros": 14_000_000,
                "impressions": 2_000_000,
                "clicks": 40_000,
                "reached_queries": 5_000_000,
                "bids_in_auction": 1_000_000,
                "auctions_won": 200_000,
            }
        if "recent_spend_micros" in sql:
            return {
                "recent_spend_micros": 8_000_000,
                "previous_spend_micros": 6_000_000,
            }
        if "MIN(metric_date)" in sql:
            return {"first_metric_date": "2025-08-01"}
        if "FROM rtb_quality" in sql:
            return {
                "viewable_impressions": 500_000,
                "measurable_impressions": 700_000,
            }
        return None

    monkeypatch.setattr("services.optimizer_economics_service.pg_query_one", _stub_query_one)
    service = OptimizerEconomicsService()
    payload = await service.get_assumed_value(
        buyer_id="1111111111",
        start_date="2026-02-15",
        end_date="2026-02-28",
    )

    assert payload["buyer_id"] == "1111111111"
    assert payload["days"] == 14
    assert 0.0 <= payload["assumed_value_score"] <= 1.0
    assert payload["metrics"]["impressions"] == 2_000_000
    assert payload["metrics"]["bid_rate"] == 0.2
    assert payload["metrics"]["win_rate"] == 0.2
    assert payload["components"]["viewability_score"] > 0.0


@pytest.mark.asyncio
async def test_get_efficiency_summary_returns_metrics(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        if "COALESCE(SUM(bid_requests), 0)::bigint AS bid_requests" in sql:
            return {
                "spend_micros": 14_000_000,
                "impressions": 2_000_000,
                "bid_requests": 4_000_000,
                "reached_queries": 5_000_000,
            }
        return None

    monkeypatch.setattr("services.optimizer_economics_service.pg_query_one", _stub_query_one)
    service = OptimizerEconomicsService()

    async def _stub_assumed_value(**kwargs):
        return {"assumed_value_score": 0.75}

    monkeypatch.setattr(service, "get_assumed_value", _stub_assumed_value)
    payload = await service.get_efficiency_summary(
        buyer_id="1111111111",
        start_date="2026-02-15",
        end_date="2026-02-28",
    )

    assert payload["buyer_id"] == "1111111111"
    assert payload["days"] == 14
    assert payload["qps_efficiency"] == 0.5
    assert payload["avg_allocated_qps"] == 4.133598
    assert payload["assumed_value_score"] == 0.75
    assert payload["assumed_value_per_qps"] == 0.18144
    assert payload["has_bid_request_data"] is True
    assert payload["has_reached_query_data"] is True


@pytest.mark.asyncio
async def test_get_efficiency_summary_handles_missing_inputs(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        if "COALESCE(SUM(bid_requests), 0)::bigint AS bid_requests" in sql:
            return {
                "spend_micros": 500_000,
                "impressions": 100_000,
                "bid_requests": 0,
                "reached_queries": 0,
            }
        return None

    monkeypatch.setattr("services.optimizer_economics_service.pg_query_one", _stub_query_one)
    service = OptimizerEconomicsService()

    async def _stub_assumed_value(**kwargs):
        return {"assumed_value_score": 0.5}

    monkeypatch.setattr(service, "get_assumed_value", _stub_assumed_value)
    payload = await service.get_efficiency_summary(
        buyer_id="1111111111",
        days=14,
    )

    assert payload["qps_efficiency"] is None
    assert payload["avg_allocated_qps"] is None
    assert payload["assumed_value_per_qps"] is None
    assert payload["has_bid_request_data"] is False
    assert payload["has_reached_query_data"] is False
