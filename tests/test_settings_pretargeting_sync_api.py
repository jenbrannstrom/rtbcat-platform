"""Sync endpoint: a billing_id must sync the bidder that owns that config."""

from __future__ import annotations

import types

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from tests.support.asgi_client import SyncASGIClient

from api.routers.settings import pretargeting as pretargeting_router


def _account(tmp_path, name: str):
    creds = tmp_path / f"{name}.json"
    creds.write_text("{}")
    return types.SimpleNamespace(id=f"sa-{name}", display_name=name, credentials_path=str(creds))


class _StubSeatsService:
    def __init__(self, accounts, bidder_by_account, owner_by_bidder):
        self.accounts = accounts
        self.bidder_by_account = bidder_by_account
        self.owner_by_bidder = owner_by_bidder

    async def get_service_accounts(self, active_only: bool = True):
        return self.accounts

    async def get_service_account(self, account_id: str):
        return next((a for a in self.accounts if a.id == account_id), None)

    async def get_bidder_id_for_service_account(self, service_account_id: str):
        return self.bidder_by_account.get(service_account_id)

    async def get_service_account_for_bidder(self, bidder_id: str):
        return self.owner_by_bidder.get(bidder_id)

    async def get_first_bidder_id(self):
        return None


class _StubPretargetingService:
    configs = {"198363911721": {"billing_id": "198363911721", "config_id": "cfg-1", "bidder_id": "bidder-B"}}
    saved: list[dict] = []

    async def get_config(self, billing_id: str):
        return self.configs.get(billing_id)

    async def save_config(self, row: dict):
        self.saved.append(row)

    async def clear_sync_publishers(self, billing_id: str):
        return None

    async def add_publisher(self, **kwargs):
        return None

    async def list_configs(self, bidder_id=None, limit=None, summary_only=False):
        return []

    async def update_state(self, billing_id: str, state: str):
        return None


class _StubClient:
    built: list[dict] = []

    def __init__(self, credentials_path: str, account_id: str):
        self.built.append({"credentials_path": credentials_path, "account_id": account_id})
        self.account_id = account_id

    async def fetch_all_pretargeting_configs(self):
        return [{
            "configId": "cfg-1",
            "billingId": "198363911721",
            "displayName": "US+CAN_CTV",
            "state": "ACTIVE",
            "maximumQps": "15000",
        }]

    async def get_pretargeting_config_by_id(self, config_id: str):
        return None


def _build_client(monkeypatch, seats) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(pretargeting_router.router, prefix="/api")
    app.dependency_overrides[pretargeting_router.require_seat_admin_or_sudo] = lambda: types.SimpleNamespace(
        id="u1", role="admin", email="admin@example.com"
    )
    app.dependency_overrides[pretargeting_router.get_seats_service] = lambda: seats
    monkeypatch.setattr(pretargeting_router, "PretargetingService", _StubPretargetingService)
    monkeypatch.setattr(pretargeting_router, "PretargetingClient", _StubClient)
    _StubClient.built = []
    _StubPretargetingService.saved = []
    return SyncASGIClient(app)


@pytest.fixture
def seats(tmp_path):
    first = _account(tmp_path, "aaa-first")
    owner = _account(tmp_path, "zzz-owner")
    return _StubSeatsService(
        accounts=[first, owner],
        bidder_by_account={first.id: "bidder-A", owner.id: "bidder-B"},
        owner_by_bidder={"bidder-B": owner},
    )


def test_sync_with_billing_id_targets_the_owning_bidder(monkeypatch, seats):
    client = _build_client(monkeypatch, seats)

    response = client.post("/api/settings/pretargeting/sync?billing_id=198363911721")

    assert response.status_code == 200, response.text
    assert response.json()["bidder_id"] == "bidder-B"
    assert _StubClient.built == [{"credentials_path": seats.accounts[1].credentials_path, "account_id": "bidder-B"}]
    assert _StubPretargetingService.saved[0]["bidder_id"] == "bidder-B"
    assert "15000" in _StubPretargetingService.saved[0]["raw_config"]


def test_sync_without_billing_id_keeps_first_account_behaviour(monkeypatch, seats):
    client = _build_client(monkeypatch, seats)

    response = client.post("/api/settings/pretargeting/sync")

    assert response.status_code == 200, response.text
    assert response.json()["bidder_id"] == "bidder-A"
    assert _StubClient.built[0]["account_id"] == "bidder-A"


def test_sync_with_unknown_billing_id_is_404(monkeypatch, seats):
    client = _build_client(monkeypatch, seats)

    response = client.post("/api/settings/pretargeting/sync?billing_id=does-not-exist")

    assert response.status_code == 404
