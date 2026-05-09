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


@pytest.mark.asyncio
async def test_list_campaigns_filters_to_buyer_creative_membership(monkeypatch) -> None:
    calls = []

    async def fake_query(sql: str, params: tuple):
        calls.append((sql, params))
        return []

    monkeypatch.setattr(campaign_repo, "pg_query", fake_query)

    await CampaignRepository().list_campaigns(
        status="active",
        buyer_id="buyer-1",
        limit=25,
        offset=5,
    )

    sql, params = calls[0]
    assert "EXISTS" in sql
    assert "JOIN creatives cr ON cr.id = cc.creative_id" in sql
    assert "AND cr.buyer_id = %s" in sql
    assert params == ("active", "buyer-1", 25, 5)


@pytest.mark.asyncio
async def test_find_existing_campaign_for_creatives_matches_single_destination_identity(monkeypatch) -> None:
    calls = []

    async def fake_query_one(sql: str, params: tuple):
        calls.append((sql, params))
        return {"campaign_id": "existing-campaign"}

    monkeypatch.setattr(campaign_repo, "pg_query_one", fake_query_one)

    result = await CampaignRepository().find_existing_campaign_for_creatives(
        ["creative-1", "creative-2"],
        buyer_id="buyer-1",
    )

    sql, params = calls[0]
    assert "single_identity.identity_count = 1" in sql
    assert "single_identity.identified_count = single_identity.total_count" in sql
    assert "single_identity.buyer_count = 1" in sql
    assert "display:" in sql
    assert sql.count("%s::text IS NULL") == 2
    assert params == (["creative-1", "creative-2"], "buyer-1", "buyer-1", "buyer-1", "buyer-1")
    assert result == "existing-campaign"


@pytest.mark.asyncio
async def test_find_existing_campaign_for_creatives_ignores_empty_requests(monkeypatch) -> None:
    async def fake_query_one(_sql: str, _params: tuple):
        raise AssertionError("empty creative requests should not hit the database")

    monkeypatch.setattr(campaign_repo, "pg_query_one", fake_query_one)

    result = await CampaignRepository().find_existing_campaign_for_creatives([])

    assert result is None


@pytest.mark.asyncio
async def test_assign_creatives_batch_uses_single_bulk_statement(monkeypatch) -> None:
    calls = []

    async def fake_execute(sql: str, params: tuple):
        calls.append((sql, params))
        return 2

    monkeypatch.setattr(campaign_repo, "pg_execute", fake_execute)

    result = await CampaignRepository().assign_creatives_batch(
        ["creative-1", "creative-2", "creative-1"],
        "campaign-1",
        assigned_by="user",
        manually_assigned=True,
    )

    assert result == 2
    assert len(calls) == 1
    sql, params = calls[0]
    assert "unnest(%s::text[])" in sql
    assert params == (["creative-1", "creative-2"], "campaign-1", True, "user")
