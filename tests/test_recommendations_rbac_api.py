"""RBAC tests for recommendations routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.routers import recommendations as rec_router
from services.auth_service import User


class _StubRecommendationsService:
    def __init__(self, store):
        _ = store

    async def generate(self, days: int, min_severity: str):
        _ = (days, min_severity)
        return []

    async def summary(self, days: int):
        _ = days
        return {
            "analysis_period_days": 7,
            "total_queries": 0,
            "total_impressions": 0,
            "total_waste_queries": 0,
            "total_waste_rate": 0.0,
            "total_wasted_qps": 0.0,
            "total_spend_usd": 0.0,
            "recommendation_count": {"low": 0, "medium": 0, "high": 0, "critical": 0},
            "total_recommendations": 0,
            "generated_at": "2026-03-04T00:00:00Z",
        }

    async def resolve(self, recommendation_id: str, notes=None):
        _ = (recommendation_id, notes)
        return True

    async def by_type(self, rec_type: str, days: int):
        _ = (rec_type, days)
        return []


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    current_user_override=None,
    seat_admin_override=None,
) -> TestClient:
    app = FastAPI()
    app.include_router(rec_router.router, prefix="/api")
    app.dependency_overrides[rec_router.get_store] = lambda: SimpleNamespace()
    if current_user_override is not None:
        app.dependency_overrides[rec_router.get_current_user] = current_user_override
    if seat_admin_override is not None:
        app.dependency_overrides[rec_router.require_seat_admin_or_sudo] = seat_admin_override
    monkeypatch.setattr(rec_router, "RecommendationsService", _StubRecommendationsService)
    return TestClient(app)


def test_recommendations_list_forbidden_when_not_authenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _deny_user():
        raise HTTPException(status_code=401, detail="Not authenticated")

    client = _build_client(monkeypatch, current_user_override=_deny_user)
    response = client.get("/api/recommendations")

    assert response.status_code == 401


def test_resolve_recommendation_forbidden_without_seat_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _deny_seat_admin():
        raise HTTPException(status_code=403, detail="Admin access to at least one seat is required.")

    client = _build_client(monkeypatch, seat_admin_override=_deny_seat_admin)
    response = client.post("/api/recommendations/rec-1/resolve")

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_resolve_recommendation_allows_with_seat_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow_seat_admin():
        return User(id="admin-1", email="admin@example.com", role="read")

    client = _build_client(monkeypatch, seat_admin_override=_allow_seat_admin)
    response = client.post("/api/recommendations/rec-1/resolve", params={"notes": "done"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "resolved"
    assert payload["id"] == "rec-1"
