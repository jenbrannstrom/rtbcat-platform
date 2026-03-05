"""Regression tests for Home precompute bidstream report-type scoping."""

from __future__ import annotations

import importlib
import sys
import types

import pytest


class _FakeConn:
    def execute(self, *_args, **_kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_refresh_home_summaries_filters_bidstream_queries_by_report_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Provide a lightweight BigQuery stub so this test can run without
    # google-cloud-bigquery installed in the test environment.
    fake_bigquery = types.SimpleNamespace(
        ArrayQueryParameter=lambda *args, **kwargs: ("array", args, kwargs),
        ScalarQueryParameter=lambda *args, **kwargs: ("scalar", args, kwargs),
    )
    fake_cloud = types.ModuleType("google.cloud")
    fake_cloud.bigquery = fake_bigquery  # type: ignore[attr-defined]
    fake_google = types.ModuleType("google")
    fake_google.cloud = fake_cloud  # type: ignore[attr-defined]

    monkeypatch.delitem(sys.modules, "services.home_precompute", raising=False)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.cloud", fake_cloud)

    home_precompute = importlib.import_module("services.home_precompute")

    captured_sql: list[str] = []

    def _fake_get_bigquery_client():
        return object()

    def _fake_build_table_ref(_client, table_env: str, default_table: str) -> str:
        del table_env
        return default_table

    def _fake_run_query(_client, sql: str, params):
        del params
        captured_sql.append(sql)
        return []

    def _fake_execute_many(_conn, sql: str, rows) -> None:
        del sql, rows
        return None

    async def _fake_pg_transaction_async(fn):
        return fn(_FakeConn())

    monkeypatch.setattr(home_precompute, "get_bigquery_client", _fake_get_bigquery_client)
    monkeypatch.setattr(home_precompute, "build_table_ref", _fake_build_table_ref)
    monkeypatch.setattr(home_precompute, "run_query", _fake_run_query)
    monkeypatch.setattr(home_precompute, "execute_many", _fake_execute_many)
    monkeypatch.setattr(home_precompute, "pg_transaction_async", _fake_pg_transaction_async)
    monkeypatch.setattr(home_precompute, "record_refresh_log_postgres", lambda *_a, **_k: None)
    monkeypatch.setattr(home_precompute, "record_refresh_run_postgres", lambda *_a, **_k: None)

    result = await home_precompute.refresh_home_summaries(dates=["2026-03-04"])

    assert result["dates"] == ["2026-03-04"]
    assert len(captured_sql) >= 5

    seat_sql, publisher_sql, geo_sql = captured_sql[:3]
    required_filter = "AND report_type = 'rtb_bidstream_publisher'"

    assert required_filter in seat_sql
    assert required_filter in publisher_sql
    assert required_filter in geo_sql
