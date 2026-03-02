"""Data health service tests for optimizer-readiness checks."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from services.data_health_service import DataHealthService


def _build_query_one_stub(stale_quality: bool = False):
    today = date.today()
    refreshed_at = datetime.now(timezone.utc)

    async def _stub(
        sql: str,
        params: tuple = (),
        statement_timeout_ms: int | None = None,
    ):
        if "SELECT MAX(refreshed_at) AS refreshed_at FROM seat_report_completeness_daily" in sql:
            return {"refreshed_at": refreshed_at}

        # Source freshness
        if "FROM rtb_daily" in sql and "MAX(metric_date::date) AS max_metric_date, COUNT(*) AS rows" in sql:
            return {"max_metric_date": today, "rows": 300}
        if "FROM rtb_geo_daily" in sql:
            return {"max_metric_date": today, "rows": 220}

        # Serving freshness
        if "FROM seat_geo_daily" in sql:
            return {"max_metric_date": today, "rows": 180}
        if "FROM pretarg_geo_daily" in sql:
            return {"max_metric_date": today, "rows": 180}
        if "FROM pretarg_publisher_daily" in sql:
            return {"max_metric_date": today, "rows": 180}

        # Dimension coverage
        if "FROM rtb_daily" in sql and "missing_country_rows" in sql:
            return {
                "total_rows": 300,
                "missing_country_rows": 5,
                "missing_publisher_rows": 7,
                "missing_billing_rows": 4,
            }

        # Ingestion summary
        if "FROM ingestion_runs" in sql:
            return {
                "total_runs": 12,
                "successful_runs": 12,
                "failed_runs": 0,
                "last_started_at": None,
                "last_finished_at": None,
            }

        # Report completeness by table
        if "COUNT(DISTINCT metric_date::date) AS active_days" in sql and "FROM rtb_daily" in sql:
            return {"rows": 300, "active_days": 7, "max_metric_date": today}
        if "COUNT(DISTINCT metric_date::date) AS active_days" in sql and "FROM rtb_bidstream" in sql:
            return {"rows": 280, "active_days": 7, "max_metric_date": today}
        if "COUNT(DISTINCT metric_date::date) AS active_days" in sql and "FROM rtb_bid_filtering" in sql:
            return {"rows": 120, "active_days": 7, "max_metric_date": today}
        if "COUNT(DISTINCT metric_date::date) AS active_days" in sql and "FROM rtb_quality" in sql:
            return {"rows": 140, "active_days": 7, "max_metric_date": today}
        if "COUNT(DISTINCT metric_date::date) AS active_days" in sql and "FROM web_domain_daily" in sql:
            return {"rows": 95, "active_days": 7, "max_metric_date": today}

        # Quality freshness
        if (
            "FROM rtb_quality" in sql
            and "COUNT(*) AS rows" in sql
            and "COUNT(DISTINCT metric_date::date)" not in sql
        ):
            max_metric_date = today - timedelta(days=9) if stale_quality else today
            return {"rows": 140, "max_metric_date": max_metric_date}

        # Bidstream dimension coverage
        if "FROM rtb_bidstream" in sql and "missing_platform_rows" in sql:
            return {
                "total_rows": 280,
                "missing_platform_rows": 12,
                "missing_environment_rows": 8,
                "missing_transaction_type_rows": 15,
            }

        return {}

    return _stub


def _build_query_rows_stub():
    today = date.today()
    refreshed_at = datetime.now(timezone.utc)

    async def _stub(sql: str, params: tuple = ()):
        if "FROM seat_report_completeness_daily" in sql:
            return [
                {
                    "metric_date": today,
                    "buyer_account_id": "1111111111",
                    "has_rtb_daily": True,
                    "has_rtb_bidstream": True,
                    "has_rtb_bid_filtering": True,
                    "has_rtb_quality": True,
                    "has_web_domain_daily": True,
                    "available_report_types": 5,
                    "expected_report_types": 5,
                    "completeness_pct": 100.0,
                    "availability_state": "healthy",
                    "refreshed_at": refreshed_at,
                },
                {
                    "metric_date": today,
                    "buyer_account_id": "2222222222",
                    "has_rtb_daily": True,
                    "has_rtb_bidstream": True,
                    "has_rtb_bid_filtering": False,
                    "has_rtb_quality": True,
                    "has_web_domain_daily": False,
                    "available_report_types": 3,
                    "expected_report_types": 5,
                    "completeness_pct": 60.0,
                    "availability_state": "degraded",
                    "refreshed_at": refreshed_at,
                },
            ]
        return []

    return _stub


async def _noop_execute(sql: str, params: tuple = ()) -> int:
    return 0


@pytest.mark.asyncio
async def test_get_data_health_includes_optimizer_readiness(monkeypatch: pytest.MonkeyPatch):
    query_one_stub = _build_query_one_stub()
    monkeypatch.setattr("services.data_health_service.pg_query_one_with_timeout", query_one_stub)
    monkeypatch.setattr("services.data_health_service.pg_query", _build_query_rows_stub())
    monkeypatch.setattr("services.data_health_service.pg_execute", _noop_execute)
    service = DataHealthService()

    payload = await service.get_data_health(days=7, buyer_id=None)

    assert payload["state"] == "degraded"
    readiness = payload["optimizer_readiness"]
    assert readiness["report_completeness"]["availability_state"] == "healthy"
    assert readiness["report_completeness"]["coverage_pct"] == 100.0
    assert readiness["rtb_quality_freshness"]["availability_state"] == "healthy"
    assert readiness["bidstream_dimension_coverage"]["availability_state"] == "healthy"
    assert readiness["seat_day_completeness"]["summary"]["total_seat_days"] == 2
    assert readiness["seat_day_completeness"]["summary"]["degraded_seat_days"] == 1


@pytest.mark.asyncio
async def test_get_data_health_marks_stale_quality_as_degraded(monkeypatch: pytest.MonkeyPatch):
    query_one_stub = _build_query_one_stub(stale_quality=True)
    monkeypatch.setattr("services.data_health_service.pg_query_one_with_timeout", query_one_stub)
    monkeypatch.setattr("services.data_health_service.pg_query", _build_query_rows_stub())
    monkeypatch.setattr("services.data_health_service.pg_execute", _noop_execute)
    service = DataHealthService()

    payload = await service.get_data_health(days=7, buyer_id=None)

    assert payload["state"] == "degraded"
    freshness = payload["optimizer_readiness"]["rtb_quality_freshness"]
    assert freshness["availability_state"] == "stale"
    assert freshness["age_days"] >= 9


@pytest.mark.asyncio
async def test_get_data_health_applies_seat_day_filters(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    async def _capture_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    query_one_stub = _build_query_one_stub()
    monkeypatch.setattr("services.data_health_service.pg_query_one_with_timeout", query_one_stub)
    monkeypatch.setattr("services.data_health_service.pg_query", _capture_query)
    monkeypatch.setattr("services.data_health_service.pg_execute", _noop_execute)
    service = DataHealthService()

    await service.get_data_health(
        days=14,
        buyer_id="3333333333",
        availability_state="degraded",
        min_completeness_pct=70.0,
        limit=50,
    )

    sql = str(captured.get("sql") or "")
    params = tuple(captured.get("params") or ())

    assert "buyer_account_id = %s" in sql
    assert "availability_state = %s" in sql
    assert "completeness_pct >= %s" in sql
    assert params == (14, "3333333333", "degraded", 70.0, 50)
