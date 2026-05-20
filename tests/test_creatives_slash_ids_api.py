"""Regression tests for creative IDs containing URL path characters."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from api.routers import creatives as creatives_router
from api.routers import creatives_live as creatives_live_router
from services.creatives_service import CreativeListContext
from storage.models import Creative
from tests.support.asgi_client import SyncASGIClient


class _Store:
    def __init__(self, creative: Creative):
        self.creative = creative
        self.requested_ids: list[str] = []
        self.saved: list[Creative] = []

    async def get_creative(self, creative_id: str):
        self.requested_ids.append(creative_id)
        return self.creative if creative_id == self.creative.id else None

    async def save_creatives(self, creatives):
        self.saved.extend(creatives)


def _creative(creative_id: str) -> Creative:
    return Creative(
        id=creative_id,
        name=f"buyers/6574658621/creatives/{creative_id}",
        format="HTML",
        account_id="6574658621",
        buyer_id="6574658621",
        approval_status="APPROVED",
        width=300,
        height=250,
    )


def _build_client(store: _Store) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(creatives_router.router, prefix="/api")
    app.include_router(creatives_live_router.router, prefix="/api")
    app.dependency_overrides[creatives_router.get_store] = lambda: store
    app.dependency_overrides[creatives_router.get_current_user] = lambda: SimpleNamespace(
        id="u1",
        role="sudo",
        email="admin@example.com",
    )
    app.dependency_overrides[creatives_live_router.get_store] = lambda: store
    app.dependency_overrides[creatives_live_router.get_current_user] = lambda: SimpleNamespace(
        id="u1",
        role="sudo",
        email="admin@example.com",
    )
    app.dependency_overrides[creatives_live_router.get_config] = lambda: SimpleNamespace()
    return SyncASGIClient(app)


def test_detail_route_accepts_encoded_slash_creative_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creative_id = "abc/def="
    store = _Store(_creative(creative_id))

    async def _get_list_context(*_args, **_kwargs):
        return CreativeListContext(
            thumbnail_statuses={},
            waste_flags={},
            country_data={},
            market_alerts={},
        )

    monkeypatch.setattr(creatives_router.creatives_service, "get_list_context", _get_list_context)

    client = _build_client(store)
    response = client.get("/api/creatives/detail/abc%2Fdef%3D")

    assert response.status_code == 200
    assert store.requested_ids == [creative_id]
    assert response.json()["id"] == creative_id


def test_live_route_accepts_encoded_slash_creative_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creative_id = "abc/def="
    store = _Store(_creative(creative_id))
    fetched: list[tuple[str, str, str]] = []

    async def _get_list_context(*_args, **_kwargs):
        return CreativeListContext(
            thumbnail_statuses={},
            waste_flags={},
            country_data={},
            market_alerts={},
        )

    class _Client:
        async def get_creative_by_id(self, creative_id: str, view: str, buyer_id: str):
            fetched.append((creative_id, view, buyer_id))
            return {
                "creativeId": creative_id,
                "creativeName": f"buyers/{buyer_id}/creatives/{creative_id}",
                "accountId": buyer_id,
                "buyerId": buyer_id,
                "format": "HTML",
                "approvalStatus": "APPROVED",
                "html": {"width": 300, "height": 250},
                "utmParams": {},
            }

    async def _resolve_live_client(self, creative):
        assert creative.id == creative_id
        return _Client()

    monkeypatch.setattr(
        creatives_live_router.creatives_service,
        "get_list_context",
        _get_list_context,
    )
    monkeypatch.setattr(
        creatives_live_router.CreativeCacheService,
        "resolve_live_client",
        _resolve_live_client,
    )

    client = _build_client(store)
    response = client.get(
        "/api/creatives/live/abc%2Fdef%3D?allow_cache_fallback=false&refresh_cache=true"
    )

    assert response.status_code == 200
    assert store.requested_ids == [creative_id]
    assert fetched == [(creative_id, "FULL", "6574658621")]
    assert store.saved and store.saved[0].id == creative_id
    payload = response.json()
    assert payload["source"] == "live"
    assert payload["creative"]["id"] == creative_id


def test_legacy_live_route_accepts_encoded_slash_creative_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creative_id = "abc/def="
    store = _Store(_creative(creative_id))

    async def _get_list_context(*_args, **_kwargs):
        return CreativeListContext(
            thumbnail_statuses={},
            waste_flags={},
            country_data={},
            market_alerts={},
        )

    class _Client:
        async def get_creative_by_id(self, creative_id: str, view: str, buyer_id: str):
            return {
                "creativeId": creative_id,
                "creativeName": f"buyers/{buyer_id}/creatives/{creative_id}",
                "accountId": buyer_id,
                "buyerId": buyer_id,
                "format": "HTML",
                "approvalStatus": "APPROVED",
                "html": {"width": 300, "height": 250},
                "utmParams": {},
            }

    async def _resolve_live_client(self, creative):
        assert creative.id == creative_id
        return _Client()

    monkeypatch.setattr(
        creatives_live_router.creatives_service,
        "get_list_context",
        _get_list_context,
    )
    monkeypatch.setattr(
        creatives_live_router.CreativeCacheService,
        "resolve_live_client",
        _resolve_live_client,
    )

    client = _build_client(store)
    response = client.get(
        "/api/creatives/abc%2Fdef%3D/live?allow_cache_fallback=false&refresh_cache=false"
    )

    assert response.status_code == 200
    assert response.json()["creative"]["id"] == creative_id
