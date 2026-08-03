"""Buyer-authorization tests for recommendation routes."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException

from analytics.recommendation_data import RecommendationDataUnavailable
from api.routers import recommendations as rec_router
from services.auth_service import User
from tests.support.asgi_client import SyncASGIClient


def _build_client(*, current_user_override=None) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(rec_router.router, prefix="/api")
    if current_user_override is not None:
        app.dependency_overrides[rec_router.get_current_user] = current_user_override
    app.dependency_overrides[rec_router.get_store] = lambda: object()
    return SyncASGIClient(app)


async def _allow_user() -> User:
    return User(id="reader-1", email="reader@example.com", role="read")


async def _allow_sudo() -> User:
    return User(id="sudo-1", email="sudo@example.com", role="sudo")


def test_recommendations_list_forbidden_when_not_authenticated() -> None:
    async def _deny_user():
        raise HTTPException(status_code=401, detail="Not authenticated")

    response = _build_client(current_user_override=_deny_user).get(
        "/api/recommendations",
        params={"buyer_id": "buyer-a"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/recommendations",
        "/api/recommendations/summary",
        "/api/recommendations/by-type/fraud_alert",
    ],
)
def test_recommendation_reads_require_resolved_buyer(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    async def _no_global_scope(_buyer_id, *, store, user):
        return None

    monkeypatch.setattr(rec_router, "resolve_buyer_id", _no_global_scope)
    response = _build_client(current_user_override=_allow_user).get(path)

    assert response.status_code == 400
    assert response.json() == {
        "detail": "buyer_id is required for recommendation endpoints."
    }


def test_recommendation_read_uses_authorized_buyer_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    async def _resolve(buyer_id, *, store, user):
        calls["resolver_buyer"] = buyer_id
        return "buyer-a"

    class FakeService:
        def __init__(self, store):
            calls["store"] = store

        async def generate(self, **kwargs):
            calls["generate"] = kwargs
            return []

    monkeypatch.setattr(rec_router, "resolve_buyer_id", _resolve)
    monkeypatch.setattr(rec_router, "RecommendationsService", FakeService)

    response = _build_client(current_user_override=_allow_user).get(
        "/api/recommendations",
        params={"buyer_id": "buyer-a", "days": 14, "min_severity": "high"},
    )

    assert response.status_code == 200
    assert response.json() == []
    assert calls["resolver_buyer"] == "buyer-a"
    assert calls["generate"] == {
        "buyer_id": "buyer-a",
        "days": 14,
        "min_severity": "high",
    }


def test_sudo_must_choose_an_explicit_buyer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeService:
        def __init__(self, store):
            pass

        async def generate(self, **kwargs):
            return []

    monkeypatch.setattr(rec_router, "RecommendationsService", FakeService)
    client = _build_client(current_user_override=_allow_sudo)

    missing = client.get("/api/recommendations")
    explicit = client.get(
        "/api/recommendations",
        params={"buyer_id": "buyer-a"},
    )

    assert missing.status_code == 400
    assert missing.json() == {
        "detail": "buyer_id is required for recommendation endpoints."
    }
    assert explicit.status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/recommendations",
        "/api/recommendations/summary",
        "/api/recommendations/by-type/fraud_alert",
    ],
)
def test_recommendation_reads_preserve_other_buyer_access_denial(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    async def _deny(_buyer_id, *, store, user):
        raise HTTPException(status_code=403, detail="No access")

    monkeypatch.setattr(rec_router, "resolve_buyer_id", _deny)
    response = _build_client(current_user_override=_allow_user).get(
        path, params={"buyer_id": "buyer-b"}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "No access"}


def test_missing_buyer_metrics_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _resolve(buyer_id, *, store, user):
        return buyer_id

    class FakeService:
        def __init__(self, store):
            pass

        async def generate(self, **kwargs):
            raise RecommendationDataUnavailable("missing")

    monkeypatch.setattr(rec_router, "resolve_buyer_id", _resolve)
    monkeypatch.setattr(rec_router, "RecommendationsService", FakeService)

    response = _build_client(current_user_override=_allow_user).get(
        "/api/recommendations",
        params={"buyer_id": "buyer-a"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": rec_router.RECOMMENDATION_DATA_UNAVAILABLE_DETAIL
    }


def test_resolve_is_scoped_to_administered_buyer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    async def _resolve_admin(buyer_id, *, store, user):
        calls["resolver_buyer"] = buyer_id
        return "buyer-a"

    class FakeService:
        def __init__(self, store):
            pass

        async def resolve(self, **kwargs):
            calls["resolve"] = kwargs
            return True

    monkeypatch.setattr(rec_router, "resolve_admin_buyer_id", _resolve_admin)
    monkeypatch.setattr(rec_router, "RecommendationsService", FakeService)

    response = _build_client(current_user_override=_allow_user).post(
        "/api/recommendations/rec-1/resolve",
        params={"buyer_id": "buyer-a", "notes": "done"},
    )

    assert response.status_code == 200
    assert calls["resolver_buyer"] == "buyer-a"
    assert calls["resolve"] == {
        "buyer_id": "buyer-a",
        "recommendation_id": "rec-1",
        "notes": "done",
    }


def test_resolve_cannot_find_another_buyers_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _resolve_admin(buyer_id, *, store, user):
        return buyer_id

    class FakeService:
        def __init__(self, store):
            pass

        async def resolve(self, **kwargs):
            return False

    monkeypatch.setattr(rec_router, "resolve_admin_buyer_id", _resolve_admin)
    monkeypatch.setattr(rec_router, "RecommendationsService", FakeService)

    response = _build_client(current_user_override=_allow_user).post(
        "/api/recommendations/shared-id/resolve",
        params={"buyer_id": "buyer-b"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Recommendation not found"}
