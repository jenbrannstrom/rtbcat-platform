"""API tests for creative language mismatch endpoint."""

from __future__ import annotations

from datetime import datetime, UTC
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from api.routers import creative_language as creative_language_router
from tests.support.asgi_client import SyncASGIClient


class _StoreWithCreative:
    async def get_creative(self, creative_id: str):
        return SimpleNamespace(
            id=creative_id,
            buyer_id="1487810529",
            detected_language=None,
            detected_language_code=None,
        )


def _build_client() -> SyncASGIClient:
    app = FastAPI()
    app.include_router(creative_language_router.router, prefix="/api")
    app.dependency_overrides[creative_language_router.get_store] = lambda: _StoreWithCreative()
    app.dependency_overrides[creative_language_router.get_current_user] = lambda: SimpleNamespace(
        id="u1",
        role="sudo",
        email="admin@example.com",
    )
    return SyncASGIClient(app)


def test_geo_mismatch_response_exposes_language_and_currency_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _require_buyer_access(buyer_id: str, store=None, user=None):
        _ = (buyer_id, store, user)
        return None

    async def _get_geo_mismatch(creative, days: int):
        _ = (creative, days)
        return {
            "has_mismatch": True,
            "alert": {
                "severity": "error",
                "category": "currency",
                "language": None,
                "language_code": "en",
                "mismatched_countries": ["PH"],
                "expected_countries": [],
                "message": "Currency AED conflicts with PHL",
            },
            "serving_countries": ["PH"],
            "detected_currencies": ["AED"],
            "language_flag_status": "orange",
            "language_flag_reason": "English creative serving in PHL",
            "language_flag_source": "heuristic",
            "effective_language_code": "en",
            "heuristic_language_code": "en",
            "currency_flag_status": "red",
            "currency_flag_reason": "Currency AED conflicts with PHL",
            "geo_linguistic_status": "red",
            "geo_linguistic_reason": "Currency AED conflicts with PHL (heuristic)",
            "geo_linguistic_decision": "heuristic_currency_mismatch",
            "geo_linguistic_completed_at": None,
        }

    monkeypatch.setattr(creative_language_router, "require_buyer_access", _require_buyer_access)
    monkeypatch.setattr(
        creative_language_router.language_service,
        "get_geo_mismatch",
        _get_geo_mismatch,
    )

    client = _build_client()
    response = client.get("/api/creatives/creative-1/geo-mismatch")

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_mismatch"] is True
    assert payload["alert"]["category"] == "currency"
    assert payload["language_flag_status"] == "orange"
    assert payload["currency_flag_status"] == "red"
    assert payload["geo_linguistic_status"] == "red"
    assert payload["detected_currencies"] == ["AED"]


def test_geo_mismatch_response_serializes_completed_at_datetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _require_buyer_access(buyer_id: str, store=None, user=None):
        _ = (buyer_id, store, user)
        return None

    completed_at = datetime(2026, 4, 14, 19, 40, 21, tzinfo=UTC)

    async def _get_geo_mismatch(creative, days: int):
        _ = (creative, days)
        return {
            "has_mismatch": True,
            "alert": None,
            "serving_countries": ["IN"],
            "detected_currencies": [],
            "language_flag_status": "red",
            "language_flag_reason": "Spanish CTA 'instalar' mixed into English creative serving in IND",
            "language_flag_source": "plaintext_fields",
            "effective_language_code": "en",
            "heuristic_language_code": None,
            "plaintext_language_summary": "Primary plaintext: English · CTA: Spanish ('instalar')",
            "primary_text_language": "English",
            "primary_text_language_code": "en",
            "secondary_text_language": "Spanish",
            "secondary_text_language_code": "es",
            "secondary_text_sample": "instalar",
            "currency_flag_status": "orange",
            "currency_flag_reason": "No obvious market currency detected",
            "geo_linguistic_status": "orange",
            "geo_linguistic_reason": "Spanish CTA mixed into English copy",
            "geo_linguistic_decision": "needs_review",
            "geo_linguistic_completed_at": completed_at,
        }

    monkeypatch.setattr(creative_language_router, "require_buyer_access", _require_buyer_access)
    monkeypatch.setattr(
        creative_language_router.language_service,
        "get_geo_mismatch",
        _get_geo_mismatch,
    )

    client = _build_client()
    response = client.get("/api/creatives/creative-1/geo-mismatch")

    assert response.status_code == 200
    payload = response.json()
    assert payload["geo_linguistic_completed_at"] == "2026-04-14T19:40:21Z"
    assert payload["plaintext_language_summary"] == (
        "Primary plaintext: English · CTA: Spanish ('instalar')"
    )
