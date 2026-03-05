"""Tests for creative performance summary clicks parity fix.

Validates that:
- get_creative_summaries returns real clicks from rtb_daily
- Derived metrics (CPM, CPC, CTR) are correctly computed
- Buyer scoping is applied when filter is provided
- Empty results handled gracefully
"""

from unittest.mock import AsyncMock, patch

import pytest

from storage.postgres_repositories.creative_performance_repo import CreativePerformanceRepository


@pytest.fixture
def repo():
    return CreativePerformanceRepository()


@pytest.mark.asyncio
async def test_empty_creative_ids_returns_empty(repo):
    result = await repo.get_creative_summaries([], days=7)
    assert result == {}


@pytest.mark.asyncio
async def test_summaries_with_clicks(repo):
    """Non-zero clicks returns correct CTR and CPC."""
    mock_rows = [
        {
            "creative_id": "12345",
            "total_impressions": 10000,
            "total_clicks": 50,
            "total_spend_micros": 5000000,  # $5.00
            "days_with_data": 7,
            "earliest_date": "2026-02-18",
            "latest_date": "2026-02-24",
        }
    ]

    with patch(
        "storage.postgres_repositories.creative_performance_repo.pg_query",
        new_callable=AsyncMock,
        return_value=mock_rows,
    ):
        result = await repo.get_creative_summaries(["12345"], days=7)

    assert "12345" in result
    s = result["12345"]
    assert s["total_clicks"] == 50
    assert s["clicks_available"] is True
    assert s["metric_source"] == "rtb_daily"
    # CPM = (5000000 / 10000) * 1000 = 500000
    assert s["avg_cpm_micros"] == 500000
    # CPC = 5000000 / 50 = 100000
    assert s["avg_cpc_micros"] == 100000
    # CTR = (50 / 10000) * 100 = 0.5
    assert s["ctr_percent"] == 0.5


@pytest.mark.asyncio
async def test_summaries_with_zero_clicks(repo):
    """Zero clicks returns CPC=None, CTR=0."""
    mock_rows = [
        {
            "creative_id": "67890",
            "total_impressions": 5000,
            "total_clicks": 0,
            "total_spend_micros": 2000000,
            "days_with_data": 3,
            "earliest_date": "2026-02-22",
            "latest_date": "2026-02-24",
        }
    ]

    with patch(
        "storage.postgres_repositories.creative_performance_repo.pg_query",
        new_callable=AsyncMock,
        return_value=mock_rows,
    ):
        result = await repo.get_creative_summaries(["67890"], days=7)

    s = result["67890"]
    assert s["total_clicks"] == 0
    assert s["avg_cpc_micros"] is None  # Can't compute CPC with 0 clicks
    assert s["ctr_percent"] == 0.0  # CTR is 0 when clicks are 0 but impressions > 0
    assert s["clicks_available"] is True  # Clicks ARE available, they're just 0


@pytest.mark.asyncio
async def test_summaries_buyer_scoping(repo):
    """Verify buyer_id_filter is passed to SQL query."""
    with patch(
        "storage.postgres_repositories.creative_performance_repo.pg_query",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_query:
        await repo.get_creative_summaries(
            ["12345"], days=7, buyer_id_filter="2222222222"
        )

    # Verify the query was called with buyer filter in params
    call_args = mock_query.call_args
    sql = call_args[0][0]
    params = call_args[0][1]
    assert "buyer_account_id" in sql
    assert "2222222222" in params


@pytest.mark.asyncio
async def test_summaries_no_buyer_filter(repo):
    """Without buyer filter, query should not include buyer_account_id clause."""
    with patch(
        "storage.postgres_repositories.creative_performance_repo.pg_query",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_query:
        await repo.get_creative_summaries(["12345"], days=7)

    sql = mock_query.call_args[0][0]
    assert "buyer_account_id" not in sql


@pytest.mark.asyncio
async def test_batch_multiple_creatives(repo):
    """Batch query returns correct mapping for multiple creatives."""
    mock_rows = [
        {
            "creative_id": "aaa",
            "total_impressions": 1000,
            "total_clicks": 10,
            "total_spend_micros": 1000000,
            "days_with_data": 5,
            "earliest_date": "2026-02-20",
            "latest_date": "2026-02-24",
        },
        {
            "creative_id": "bbb",
            "total_impressions": 500,
            "total_clicks": 0,
            "total_spend_micros": 500000,
            "days_with_data": 3,
            "earliest_date": "2026-02-22",
            "latest_date": "2026-02-24",
        },
    ]

    with patch(
        "storage.postgres_repositories.creative_performance_repo.pg_query",
        new_callable=AsyncMock,
        return_value=mock_rows,
    ):
        result = await repo.get_creative_summaries(["aaa", "bbb", "ccc"], days=7)

    assert len(result) == 2  # "ccc" not in rtb_daily
    assert result["aaa"]["total_clicks"] == 10
    assert result["bbb"]["total_clicks"] == 0
    assert "ccc" not in result
