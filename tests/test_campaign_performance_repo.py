"""Campaign performance aggregation regressions."""

import pytest

import storage.postgres_repositories.campaign_repo as campaign_repo
from storage.postgres_repositories.campaign_repo import CampaignRepository


@pytest.mark.asyncio
async def test_get_campaign_performance_uses_live_metric_tables(monkeypatch) -> None:
    calls = []

    async def fake_query_one(sql: str, params: tuple):
        calls.append((sql, params))
        return {
            "impressions": 1000,
            "clicks": 25,
            "spend_micros": 2_500_000,
            "queries": 10_000,
        }

    monkeypatch.setattr(campaign_repo, "pg_query_one", fake_query_one)

    result = await CampaignRepository().get_campaign_performance(
        "camp-1",
        days=7,
        buyer_id="buyer-1",
    )

    sql, params = calls[0]
    assert "campaign_daily_summary" not in sql
    assert "rtb_daily" in sql
    assert "config_creative_daily" in sql
    assert "performance_metrics" in sql
    assert params == ("camp-1", "buyer-1", 7, 7, 7)
    assert result["spend_micros"] == 2_500_000
    assert result["spend"] == 2.5
    assert result["win_rate"] == 10.0
    assert result["ctr"] == 2.5
    assert result["cpm"] == 2.5


@pytest.mark.asyncio
async def test_get_campaign_performance_returns_zero_shape(monkeypatch) -> None:
    async def fake_query_one(_sql: str, _params: tuple):
        return None

    monkeypatch.setattr(campaign_repo, "pg_query_one", fake_query_one)

    result = await CampaignRepository().get_campaign_performance("camp-1")

    assert result == {
        "impressions": 0,
        "clicks": 0,
        "spend": 0,
        "spend_micros": 0,
        "queries": 0,
        "win_rate": None,
        "ctr": None,
        "cpm": None,
    }
