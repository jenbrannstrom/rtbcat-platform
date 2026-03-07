"""RBAC tests for /conversions/csv/upload."""

from __future__ import annotations

import io

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers import conversions as conversions_router
from services.auth_service import User


class _StubConversionIngestionService:
    async def ingest_csv(self, csv_text: str, source_type: str, buyer_id_override=None):
        _ = (csv_text, source_type, buyer_id_override)
        return {
            "accepted": True,
            "source_type": source_type,
            "import_batch_id": "batch-1",
            "rows_read": 1,
            "rows_inserted": 1,
            "rows_duplicate": 0,
            "rows_skipped": 0,
            "errors": [],
        }


def _build_client(monkeypatch: pytest.MonkeyPatch, seat_admin_override) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(conversions_router.router, prefix="/api")
    app.dependency_overrides[conversions_router.require_seat_admin_or_sudo] = seat_admin_override
    monkeypatch.setattr(conversions_router, "ConversionIngestionService", _StubConversionIngestionService)
    return SyncASGIClient(app)


def test_csv_upload_forbidden_without_seat_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _deny_seat_admin():
        raise HTTPException(status_code=403, detail="Admin access to at least one seat is required.")

    client = _build_client(monkeypatch, _deny_seat_admin)
    response = client.post(
        "/api/conversions/csv/upload",
        data={"source_type": "manual_csv", "buyer_id": "1111111111"},
        files={"file": ("events.csv", io.BytesIO(b"event_type,event_ts\npurchase,2026-03-04T00:00:00Z\n"), "text/csv")},
    )

    assert response.status_code == 403
    assert "admin access" in response.json()["detail"].lower()


def test_csv_upload_allows_with_seat_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow_seat_admin():
        return User(id="admin-1", email="admin@example.com", role="read")

    client = _build_client(monkeypatch, _allow_seat_admin)
    response = client.post(
        "/api/conversions/csv/upload",
        data={"source_type": "manual_csv", "buyer_id": "1111111111"},
        files={"file": ("events.csv", io.BytesIO(b"event_type,event_ts\npurchase,2026-03-04T00:00:00Z\n"), "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_type"] == "manual_csv"
    assert payload["accepted"] is True
    assert payload["rows_inserted"] == 1
    assert payload["rows_duplicate"] == 0
