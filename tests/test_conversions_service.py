"""Tests for conversion aggregate service."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from services.conversions_service import ConversionsService


@pytest.mark.asyncio
async def test_refresh_aggregates_applies_buyer_filter(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, tuple]] = []

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        calls.append((sql, params))
        if sql.lstrip().startswith("DELETE"):
            return 4
        return 9

    monkeypatch.setattr("services.conversions_service.pg_execute", _stub_execute)
    service = ConversionsService()

    payload = await service.refresh_aggregates(
        days=7,
        start_date="2026-02-20",
        end_date="2026-02-26",
        buyer_id="1111111111",
    )

    assert payload["start_date"] == "2026-02-20"
    assert payload["end_date"] == "2026-02-26"
    assert payload["buyer_id"] == "1111111111"
    assert payload["deleted_rows"] == 4
    assert payload["upserted_rows"] == 9

    assert len(calls) == 2
    delete_sql, delete_params = calls[0]
    insert_sql, insert_params = calls[1]
    assert "DELETE FROM conversion_aggregates_daily" in delete_sql
    assert "AND buyer_id = %s" in delete_sql
    assert delete_params == ("2026-02-20", "2026-02-26", "1111111111")
    assert "FROM conversion_events" in insert_sql
    assert "FROM rtb_daily" in insert_sql
    assert insert_params[0:3] == ("2026-02-20", "2026-02-26", "1111111111")


@pytest.mark.asyncio
async def test_get_aggregates_applies_filters_and_shapes_response(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, tuple] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["rows_sql"] = (sql, params)
        return [
            {
                "agg_date": date(2026, 2, 27),
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "country": "US",
                "publisher_id": "pub-1",
                "creative_id": "cr-1",
                "app_id": "com.example.app",
                "source_type": "appsflyer",
                "event_type": "first_deposit",
                "event_count": 3,
                "event_value_total": 120.0,
                "impressions": 1000,
                "clicks": 40,
                "spend_usd": 60.0,
                "cost_per_event": 20.0,
                "event_rate_pct": 7.5,
                "created_at": datetime(2026, 2, 27, 0, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 27, 1, 0, tzinfo=timezone.utc),
            }
        ]

    async def _stub_query_one(sql: str, params: tuple = ()):
        captured["count_sql"] = (sql, params)
        return {"total_rows": 1}

    monkeypatch.setattr("services.conversions_service.pg_query", _stub_query)
    monkeypatch.setattr("services.conversions_service.pg_query_one", _stub_query_one)
    service = ConversionsService()

    payload = await service.get_aggregates(
        days=14,
        buyer_id="1111111111",
        billing_id="cfg-1",
        source_type="appsflyer",
        event_type="first_deposit",
        limit=20,
        offset=0,
    )

    assert payload["meta"]["total"] == 1
    assert payload["meta"]["returned"] == 1
    assert payload["meta"]["limit"] == 20
    assert payload["rows"][0]["event_count"] == 3
    assert payload["rows"][0]["event_type"] == "first_deposit"

    rows_sql, rows_params = captured["rows_sql"]
    assert "buyer_id = %s" in rows_sql
    assert "billing_id = %s" in rows_sql
    assert "source_type = %s" in rows_sql
    assert "event_type = %s" in rows_sql
    assert rows_params[-2:] == (20, 0)


@pytest.mark.asyncio
async def test_get_health_marks_stale_when_lag_high(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        if "FROM conversion_events" in sql:
            return {
                "total_events": 10,
                "max_event_ts": datetime(2026, 2, 20, 0, 0, tzinfo=timezone.utc),
                "last_ingested_at": datetime(2026, 2, 20, 1, 0, tzinfo=timezone.utc),
            }
        return {
            "total_rows": 8,
            "max_agg_date": date(2026, 2, 20),
            "last_aggregated_at": datetime(2026, 2, 20, 2, 0, tzinfo=timezone.utc),
        }

    monkeypatch.setattr("services.conversions_service.pg_query_one", _stub_query_one)
    service = ConversionsService()

    payload = await service.get_health(buyer_id="1111111111")

    assert payload["buyer_id"] == "1111111111"
    assert payload["state"] in {"degraded", "stale"}
    assert payload["ingestion"]["total_events"] == 10
    assert payload["aggregation"]["total_rows"] == 8
