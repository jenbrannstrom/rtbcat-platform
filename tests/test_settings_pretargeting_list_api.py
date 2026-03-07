"""API tests for pretargeting list response shaping."""

from __future__ import annotations

import json
import sys
import types

import pytest

# Avoid optional Google API dependency while importing settings routers.
if "collectors" not in sys.modules:
    fake_collectors = types.ModuleType("collectors")
    fake_collectors.PretargetingClient = object
    sys.modules["collectors"] = fake_collectors

pytest.importorskip("fastapi")
from fastapi import FastAPI
from tests.support.asgi_client import SyncASGIClient

from api.routers.settings import pretargeting as pretargeting_router


class _StubPretargetingService:
    async def list_configs_for_buyer(
        self,
        buyer_id: str,
        limit: int | None = None,
        summary_only: bool = False,
    ):
        assert buyer_id == "buyer-1"
        assert limit is None
        assert summary_only is False
        return [
            {
                "config_id": "cfg-1",
                "bidder_id": "bidder-1",
                "billing_id": "1001",
                "display_name": "Config A",
                "user_name": None,
                "state": "ACTIVE",
                "included_formats": json.dumps(["HTML"]),
                "included_platforms": json.dumps(["PHONE"]),
                "included_sizes": json.dumps(["300x250"]),
                "included_geos": json.dumps(["US"]),
                "excluded_geos": json.dumps([]),
                "included_operating_systems": json.dumps(["30001", "30002"]),
                "raw_config": json.dumps({"maximumQps": "120"}),
                "synced_at": "2026-03-01T00:00:00+00:00",
            },
            {
                "config_id": "cfg-2",
                "bidder_id": "bidder-1",
                "billing_id": "1002",
                "display_name": "Config B",
                "user_name": "Manual Name",
                "state": "SUSPENDED",
                "included_formats": json.dumps(["VIDEO"]),
                "included_platforms": json.dumps(["TABLET"]),
                "included_sizes": json.dumps(["320x50"]),
                "included_geos": json.dumps(["GB"]),
                "excluded_geos": json.dumps([]),
                "included_operating_systems": None,
                "raw_config": {"maximumQps": "not-a-number"},
                "synced_at": None,
            },
        ]

    async def list_configs(
        self,
        bidder_id: str | None = None,
        limit: int | None = None,
        summary_only: bool = False,
    ):
        assert bidder_id == "bidder-1"
        assert limit is None
        assert summary_only is False
        return []


class _StubSeatsService:
    async def get_service_accounts(self, active_only: bool = True):
        return []

    async def get_bidder_id_for_service_account(self, service_account_id: str):
        return None

    async def get_first_bidder_id(self):
        return None


def _build_client(monkeypatch: pytest.MonkeyPatch) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(pretargeting_router.router, prefix="/api")
    app.dependency_overrides[pretargeting_router.get_current_user] = lambda: types.SimpleNamespace(
        id="u1",
        role="read",
        email="user@example.com",
    )
    app.dependency_overrides[pretargeting_router.get_seats_service] = lambda: _StubSeatsService()
    monkeypatch.setattr(
        pretargeting_router,
        "PretargetingService",
        lambda: _StubPretargetingService(),
    )
    return SyncASGIClient(app)


def test_pretargeting_list_includes_maximum_qps(monkeypatch: pytest.MonkeyPatch):
    client = _build_client(monkeypatch)

    response = client.get("/api/settings/pretargeting", params={"buyer_id": "buyer-1"})

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2

    assert rows[0]["billing_id"] == "1001"
    assert rows[0]["maximum_qps"] == 120
    assert rows[0]["included_operating_systems"] == ["iOS", "Android"]

    assert rows[1]["billing_id"] == "1002"
    assert rows[1]["maximum_qps"] is None
