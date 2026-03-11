"""RBAC tests for settings mutation endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers.settings import actions as actions_router
from api.routers.settings import changes as changes_router
from api.routers.settings import endpoints as endpoints_router
from api.routers.settings import optimizer as optimizer_router
from api.routers.settings import pretargeting as pretargeting_router
from api.routers.settings import snapshots as snapshots_router
from services.auth_service import User


def _deny_seat_admin():
    async def _deny():
        raise HTTPException(status_code=403, detail="Admin access to at least one seat is required.")

    return _deny


def _build_actions_client() -> SyncASGIClient:
    app = FastAPI()
    app.include_router(actions_router.router, prefix="/api")
    app.dependency_overrides[actions_router.require_seat_admin_or_sudo] = _deny_seat_admin()
    return SyncASGIClient(app)


def _build_changes_client() -> SyncASGIClient:
    app = FastAPI()
    app.include_router(changes_router.router, prefix="/api")
    app.dependency_overrides[changes_router.require_seat_admin_or_sudo] = _deny_seat_admin()
    return SyncASGIClient(app)


def _build_endpoints_client() -> SyncASGIClient:
    app = FastAPI()
    app.include_router(endpoints_router.router, prefix="/api")
    app.dependency_overrides[endpoints_router.require_seat_admin_or_sudo] = _deny_seat_admin()
    app.dependency_overrides[endpoints_router.get_seats_service] = lambda: SimpleNamespace()
    return SyncASGIClient(app)


def _build_pretargeting_client() -> SyncASGIClient:
    app = FastAPI()
    app.include_router(pretargeting_router.router, prefix="/api")
    app.dependency_overrides[pretargeting_router.require_seat_admin_or_sudo] = _deny_seat_admin()
    app.dependency_overrides[pretargeting_router.get_seats_service] = lambda: SimpleNamespace()
    return SyncASGIClient(app)


def _build_snapshots_client() -> SyncASGIClient:
    app = FastAPI()
    app.include_router(snapshots_router.router, prefix="/api")
    app.dependency_overrides[snapshots_router.require_seat_admin_or_sudo] = _deny_seat_admin()
    return SyncASGIClient(app)


def _build_optimizer_client(require_admin_override) -> SyncASGIClient:
    class _StubStore:
        def __init__(self):
            self.set_calls = 0
            self.audit_calls = 0

        async def set_setting(self, key: str, value: str, updated_by=None):
            _ = (key, value, updated_by)
            self.set_calls += 1

        async def log_audit(self, **kwargs):
            _ = kwargs
            self.audit_calls += 1

        async def get_setting(self, _key: str):
            return None

    app = FastAPI()
    app.include_router(optimizer_router.router, prefix="/api")
    app.dependency_overrides[optimizer_router.require_admin] = require_admin_override
    app.dependency_overrides[optimizer_router.get_store] = _StubStore
    return SyncASGIClient(app)


def test_actions_apply_all_forbidden_without_seat_admin() -> None:
    client = _build_actions_client()

    response = client.post("/api/settings/pretargeting/123/apply-all")

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_changes_mark_applied_forbidden_without_seat_admin() -> None:
    client = _build_changes_client()

    response = client.post("/api/settings/pretargeting/pending-change/1/mark-applied")

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_changes_discard_all_forbidden_without_seat_admin() -> None:
    client = _build_changes_client()

    response = client.post("/api/settings/pretargeting/123/discard-all")

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_endpoints_sync_forbidden_without_seat_admin() -> None:
    client = _build_endpoints_client()

    response = client.post("/api/settings/endpoints/sync")

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_pretargeting_sync_forbidden_without_seat_admin() -> None:
    client = _build_pretargeting_client()

    response = client.post("/api/settings/pretargeting/sync")

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_snapshots_create_forbidden_without_seat_admin() -> None:
    client = _build_snapshots_client()

    response = client.post(
        "/api/settings/pretargeting/snapshot",
        json={"billing_id": "123", "snapshot_name": "before-change"},
    )

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_optimizer_update_forbidden_without_sudo() -> None:
    async def _deny_admin():
        raise HTTPException(status_code=403, detail="Sudo access required.")

    client = _build_optimizer_client(_deny_admin)

    response = client.put(
        "/api/settings/optimizer/setup",
        json={"monthly_hosting_cost_usd": 10.0},
    )

    assert response.status_code == 403
    assert "sudo" in response.json()["detail"].lower()


def test_optimizer_update_allows_with_sudo() -> None:
    async def _allow_admin():
        return User(id="sudo-1", email="sudo@example.com", role="sudo")

    client = _build_optimizer_client(_allow_admin)

    response = client.put(
        "/api/settings/optimizer/setup",
        json={"monthly_hosting_cost_usd": 10.0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["monthly_hosting_cost_usd"] == 10.0
    assert body["effective_cpm_enabled"] is True
