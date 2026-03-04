"""RBAC tests for retention mutation endpoints."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.routers import retention as retention_router
from services.auth_service import User


class _StubRetentionService:
    set_calls = []
    run_calls = 0

    async def get_config(self):
        return {
            "raw_retention_days": 90,
            "summary_retention_days": 365,
            "auto_aggregate_after_days": 30,
        }

    async def set_config(self, **kwargs):
        self.__class__.set_calls.append(kwargs)

    async def get_storage_stats(self):
        return {
            "raw_rows": 0,
            "raw_earliest_date": None,
            "raw_latest_date": None,
            "summary_rows": 0,
            "summary_earliest_date": None,
            "summary_latest_date": None,
            "conversion_event_rows": 0,
            "conversion_event_earliest_ts": None,
            "conversion_event_latest_ts": None,
            "conversion_failure_rows": 0,
            "conversion_failure_earliest_ts": None,
            "conversion_failure_latest_ts": None,
            "conversion_join_rows": 0,
            "conversion_join_earliest_ts": None,
            "conversion_join_latest_ts": None,
            "conversion_raw_event_rows": 0,
            "conversion_raw_event_earliest_ts": None,
            "conversion_raw_event_latest_ts": None,
        }

    async def run_retention_job(self):
        self.__class__.run_calls += 1
        return {
            "aggregated_rows": 3,
            "deleted_raw_rows": 5,
            "deleted_summary_rows": 1,
            "deleted_conversion_event_rows": 0,
            "deleted_conversion_failure_rows": 0,
            "deleted_conversion_join_rows": 0,
            "deleted_conversion_raw_event_rows": 0,
        }


def _build_client(monkeypatch: pytest.MonkeyPatch, require_admin_override) -> TestClient:
    app = FastAPI()
    app.include_router(retention_router.router, prefix="/api")
    app.dependency_overrides[retention_router.require_admin] = require_admin_override
    monkeypatch.setattr(retention_router, "RetentionService", _StubRetentionService)
    return TestClient(app)


def test_set_retention_config_forbidden_when_require_admin_denies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _StubRetentionService.set_calls = []

    async def _deny_admin():
        raise HTTPException(status_code=403, detail="Sudo access required.")

    client = _build_client(monkeypatch, _deny_admin)
    response = client.post(
        "/api/retention/config",
        json={
            "raw_retention_days": 90,
            "summary_retention_days": 365,
            "auto_aggregate_after_days": 30,
        },
    )

    assert response.status_code == 403
    assert "sudo" in response.json()["detail"].lower()
    assert _StubRetentionService.set_calls == []


def test_set_retention_config_allows_when_require_admin_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _StubRetentionService.set_calls = []

    async def _allow_admin():
        return User(id="sudo-1", email="sudo@example.com", role="sudo")

    client = _build_client(monkeypatch, _allow_admin)
    response = client.post(
        "/api/retention/config",
        json={
            "raw_retention_days": 120,
            "summary_retention_days": 730,
            "auto_aggregate_after_days": 45,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["raw_retention_days"] == 120
    assert body["summary_retention_days"] == 730
    assert body["auto_aggregate_after_days"] == 45
    assert _StubRetentionService.set_calls == [
        {
            "raw_retention_days": 120,
            "summary_retention_days": 730,
            "auto_aggregate_after_days": 45,
        }
    ]


def test_run_retention_job_forbidden_when_require_admin_denies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _StubRetentionService.run_calls = 0

    async def _deny_admin():
        raise HTTPException(status_code=403, detail="Sudo access required.")

    client = _build_client(monkeypatch, _deny_admin)
    response = client.post("/api/retention/run")

    assert response.status_code == 403
    assert "sudo" in response.json()["detail"].lower()
    assert _StubRetentionService.run_calls == 0


def test_run_retention_job_allows_when_require_admin_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _StubRetentionService.run_calls = 0

    async def _allow_admin():
        return User(id="sudo-1", email="sudo@example.com", role="sudo")

    client = _build_client(monkeypatch, _allow_admin)
    response = client.post("/api/retention/run")

    assert response.status_code == 200
    body = response.json()
    assert body["aggregated_rows"] == 3
    assert body["deleted_raw_rows"] == 5
    assert _StubRetentionService.run_calls == 1
