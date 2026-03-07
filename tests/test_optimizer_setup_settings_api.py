"""API tests for optimizer setup settings endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from tests.support.asgi_client import SyncASGIClient

from api.routers.settings import optimizer as optimizer_settings_router


class _StubStore:
    def __init__(self):
        self.settings: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, str | None]] = []
        self.audit_calls: list[dict] = []

    async def get_setting(self, key: str):
        return self.settings.get(key)

    async def set_setting(self, key: str, value: str, updated_by=None):
        self.settings[key] = value
        self.set_calls.append((key, value, updated_by))

    async def log_audit(self, **kwargs):
        self.audit_calls.append(kwargs)
        return SimpleNamespace(**kwargs)


def _build_client(
    stub_store: _StubStore,
    monkeypatch: pytest.MonkeyPatch,
) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(optimizer_settings_router.router, prefix="/api")
    app.dependency_overrides[optimizer_settings_router.get_store] = lambda: stub_store
    app.dependency_overrides[optimizer_settings_router.get_current_user] = lambda: SimpleNamespace(
        id="u1",
        role="sudo",
        email="admin@example.com",
    )
    app.dependency_overrides[optimizer_settings_router.require_admin] = lambda: SimpleNamespace(
        id="u1",
        role="sudo",
        email="admin@example.com",
    )
    return SyncASGIClient(app)


def test_get_optimizer_setup_parses_monthly_cost(monkeypatch: pytest.MonkeyPatch):
    stub = _StubStore()
    stub.settings["optimizer_monthly_hosting_cost_usd"] = "3000.5"
    client = _build_client(stub, monkeypatch)

    response = client.get("/api/settings/optimizer/setup")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monthly_hosting_cost_usd"] == 3000.5
    assert payload["effective_cpm_enabled"] is True


def test_get_optimizer_setup_handles_missing_or_invalid(monkeypatch: pytest.MonkeyPatch):
    stub = _StubStore()
    stub.settings["optimizer_monthly_hosting_cost_usd"] = "not-a-number"
    client = _build_client(stub, monkeypatch)

    response = client.get("/api/settings/optimizer/setup")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monthly_hosting_cost_usd"] is None
    assert payload["effective_cpm_enabled"] is False


def test_update_optimizer_setup_writes_setting_and_audit(monkeypatch: pytest.MonkeyPatch):
    stub = _StubStore()
    client = _build_client(stub, monkeypatch)

    response = client.put(
        "/api/settings/optimizer/setup",
        json={"monthly_hosting_cost_usd": 4500.0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["monthly_hosting_cost_usd"] == 4500.0
    assert payload["effective_cpm_enabled"] is True

    assert len(stub.set_calls) == 1
    set_call = stub.set_calls[0]
    assert set_call[0] == "optimizer_monthly_hosting_cost_usd"
    assert set_call[1] == "4500.000000"
    assert set_call[2] == "u1"

    assert len(stub.audit_calls) == 1
    assert stub.audit_calls[0]["action"] == "optimizer_setup_updated"
    assert stub.audit_calls[0]["resource_id"] == "optimizer_monthly_hosting_cost_usd"
