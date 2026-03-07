"""RBAC tests for /performance routes."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers import performance as performance_router
from services.auth_service import User


class _StubStore:
    def __init__(self) -> None:
        self.cleanup_days: int | None = None
        self.metrics_calls = 0

    async def clear_old_rtb_daily(self, days_to_keep: int) -> int:
        self.cleanup_days = days_to_keep
        return 7

    async def get_performance_metrics(self, **kwargs):
        _ = kwargs
        self.metrics_calls += 1
        return []


def _build_client(
    *,
    require_admin_override=None,
    require_seat_admin_override=None,
    store: _StubStore | None = None,
) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(performance_router.router, prefix="/api")

    if store is None:
        store = _StubStore()
    app.dependency_overrides[performance_router.get_store] = lambda: store

    if require_admin_override is not None:
        app.dependency_overrides[performance_router.require_admin] = require_admin_override

    if require_seat_admin_override is not None:
        app.dependency_overrides[performance_router.require_seat_admin_or_sudo] = require_seat_admin_override

    return SyncASGIClient(app)


def test_import_stream_start_forbidden_when_seat_admin_dependency_denies() -> None:
    async def _deny_seat_admin():
        raise HTTPException(status_code=403, detail="Admin access to at least one seat is required.")

    client = _build_client(require_seat_admin_override=_deny_seat_admin)

    response = client.post(
        "/api/performance/import/stream/start",
        json={"filename": "sample.csv", "file_size_bytes": 1024},
    )

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_import_stream_start_allows_when_seat_admin_dependency_passes() -> None:
    async def _allow_seat_admin():
        return User(id="seat-admin-1", email="admin@example.com", role="read")

    client = _build_client(require_seat_admin_override=_allow_seat_admin)

    response = client.post(
        "/api/performance/import/stream/start",
        json={"filename": "sample.csv", "file_size_bytes": 1024},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_id"]
    assert payload["message"] == "Upload started"

    # Cleanup temporary upload artifacts created by the endpoint.
    upload_id = payload["upload_id"]
    for path in (
        performance_router._meta_path(upload_id),
        performance_router._data_path(upload_id),
    ):
        Path(path).unlink(missing_ok=True)


def test_cleanup_forbidden_when_require_admin_denies() -> None:
    async def _deny_admin():
        raise HTTPException(status_code=403, detail="Sudo access required.")

    client = _build_client(require_admin_override=_deny_admin)

    response = client.delete("/api/performance/cleanup", params={"days_to_keep": 30})

    assert response.status_code == 403
    assert "sudo" in response.json()["detail"].lower()


def test_cleanup_calls_store_when_require_admin_allows() -> None:
    async def _allow_admin():
        return User(id="sudo-1", email="sudo@example.com", role="sudo")

    stub_store = _StubStore()
    client = _build_client(require_admin_override=_allow_admin, store=stub_store)

    response = client.delete("/api/performance/cleanup", params={"days_to_keep": 30})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["records_deleted"] == 7
    assert stub_store.cleanup_days == 30


def test_metrics_forbidden_when_require_admin_denies() -> None:
    async def _deny_admin():
        raise HTTPException(status_code=403, detail="Sudo access required.")

    stub_store = _StubStore()
    client = _build_client(require_admin_override=_deny_admin, store=stub_store)

    response = client.get("/api/performance/metrics")

    assert response.status_code == 403
    assert "sudo" in response.json()["detail"].lower()
    assert stub_store.metrics_calls == 0
