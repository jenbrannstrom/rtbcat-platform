"""API tests for pretargeting detail response shaping."""

from __future__ import annotations

import types

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from tests.support.asgi_client import SyncASGIClient

from api.routers.settings import changes as changes_router


class _StubPretargetingService:
    async def get_config(self, billing_id: str):
        assert billing_id == "1001"
        return {
            "config_id": "cfg-1",
            "bidder_id": "bidder-1",
            "display_name": "Config A",
            "user_name": None,
            "state": "ACTIVE",
            "included_formats": ["HTML"],
            "included_platforms": ["PHONE"],
            "included_sizes": ["300x250"],
            "included_geos": ["2840"],
            "excluded_geos": [],
            "raw_config": {
                "publisherTargeting": {"targetingMode": "INCLUSIVE", "values": []},
                "maximumQps": "120",
            },
            "synced_at": "2026-03-01T00:00:00+00:00",
        }


class _StubChangesService:
    async def list_pending_changes(
        self,
        billing_id: str,
        status: str,
        limit: int,
    ):
        assert billing_id == "1001"
        assert status == "pending"
        assert limit == 500
        return [
            {
                "id": 7,
                "billing_id": "1001",
                "config_id": "cfg-1",
                "change_type": "add_geo",
                "field_name": "included_geos",
                "value": "2124",
                "reason": None,
                "estimated_qps_impact": None,
                "created_at": "2026-03-01T00:00:00+00:00",
                "created_by": "user@example.com",
                "status": "pending",
            }
        ]


class _StubBidstreamRepo:
    async def get_country_codes_for_geo_ids(self, geo_ids: list[str]):
        assert geo_ids == ["2124", "2840"]
        return ["CA", "US"]


def _build_client(monkeypatch: pytest.MonkeyPatch) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(changes_router.router, prefix="/api")
    app.dependency_overrides[changes_router.get_current_user] = lambda: types.SimpleNamespace(
        id="u1",
        role="read",
        email="user@example.com",
    )
    monkeypatch.setattr(
        changes_router,
        "PretargetingService",
        lambda: _StubPretargetingService(),
    )
    monkeypatch.setattr(
        changes_router,
        "ChangesService",
        lambda: _StubChangesService(),
    )
    monkeypatch.setattr(
        changes_router,
        "RtbBidstreamRepository",
        lambda: _StubBidstreamRepo(),
    )
    return SyncASGIClient(app)


def test_pretargeting_detail_includes_effective_geo_country_codes(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _build_client(monkeypatch)

    response = client.get("/api/settings/pretargeting/1001/detail")

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_geos"] == ["2124", "2840"]
    assert payload["effective_geo_country_codes"] == ["CA", "US"]
