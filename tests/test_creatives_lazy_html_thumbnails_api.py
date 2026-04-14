"""Regression tests for lazy HTML thumbnail backfill on creative list pages."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from api.routers import creatives as creatives_router
from tests.support.asgi_client import SyncASGIClient


def _creative(**overrides):
    base = dict(
        id="2013591677579276290",
        name="creative",
        format="HTML",
        account_id=None,
        buyer_id="1487810529",
        approval_status="APPROVED",
        width=300,
        height=250,
        final_url="https://play.google.com/store/apps/details?id=test",
        display_url="https://play.google.com/store/apps/details?id=test",
        utm_source=None,
        utm_medium=None,
        utm_campaign=None,
        utm_content=None,
        utm_term=None,
        advertiser_name=None,
        campaign_id=None,
        cluster_id=None,
        app_id=None,
        app_name=None,
        app_store=None,
        disapproval_reasons=None,
        serving_restrictions=None,
        detected_language=None,
        detected_language_code=None,
        language_confidence=None,
        language_source=None,
        language_analyzed_at=None,
        language_analysis_error=None,
        updated_at=None,
        raw_data=None,
        seat_name=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _Store:
    def __init__(self):
        self._processed_ids: list[str] = []
        self.creatives = [_creative()]

    async def get_creative_count(self, **_kwargs):
        return 1

    async def list_creatives(self, **_kwargs):
        return self.creatives

    async def get_thumbnail_statuses(self, creative_ids: list[str]):
        rows = {}
        for creative_id in creative_ids:
            if creative_id in self._processed_ids:
                rows[creative_id] = {
                    "status": "success",
                    "error_reason": None,
                    "thumbnail_url": "https://static.example.com/thumb.jpg",
                    "updated_at": None,
                }
        return rows

    async def process_html_thumbnails(
        self,
        limit: int = 100,
        force_retry: bool = False,
        creative_ids: list[str] | None = None,
    ):
        assert limit == 1
        assert force_retry is False
        assert creative_ids == ["2013591677579276290"]
        self._processed_ids.extend(creative_ids or [])
        return {
            "processed": 1,
            "success": 1,
            "failed": 0,
            "no_image_found": 0,
            "message": "ok",
        }


def _build_client(store: object) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(creatives_router.router, prefix="/api")
    app.dependency_overrides[creatives_router.get_store] = lambda: store
    app.dependency_overrides[creatives_router.get_current_user] = lambda: SimpleNamespace(
        id="u1",
        role="sudo",
        email="admin@example.com",
    )
    return SyncASGIClient(app)


def test_paginated_creatives_lazily_backfill_missing_html_thumbnails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()

    async def _resolve_buyer_id(buyer_id, store=None, user=None):
        _ = (store, user)
        return buyer_id

    monkeypatch.setattr(creatives_router, "resolve_buyer_id", _resolve_buyer_id)

    client = _build_client(store)
    response = client.get(
        "/api/creatives/v2?buyer_id=1487810529&limit=1&offset=0&slim=true"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["id"] == "2013591677579276290"
    assert payload["data"][0]["html"]["thumbnail_url"] == "https://static.example.com/thumb.jpg"

