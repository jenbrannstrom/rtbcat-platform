"""API tests for UI page-load telemetry routes."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from api.routers import system as system_router
from tests.support.asgi_client import SyncASGIClient


def _build_client(monkeypatch: pytest.MonkeyPatch) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(system_router.router, prefix="/api")

    async def _get_store():
        return SimpleNamespace()

    async def _get_current_user():
        return SimpleNamespace(id="u1", role="sudo", email="admin@example.com")

    app.dependency_overrides[system_router.get_store] = _get_store
    app.dependency_overrides[system_router.get_current_user] = _get_current_user
    return SyncASGIClient(app)


def test_record_ui_page_load_metric_records_payload(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    async def _resolve_buyer_id(buyer_id: str | None, store=None, user=None):
        return buyer_id

    async def _stub_execute(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return 1

    monkeypatch.setattr(system_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(system_router, "pg_execute", _stub_execute)
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/system/ui-metrics/page-load",
        json={
            "page": "qps_home",
            "buyer_id": "1111111111",
            "selected_days": 14,
            "time_to_first_table_row_ms": 2100,
            "time_to_table_hydrated_ms": 4300,
            "api_latency_ms": {
                "/settings/pretargeting": 1800,
                "/settings/endpoints": -10,  # invalid, should be dropped
            },
            "sampled_at": "2026-03-01T00:00:00+00:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"
    params = captured["params"]
    assert isinstance(params, tuple)
    assert params[0] == "qps_home"
    assert params[1] == "1111111111"
    assert params[2] == "u1"
    assert params[3] == 14
    assert params[4] == 2100
    assert params[5] == 4300
    assert json.loads(str(params[6])) == {"/settings/pretargeting": 1800.0}
    assert params[7] == "2026-03-01T00:00:00+00:00"


def test_record_ui_page_load_metric_rejects_empty_metrics(monkeypatch: pytest.MonkeyPatch):
    async def _resolve_buyer_id(buyer_id: str | None, store=None, user=None):
        return buyer_id

    async def _stub_execute(sql: str, params: tuple = ()):
        return 1

    monkeypatch.setattr(system_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(system_router, "pg_execute", _stub_execute)
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/system/ui-metrics/page-load",
        json={
            "page": "qps_home",
            "api_latency_ms": {},
        },
    )

    assert response.status_code == 400
    assert "At least one page-load metric" in response.json()["detail"]


def test_ui_page_load_metric_summary_returns_percentiles(monkeypatch: pytest.MonkeyPatch):
    async def _resolve_buyer_id(buyer_id: str | None, store=None, user=None):
        return buyer_id

    async def _stub_query_one(sql: str, params: tuple = ()):
        assert "percentile_cont(0.95)" in sql
        assert params == ("qps_home", 24, "1111111111")
        return {
            "sample_count": 4,
            "p50_first_table_row_ms": 2200.0,
            "p95_first_table_row_ms": 5900.0,
            "p50_table_hydrated_ms": 4300.0,
            "p95_table_hydrated_ms": 7700.0,
            "last_sampled_at": "2026-03-01T00:00:00+00:00",
        }

    async def _stub_query(sql: str, params: tuple = ()):
        if "ORDER BY sampled_at DESC" in sql:
            assert params == ("qps_home", 24, "1111111111", 5)
            return [
                {
                    "sampled_at": "2026-03-01T00:00:00+00:00",
                    "buyer_id": "1111111111",
                    "selected_days": 14,
                    "time_to_first_table_row_ms": 2200.0,
                    "time_to_table_hydrated_ms": 4300.0,
                    "api_latency_ms": {"/settings/pretargeting": 1800.0},
                }
            ]
        if "GROUP BY bucket_start" in sql:
            assert params == (1, 1, "qps_home", 24, "1111111111", 24)
            return [
                {
                    "bucket_start": "2026-03-01T00:00:00+00:00",
                    "sample_count": 2,
                    "p50_first_table_row_ms": 2100.0,
                    "p95_first_table_row_ms": 5200.0,
                    "p50_table_hydrated_ms": 4000.0,
                    "p95_table_hydrated_ms": 7500.0,
                }
            ]
        assert "jsonb_each_text" in sql
        assert params == ("qps_home", 24, "1111111111", 10)
        return [
            {
                "api_path": "/settings/pretargeting",
                "sample_count": 4,
                "p50_latency_ms": 1200.0,
                "p95_latency_ms": 1800.0,
            }
        ]

    monkeypatch.setattr(system_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(system_router, "pg_query_one", _stub_query_one)
    monkeypatch.setattr(system_router, "pg_query", _stub_query)
    client = _build_client(monkeypatch)

    response = client.get(
        "/api/system/ui-metrics/page-load/summary",
        params={
            "page": "qps_home",
            "buyer_id": "1111111111",
            "since_hours": 24,
            "latest_limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_count"] == 4
    assert payload["p95_first_table_row_ms"] == 5900.0
    assert payload["p95_table_hydrated_ms"] == 7700.0
    assert payload["latest_samples"][0]["api_latency_ms"]["/settings/pretargeting"] == 1800.0
    assert payload["api_latency_rollup"][0]["api_path"] == "/settings/pretargeting"
    assert payload["api_latency_rollup"][0]["p95_latency_ms"] == 1800.0
    assert payload["time_buckets"][0]["sample_count"] == 2
    assert payload["time_buckets"][0]["p95_first_table_row_ms"] == 5200.0


def test_ui_page_load_metric_summary_respects_api_rollup_limit(monkeypatch: pytest.MonkeyPatch):
    async def _resolve_buyer_id(buyer_id: str | None, store=None, user=None):
        return buyer_id

    async def _stub_query_one(sql: str, params: tuple = ()):
        assert params == ("qps_home", 24, "1111111111")
        return {"sample_count": 0}

    async def _stub_query(sql: str, params: tuple = ()):
        if "ORDER BY sampled_at DESC" in sql:
            assert params == ("qps_home", 24, "1111111111", 2)
            return []
        if "GROUP BY bucket_start" in sql:
            assert params == (1, 1, "qps_home", 24, "1111111111", 24)
            return []
        assert "jsonb_each_text" in sql
        assert params == ("qps_home", 24, "1111111111", 3)
        return []

    monkeypatch.setattr(system_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(system_router, "pg_query_one", _stub_query_one)
    monkeypatch.setattr(system_router, "pg_query", _stub_query)
    client = _build_client(monkeypatch)

    response = client.get(
        "/api/system/ui-metrics/page-load/summary",
        params={
            "page": "qps_home",
            "buyer_id": "1111111111",
            "since_hours": 24,
            "latest_limit": 2,
            "api_rollup_limit": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_count"] == 0
    assert payload["latest_samples"] == []
    assert payload["api_latency_rollup"] == []


def test_ui_page_load_metric_summary_respects_bucket_params(monkeypatch: pytest.MonkeyPatch):
    async def _resolve_buyer_id(buyer_id: str | None, store=None, user=None):
        return buyer_id

    async def _stub_query_one(sql: str, params: tuple = ()):
        assert params == ("qps_home", 72, "1111111111")
        return {"sample_count": 0}

    async def _stub_query(sql: str, params: tuple = ()):
        if "ORDER BY sampled_at DESC" in sql:
            assert params == ("qps_home", 72, "1111111111", 2)
            return []
        if "jsonb_each_text" in sql:
            assert params == ("qps_home", 72, "1111111111", 4)
            return []
        assert "GROUP BY bucket_start" in sql
        assert params == (6, 6, "qps_home", 72, "1111111111", 8)
        return []

    monkeypatch.setattr(system_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(system_router, "pg_query_one", _stub_query_one)
    monkeypatch.setattr(system_router, "pg_query", _stub_query)
    client = _build_client(monkeypatch)

    response = client.get(
        "/api/system/ui-metrics/page-load/summary",
        params={
            "page": "qps_home",
            "buyer_id": "1111111111",
            "since_hours": 72,
            "latest_limit": 2,
            "api_rollup_limit": 4,
            "bucket_hours": 6,
            "bucket_limit": 8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_count"] == 0
    assert payload["time_buckets"] == []
