"""RBAC tests for recommendations routes."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers import recommendations as rec_router
from services.auth_service import User


def _build_client(
    *,
    current_user_override=None,
    seat_admin_override=None,
) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(rec_router.router, prefix="/api")
    if current_user_override is not None:
        app.dependency_overrides[rec_router.get_current_user] = current_user_override
    if seat_admin_override is not None:
        app.dependency_overrides[rec_router.require_seat_admin_or_sudo] = (
            seat_admin_override
        )
    return SyncASGIClient(app)


async def _allow_user() -> User:
    return User(id="reader-1", email="reader@example.com", role="read")


async def _allow_seat_admin() -> User:
    return User(id="admin-1", email="admin@example.com", role="read")


def _assert_contained(response) -> None:
    assert response.status_code == 503
    assert response.json() == {
        "detail": rec_router.RECOMMENDATIONS_UNAVAILABLE_DETAIL,
    }


def test_recommendations_list_forbidden_when_not_authenticated() -> None:
    async def _deny_user():
        raise HTTPException(status_code=401, detail="Not authenticated")

    client = _build_client(current_user_override=_deny_user)
    response = client.get("/api/recommendations")

    assert response.status_code == 401


def test_resolve_recommendation_forbidden_without_seat_admin() -> None:
    async def _deny_seat_admin():
        raise HTTPException(
            status_code=403, detail="Admin access to at least one seat is required."
        )

    client = _build_client(seat_admin_override=_deny_seat_admin)
    response = client.post("/api/recommendations/rec-1/resolve")

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "path",
    [
        "/api/recommendations",
        "/api/recommendations/summary",
        "/api/recommendations/by-type/fraud_alert",
    ],
)
def test_recommendation_reads_fail_closed_for_authenticated_users(path: str) -> None:
    client = _build_client(current_user_override=_allow_user)
    response = client.get(path)

    _assert_contained(response)


def test_resolve_recommendation_fails_closed_with_seat_admin() -> None:
    client = _build_client(seat_admin_override=_allow_seat_admin)
    response = client.post(
        "/api/recommendations/rec-1/resolve", params={"notes": "done"}
    )

    _assert_contained(response)
