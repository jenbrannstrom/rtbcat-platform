"""RBAC tests for troubleshooting collection endpoint."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers import troubleshooting as troubleshooting_router
from services.auth_service import User


def _build_client(require_admin_override) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(troubleshooting_router.router)
    app.dependency_overrides[troubleshooting_router.require_admin] = require_admin_override
    return SyncASGIClient(app)


def test_troubleshooting_collect_forbidden_when_require_admin_denies() -> None:
    async def _deny_admin():
        raise HTTPException(status_code=403, detail="Sudo access required.")

    client = _build_client(_deny_admin)
    response = client.post("/api/troubleshooting/collect")

    assert response.status_code == 403
    assert "sudo" in response.json()["detail"].lower()


def test_troubleshooting_collect_allows_when_require_admin_passes() -> None:
    async def _allow_admin():
        return User(id="sudo-1", email="sudo@example.com", role="sudo")

    client = _build_client(_allow_admin)
    response = client.post("/api/troubleshooting/collect", params={"days": 14, "environment": "APP"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collection_queued"
    assert payload["days"] == 14
    assert payload["environment"] == "APP"
