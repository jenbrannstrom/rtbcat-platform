"""Regression tests for lazy native preview hydration on creative list pages."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from api.routers import creatives as creatives_router
from tests.support.asgi_client import SyncASGIClient


def _native_creative(*, raw_data):
    return SimpleNamespace(
        id="2004488961817030661",
        name="native-creative",
        format="NATIVE",
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
        seat_name=None,
        raw_data=raw_data,
    )


class _Store:
    def __init__(self):
        self.slim_creative = _native_creative(raw_data={})
        self.full_creative = _native_creative(
            raw_data={
                "native": {
                    "headline": "Temu",
                    "body": "Shop now",
                    "callToAction": "INSTALL",
                    "clickLinkUrl": "%%CLICK_URL_UNESC%%https://play.google.com/store/apps/details?id=test",
                    "image": {"url": "https://static.example.com/native-image.jpg"},
                    "logo": {"url": "https://static.example.com/native-logo.webp"},
                }
            }
        )

    async def get_creative_count(self, **_kwargs):
        return 1

    async def list_creatives(self, **_kwargs):
        return [self.slim_creative]

    async def get_thumbnail_statuses(self, creative_ids: list[str]):
        return {
            creative_id: {
                "status": None,
                "error_reason": None,
                "thumbnail_url": None,
                "updated_at": None,
            }
            for creative_id in creative_ids
        }

    async def process_html_thumbnails(
        self,
        limit: int = 100,
        force_retry: bool = False,
        creative_ids: list[str] | None = None,
    ):
        _ = (limit, force_retry, creative_ids)
        return {"processed": 0, "success": 0, "failed": 0, "no_image_found": 0}

    async def get_creatives_by_ids(self, creative_ids: list[str]):
        assert creative_ids == ["2004488961817030661"]
        return [self.full_creative]


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


def test_paginated_creatives_lazily_hydrate_native_previews(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()

    async def _resolve_buyer_id(buyer_id, store=None, user=None):
        _ = (store, user)
        return buyer_id

    monkeypatch.setattr(creatives_router, "resolve_buyer_id", _resolve_buyer_id)

    client = _build_client(store)
    response = client.get(
        "/api/creatives/v2?buyer_id=1487810529&limit=1&offset=0&slim=true&format=NATIVE"
    )

    assert response.status_code == 200
    payload = response.json()
    native = payload["data"][0]["native"]
    assert native["image"]["url"] == "https://static.example.com/native-image.jpg"
    assert native["logo"]["url"] == "https://static.example.com/native-logo.webp"

