"""RBAC tests for collection endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers import collect as collect_router
from services.auth_service import User


class _StubConfig:
    def is_configured(self) -> bool:
        return True

    def get_service_account_path(self) -> str:
        return "/tmp/fake-service-account.json"


class _StubCollectService:
    calls = 0

    async def collect_and_save(self, **kwargs):
        _ = kwargs
        self.__class__.calls += 1
        return 10, 7


def _build_client(monkeypatch: pytest.MonkeyPatch, seat_admin_override) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(collect_router.router, prefix="/api")
    app.dependency_overrides[collect_router.get_config] = lambda: _StubConfig()
    app.dependency_overrides[collect_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[collect_router.require_seat_admin_or_sudo] = seat_admin_override
    monkeypatch.setattr(collect_router, "CollectService", _StubCollectService)
    return SyncASGIClient(app)


def test_collect_sync_forbidden_when_seat_admin_dependency_denies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _deny_seat_admin():
        raise HTTPException(status_code=403, detail="Admin access to at least one seat is required.")

    client = _build_client(monkeypatch, _deny_seat_admin)
    response = client.post("/api/collect/sync", json={"account_id": "1111111111"})

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_collect_sync_allows_when_seat_admin_dependency_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _StubCollectService.calls = 0

    async def _allow_seat_admin():
        return User(id="admin-1", email="admin@example.com", role="read")

    client = _build_client(monkeypatch, _allow_seat_admin)
    response = client.post(
        "/api/collect/sync",
        json={"account_id": "1111111111", "filter_query": "status=ACTIVE"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["account_id"] == "1111111111"
    assert payload["creatives_collected"] == 7
    assert _StubCollectService.calls == 1
