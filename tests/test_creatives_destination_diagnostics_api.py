"""API tests for creative destination diagnostics endpoint."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import creatives as creatives_router


def _build_client(store: object) -> TestClient:
    app = FastAPI()
    app.include_router(creatives_router.router, prefix="/api")
    app.dependency_overrides[creatives_router.get_store] = lambda: store
    app.dependency_overrides[creatives_router.get_current_user] = lambda: SimpleNamespace(
        id="u1",
        role="sudo",
        email="admin@example.com",
    )
    return TestClient(app)


class _StoreWithCreative:
    def __init__(self, creative: object | None):
        self._creative = creative

    async def get_creative(self, creative_id: str):
        if not self._creative:
            return None
        return self._creative


def test_router_registers_destination_diagnostics_endpoint() -> None:
    routes = {route.path for route in creatives_router.router.routes}
    assert "/creatives/{creative_id}/destination-diagnostics" in routes


def test_destination_diagnostics_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    creative = SimpleNamespace(
        id="creative-1",
        buyer_id="1111111111",
        final_url="%%CLICK_URL_UNESC%%",
        display_url=None,
        raw_data={},
    )
    store = _StoreWithCreative(creative)

    captured: dict[str, str] = {}

    async def _require_buyer_access(buyer_id: str, store=None, user=None):
        captured["buyer_id"] = buyer_id

    def _build_diagnostics(_creative):
        return {
            "resolved_destination_url": "https://example.com/landing",
            "candidate_count": 3,
            "eligible_count": 1,
            "candidates": [
                {
                    "source": "final_url",
                    "url": "%%CLICK_URL_UNESC%%",
                    "eligible": False,
                    "reason": "contains_click_macro",
                },
                {
                    "source": "declared_click_through_url",
                    "url": "https://example.com/landing",
                    "eligible": True,
                    "reason": None,
                },
            ],
        }

    monkeypatch.setattr(creatives_router, "require_buyer_access", _require_buyer_access)
    monkeypatch.setattr(creatives_router, "build_creative_destination_diagnostics", _build_diagnostics)

    client = _build_client(store)
    response = client.get("/api/creatives/creative-1/destination-diagnostics")
    assert response.status_code == 200

    payload = response.json()
    assert payload["creative_id"] == "creative-1"
    assert payload["buyer_id"] == "1111111111"
    assert payload["resolved_destination_url"] == "https://example.com/landing"
    assert payload["candidate_count"] == 3
    assert payload["eligible_count"] == 1
    assert len(payload["candidates"]) == 2
    assert captured["buyer_id"] == "1111111111"


def test_destination_diagnostics_returns_404_for_missing_creative() -> None:
    store = _StoreWithCreative(None)
    client = _build_client(store)

    response = client.get("/api/creatives/missing-id/destination-diagnostics")
    assert response.status_code == 404
    assert response.json()["detail"] == "Creative not found"
