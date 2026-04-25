"""Regression tests for buyer-scoped legacy creative performance summaries."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from storage.postgres_store import PostgresStore


@pytest.mark.asyncio
async def test_get_creative_performance_summary_includes_buyer_filter_when_provided() -> None:
    with patch(
        "storage.postgres_store.pg_query_one",
        new_callable=AsyncMock,
        return_value={
            "total_impressions": 0,
            "total_spend_micros": 0,
            "days_with_data": 0,
            "earliest_date": None,
            "latest_date": None,
        },
    ) as mock_query:
        store = PostgresStore()
        await store.get_creative_performance_summary(
            "creative-1",
            days=7,
            buyer_id="buyer-1",
        )

    sql, params = mock_query.call_args[0]
    assert "buyer_account_id = %s" in sql
    assert params == ("creative-1", 7, "buyer-1")


@pytest.mark.asyncio
async def test_get_creative_performance_summary_omits_buyer_filter_when_absent() -> None:
    with patch(
        "storage.postgres_store.pg_query_one",
        new_callable=AsyncMock,
        return_value={
            "total_impressions": 0,
            "total_spend_micros": 0,
            "days_with_data": 0,
            "earliest_date": None,
            "latest_date": None,
        },
    ) as mock_query:
        store = PostgresStore()
        await store.get_creative_performance_summary("creative-1", days=7)

    sql, params = mock_query.call_args[0]
    assert "buyer_account_id = %s" not in sql
    assert params == ("creative-1", 7)
