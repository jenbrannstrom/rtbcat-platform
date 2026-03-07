"""RBAC tests for /analytics/home/refresh."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers.analytics import home as home_router
from services.auth_service import User


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    require_admin_override,
    refresh_impl,
) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(home_router.router, prefix="/api")
    app.dependency_overrides[home_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[home_router.require_admin] = require_admin_override

    async def _resolve_buyer_id(
        buyer_id: str | None,
        store=None,
        user=None,
    ) -> str | None:
        _ = (store, user)
        return buyer_id

    monkeypatch.setattr(home_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(home_router, "refresh_home_summaries", refresh_impl)
    return SyncASGIClient(app)


def test_refresh_home_cache_forbidden_when_require_admin_denies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _deny_admin():
        raise HTTPException(status_code=403, detail="Sudo access required")

    async def _refresh_home_summaries(**kwargs):
        _ = kwargs
        return {"status": "ok"}

    client = _build_client(
        monkeypatch=monkeypatch,
        require_admin_override=_deny_admin,
        refresh_impl=_refresh_home_summaries,
    )

    response = client.post(
        "/api/analytics/home/refresh",
        params={"days": 7, "buyer_id": "1111111111"},
    )
    assert response.status_code == 403
    assert "sudo" in response.json()["detail"].lower()


def test_refresh_home_cache_calls_refresh_when_require_admin_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh_calls: dict[str, object] = {}
    home_cache_clear_calls = {"count": 0}
    spend_cache_clear_calls = {"count": 0}

    async def _allow_admin():
        return User(id="sudo-1", email="sudo@example.com", role="sudo")

    async def _refresh_home_summaries(**kwargs):
        refresh_calls.update(kwargs)
        return {"status": "ok"}

    def _clear_home_payload_caches() -> None:
        home_cache_clear_calls["count"] += 1

    def _clear_spend_stats_cache() -> None:
        spend_cache_clear_calls["count"] += 1

    monkeypatch.setattr(
        home_router.HomeAnalyticsService,
        "clear_payload_caches",
        staticmethod(_clear_home_payload_caches),
    )
    monkeypatch.setattr(
        home_router.AnalyticsService,
        "clear_spend_stats_cache",
        staticmethod(_clear_spend_stats_cache),
    )

    client = _build_client(
        monkeypatch=monkeypatch,
        require_admin_override=_allow_admin,
        refresh_impl=_refresh_home_summaries,
    )

    response = client.post(
        "/api/analytics/home/refresh",
        params={"days": 14, "buyer_id": "1111111111"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert refresh_calls == {"buyer_account_id": "1111111111", "days": 14}
    assert home_cache_clear_calls["count"] == 1
    assert spend_cache_clear_calls["count"] == 1
