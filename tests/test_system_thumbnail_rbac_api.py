"""RBAC tests for thumbnail mutation endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.routers import system as system_router
from services.auth_service import User


class _StubStore:
    async def process_html_thumbnails(self, limit: int, force_retry: bool):
        _ = (limit, force_retry)
        return {
            "processed": 1,
            "success": 1,
            "failed": 0,
            "no_image_found": 0,
            "message": "ok",
        }


class _StubThumbnailsService:
    def check_ffmpeg(self) -> bool:
        return True

    async def generate_thumbnail(self, creative_id: str):
        return SimpleNamespace(
            creative_id=creative_id,
            status="success",
            error_reason=None,
            thumbnail_url="https://example.com/thumb.jpg",
        )

    async def generate_batch(self, limit: int, force: bool):
        _ = (limit, force)
        return [
            SimpleNamespace(
                creative_id="c1",
                status="success",
                error_reason=None,
                thumbnail_url="https://example.com/t1.jpg",
            )
        ]


def _build_client(monkeypatch: pytest.MonkeyPatch, seat_admin_override) -> TestClient:
    app = FastAPI()
    app.include_router(system_router.router, prefix="/api")
    app.dependency_overrides[system_router.get_store] = _StubStore
    app.dependency_overrides[system_router.require_seat_admin_or_sudo] = seat_admin_override
    monkeypatch.setattr(system_router, "ThumbnailsService", _StubThumbnailsService)
    return TestClient(app)


def test_generate_thumbnail_forbidden_without_seat_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _deny_seat_admin():
        raise HTTPException(status_code=403, detail="Admin access to at least one seat is required.")

    client = _build_client(monkeypatch, _deny_seat_admin)
    response = client.post("/api/thumbnails/generate", json={"creative_id": "c1"})

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_generate_thumbnail_allows_with_seat_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow_seat_admin():
        return User(id="admin-1", email="admin@example.com", role="read")

    client = _build_client(monkeypatch, _allow_seat_admin)
    response = client.post("/api/thumbnails/generate", json={"creative_id": "c1"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["creative_id"] == "c1"
    assert payload["status"] == "success"


def test_generate_batch_forbidden_without_seat_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _deny_seat_admin():
        raise HTTPException(status_code=403, detail="Admin access to at least one seat is required.")

    client = _build_client(monkeypatch, _deny_seat_admin)
    response = client.post("/api/thumbnails/generate-batch", json={"limit": 1, "force": False})

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_extract_html_forbidden_without_seat_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _deny_seat_admin():
        raise HTTPException(status_code=403, detail="Admin access to at least one seat is required.")

    client = _build_client(monkeypatch, _deny_seat_admin)
    response = client.post("/api/thumbnails/extract-html", json={"limit": 1, "force_retry": False})

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()
