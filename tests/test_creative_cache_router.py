"""API tests for creative cache refresh scheduling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from api.routers import creative_cache as creative_cache_router
from tests.support.asgi_client import SyncASGIClient


class _Secrets:
    def get(self, key: str):
        if key == "CREATIVE_CACHE_REFRESH_SECRET":
            return "scheduler-secret"
        return None


def _build_client() -> SyncASGIClient:
    app = FastAPI()
    app.include_router(creative_cache_router.router, prefix="/api")
    app.dependency_overrides[creative_cache_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[creative_cache_router.get_config] = lambda: SimpleNamespace()
    return SyncASGIClient(app)


def test_scheduled_creative_cache_refresh_can_return_queued_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def _refresh_active_creatives(self, **kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(creative_cache_router, "get_secrets_manager", lambda: _Secrets())
    monkeypatch.setattr(
        creative_cache_router.CreativeCacheService,
        "refresh_active_creatives",
        _refresh_active_creatives,
    )

    client = _build_client()
    response = client.post(
        "/api/creatives/cache/refresh/scheduled"
        "?days=7&limit=1000&include_html_thumbnails=false&background=true",
        headers={"X-Creative-Cache-Refresh-Secret": "scheduler-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["queued"] is True
    assert payload["result"]["refreshed"] == 0
    assert calls == [
        {
            "days": 7,
            "limit": 1000,
            "include_html_thumbnails": False,
            "force_html_thumbnail_retry": False,
        }
    ]
