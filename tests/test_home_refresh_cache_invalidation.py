"""Tests for Home refresh endpoint cache invalidation behavior."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from api.routers.analytics import home as home_router
from services.auth_service import User


@pytest.mark.asyncio
async def test_refresh_home_cache_clears_home_payload_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    refresh_calls: dict[str, object] = {}
    cache_clear_calls = {"count": 0}

    async def _stub_resolve_buyer_id(
        _buyer_id: str | None,
        store=None,
        user=None,
    ) -> str:
        del store, user
        return "buyer-resolved"

    async def _stub_refresh_home_summaries(**kwargs):
        refresh_calls.update(kwargs)
        return {"status": "ok"}

    def _stub_clear_payload_caches() -> None:
        cache_clear_calls["count"] += 1

    monkeypatch.setattr(home_router, "resolve_buyer_id", _stub_resolve_buyer_id)
    monkeypatch.setattr(home_router, "refresh_home_summaries", _stub_refresh_home_summaries)
    monkeypatch.setattr(
        home_router.HomeAnalyticsService,
        "clear_payload_caches",
        staticmethod(_stub_clear_payload_caches),
    )

    result = await home_router.refresh_home_cache(
        start_date=None,
        end_date=None,
        dates=None,
        days=14,
        buyer_id="buyer-requested",
        store=object(),
        user=User(id="u1", email="sudo@example.com", role="sudo"),
    )

    assert result == {"status": "ok"}
    assert refresh_calls["buyer_account_id"] == "buyer-resolved"
    assert refresh_calls["days"] == 14
    assert cache_clear_calls["count"] == 1
