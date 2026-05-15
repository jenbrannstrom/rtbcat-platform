"""Regression tests for spend-sorted creative list queries."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from storage.postgres_store import PostgresStore


@pytest.mark.asyncio
async def test_metric_sort_query_keeps_filters_and_uses_left_join() -> None:
    row = {
        "id": "creative-zero",
        "name": "Creative Zero",
        "format": "HTML",
        "buyer_id": "buyer-1",
        "approval_status": "APPROVED",
    }

    with patch(
        "storage.postgres_store.pg_query",
        new_callable=AsyncMock,
        return_value=[row],
    ) as mock_query:
        store = PostgresStore()
        creatives = await store.list_creatives(
            limit=50,
            offset=0,
            format="HTML",
            campaign_id="camp-1",
            cluster_id="cluster-1",
            buyer_id="buyer-1",
            approval_status="APPROVED",
            search="creative-zero",
            include_raw_data=True,
            sort_by="spend",
            sort_days=7,
        )

    assert [creative.id for creative in creatives] == ["creative-zero"]
    sql, params = mock_query.call_args[0]
    assert "WITH perf AS" in sql
    assert "FROM config_creative_daily d" in sql
    assert "FROM rtb_daily d" not in sql
    assert "LEFT JOIN perf p ON p.creative_id = c.id" in sql
    assert "c.format = %s" in sql
    assert "c.campaign_id = %s" in sql
    assert "c.cluster_id = %s" in sql
    assert "c.buyer_id = %s" in sql
    assert "COALESCE(c.name, '') ILIKE %s" in sql
    assert "ORDER BY COALESCE(p._sort_val, 0) DESC" in sql
    assert params[0] == 7
    assert params.count("buyer-1") == 2


@pytest.mark.asyncio
async def test_metric_sort_query_supports_not_approved_filter() -> None:
    with patch(
        "storage.postgres_store.pg_query",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_query:
        store = PostgresStore()
        await store.list_creatives(
            buyer_id="buyer-1",
            approval_status="NOT_APPROVED",
            sort_by="spend",
            sort_days=7,
        )

    sql, _params = mock_query.call_args[0]
    assert "(c.approval_status IS NULL OR c.approval_status != 'APPROVED')" in sql
    assert "FROM config_creative_daily d" in sql


@pytest.mark.asyncio
async def test_click_metric_sort_uses_raw_click_source() -> None:
    with patch(
        "storage.postgres_store.pg_query",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_query:
        store = PostgresStore()
        await store.list_creatives(
            buyer_id="buyer-1",
            sort_by="clicks",
            sort_days=7,
        )

    sql, _params = mock_query.call_args[0]
    assert "FROM rtb_daily d" in sql
