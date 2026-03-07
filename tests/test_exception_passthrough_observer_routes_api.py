"""HTTPException passthrough tests for observer/ops routes."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers import gmail as gmail_router
from api.routers import retention as retention_router
from api.routers import uploads as uploads_router
from services.auth_service import User


def _allow_user() -> User:
    return User(id="user-1", email="user@example.com", role="read")


def test_uploads_daily_grid_preserves_http_exception_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubUploadsService:
        async def get_daily_grid(
            self,
            *,
            days: int,
            expected_per_day: int,
            allowed_bidder_ids,
        ):
            _ = (days, expected_per_day, allowed_bidder_ids)
            raise HTTPException(status_code=409, detail="upload grid conflict")

    async def _allow_bidder_ids(*, user):
        _ = user
        return None

    app = FastAPI()
    app.include_router(uploads_router.router, prefix="/api")
    app.dependency_overrides[uploads_router.get_current_user] = _allow_user
    app.dependency_overrides[uploads_router.get_uploads_service] = _StubUploadsService
    monkeypatch.setattr(uploads_router, "get_allowed_bidder_ids", _allow_bidder_ids)

    client = SyncASGIClient(app)
    response = client.get("/api/uploads/daily-grid")

    assert response.status_code == 409
    assert "conflict" in response.json()["detail"].lower()


def test_gmail_status_preserves_http_exception_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubGmailService:
        def get_status(self):
            raise HTTPException(status_code=418, detail="status unavailable")

    app = FastAPI()
    app.include_router(gmail_router.router, prefix="/api")
    app.dependency_overrides[gmail_router.get_current_user] = _allow_user
    monkeypatch.setattr(gmail_router, "GmailService", _StubGmailService)

    client = SyncASGIClient(app)
    response = client.get("/api/gmail/status")

    assert response.status_code == 418
    assert "unavailable" in response.json()["detail"].lower()


def test_retention_stats_preserves_http_exception_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubRetentionService:
        async def get_storage_stats(self):
            raise HTTPException(status_code=503, detail="stats backend unavailable")

    app = FastAPI()
    app.include_router(retention_router.router, prefix="/api")
    monkeypatch.setattr(retention_router, "RetentionService", _StubRetentionService)

    client = SyncASGIClient(app)
    response = client.get("/api/retention/stats")

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()
