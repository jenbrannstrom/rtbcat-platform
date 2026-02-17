"""Unit tests for B3 metric-normalization changes."""

import pytest

from analytics import cost_estimator
from analytics.fraud_analyzer import FraudAnalyzer


@pytest.mark.asyncio
async def test_resolve_request_cost_prefers_account_query_cost(monkeypatch):
    """Account spend/reached_queries should drive request-cost estimation."""

    async def fake_db_query_one(_query, _params):
        return {
            "spend_micros": 2_500_000,  # $2.50
            "reached_queries": 500_000,
            "impressions": 100_000,
        }

    monkeypatch.setattr(cost_estimator, "db_query_one", fake_db_query_one)

    cost = await cost_estimator.resolve_request_cost_per_1000(days=7, buyer_id="buyer-1")
    assert cost == pytest.approx(0.005, rel=1e-6)


@pytest.mark.asyncio
async def test_resolve_request_cost_falls_back_to_format_profile(monkeypatch):
    """Missing spend/query data should use deterministic format fallback."""

    async def fake_db_query_one(_query, _params):
        return {
            "spend_micros": 0,
            "reached_queries": 0,
            "impressions": 0,
        }

    monkeypatch.setattr(cost_estimator, "db_query_one", fake_db_query_one)

    banner_cost = await cost_estimator.resolve_request_cost_per_1000(days=7, format_hint="banner")
    video_cost = await cost_estimator.resolve_request_cost_per_1000(days=7, format_hint="video")

    assert banner_cost == pytest.approx(0.002, rel=1e-6)
    assert video_cost == pytest.approx(0.006, rel=1e-6)
    assert video_cost > banner_cost


def test_fraud_threshold_is_format_aware():
    """Fraud analyzer should provide different CTR thresholds by format."""
    assert FraudAnalyzer._high_ctr_threshold_for_format("BANNER") == pytest.approx(0.10)
    assert FraudAnalyzer._high_ctr_threshold_for_format("VIDEO") == pytest.approx(0.20)
    assert FraudAnalyzer._high_ctr_threshold_for_format("NATIVE") == pytest.approx(0.12)
    assert FraudAnalyzer._high_ctr_threshold_for_format("HTML") == pytest.approx(0.10)
    assert FraudAnalyzer._high_ctr_threshold_for_format("unknown") == pytest.approx(0.10)


@pytest.mark.asyncio
async def test_click_fraud_detection_uses_format_thresholds(monkeypatch):
    """Identical CTR should trip banner threshold but not video threshold."""

    async def fake_db_query(_query, _params):
        return [
            {
                "source": "banner.example",
                "creative_format": "BANNER",
                "impressions": 10_000,
                "clicks": 1_500,  # 15%
                "spend_micros": 10_000_000,
                "creative_count": 1,
            },
            {
                "source": "video.example",
                "creative_format": "VIDEO",
                "impressions": 10_000,
                "clicks": 1_500,  # 15%
                "spend_micros": 10_000_000,
                "creative_count": 1,
            },
        ]

    from analytics import fraud_analyzer as fraud_module

    monkeypatch.setattr(fraud_module, "db_query", fake_db_query)

    analyzer = FraudAnalyzer()
    recs = await analyzer._check_click_fraud(days=7)

    assert len(recs) == 1
    assert "banner.example" in recs[0].title.lower()
