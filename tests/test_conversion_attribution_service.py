"""Tests for conversion attribution service."""

from __future__ import annotations

import asyncio

from services.conversion_attribution_service import ConversionAttributionService


async def _unused_async(*args, **kwargs):  # pragma: no cover
    raise AssertionError("unexpected call")


def test_refresh_joins_returns_counts_and_summary(monkeypatch):
    service = ConversionAttributionService()
    execute_calls: list[tuple[str, tuple]] = []

    execute_results = iter([2, 6, 6])

    async def _stub_execute(sql: str, params: tuple = ()):
        execute_calls.append((sql, params))
        return next(execute_results)

    async def _stub_query_one(sql: str, params: tuple = ()):
        assert "FROM conversion_events" in sql
        return {"total_events": 6}

    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM conversion_attribution_joins" in sql
        return [
            {
                "join_mode": "exact_clickid",
                "join_status": "blocked",
                "row_count": 4,
                "avg_confidence": 0.0,
                "high_confidence_count": 0,
            },
            {
                "join_mode": "fallback_creative_time",
                "join_status": "matched",
                "row_count": 3,
                "avg_confidence": 0.83,
                "high_confidence_count": 2,
            },
            {
                "join_mode": "fallback_creative_time",
                "join_status": "unmatched",
                "row_count": 3,
                "avg_confidence": 0.0,
                "high_confidence_count": 0,
            },
        ]

    monkeypatch.setattr("services.conversion_attribution_service.pg_execute", _stub_execute)
    monkeypatch.setattr("services.conversion_attribution_service.pg_query_one", _stub_query_one)
    monkeypatch.setattr("services.conversion_attribution_service.pg_query", _stub_query)

    result = asyncio.run(
        service.refresh_joins(
            buyer_id="1111111111",
            source_type="appsflyer",
            days=14,
            fallback_window_days=2,
        )
    )

    assert result["deleted_rows"] == 2
    assert result["exact_rows_upserted"] == 6
    assert result["fallback_rows_upserted"] == 6
    assert result["fallback_window_days"] == 2
    assert result["summary"]["total_events"] == 6
    assert len(result["summary"]["modes"]) == 2
    assert len(execute_calls) == 3
    assert "exact_clickid" in execute_calls[1][0]
    assert "fallback_creative_time" in execute_calls[2][0]


def test_list_joins_normalizes_rows_and_meta(monkeypatch):
    service = ConversionAttributionService()

    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM conversion_attribution_joins" in sql
        return [
            {
                "id": 9,
                "conversion_event_id": 44,
                "conversion_event_ts": "2026-03-01T00:00:00+00:00",
                "buyer_id": "1111111111",
                "source_type": "appsflyer",
                "join_mode": "fallback_creative_time",
                "join_status": "matched",
                "confidence": 0.77,
                "reason": "matched_by_creative_and_time_window",
                "matched_metric_date": "2026-03-01",
                "matched_billing_id": "cfg-1",
                "matched_creative_id": "cr-1",
                "matched_app_id": "com.example.app",
                "matched_country": "US",
                "matched_publisher_id": "pub-1",
                "matched_impressions": 1234,
                "matched_clicks": 43,
                "matched_spend_usd": 91.2,
                "fallback_window_days": 1,
                "fallback_candidate_count": 1,
                "created_at": "2026-03-01T00:01:00+00:00",
                "updated_at": "2026-03-01T00:02:00+00:00",
            }
        ]

    async def _stub_query_one(sql: str, params: tuple = ()):
        assert "COUNT(*) AS total_rows" in sql
        return {"total_rows": 1}

    monkeypatch.setattr("services.conversion_attribution_service.pg_query", _stub_query)
    monkeypatch.setattr("services.conversion_attribution_service.pg_query_one", _stub_query_one)
    monkeypatch.setattr("services.conversion_attribution_service.pg_execute", _unused_async)

    result = asyncio.run(
        service.list_joins(
            buyer_id="1111111111",
            source_type="appsflyer",
            days=14,
            join_mode="fallback_creative_time",
            join_status="matched",
            min_confidence=0.3,
            limit=25,
            offset=0,
        )
    )

    assert result["meta"]["total"] == 1
    assert result["meta"]["returned"] == 1
    assert result["meta"]["limit"] == 25
    assert result["rows"][0]["id"] == 9
    assert result["rows"][0]["confidence"] == 0.77
    assert result["rows"][0]["matched_impressions"] == 1234
