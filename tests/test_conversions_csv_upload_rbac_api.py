"""RBAC tests for /conversions/csv/upload."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers import conversions as conversions_router
from services.auth_service import User


_LAST_INGEST_KWARGS: dict = {}


def _mock_auth_svc(admin_buyer_ids: list[str]):
    svc = MagicMock()
    svc.get_user_buyer_seat_ids = AsyncMock(
        side_effect=lambda uid, min_access_level="read": (
            admin_buyer_ids if min_access_level == "admin" else admin_buyer_ids
        )
    )
    return svc


class _StubConversionIngestionService:
    async def ingest_csv(self, csv_text: str, source_type: str, buyer_id_override=None):
        _LAST_INGEST_KWARGS.clear()
        _LAST_INGEST_KWARGS["buyer_id_override"] = buyer_id_override
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
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc(["1111111111"])):
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


def test_csv_upload_denied_for_other_buyer_seat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin of seat 2222222222 cannot import into seat 1111111111."""

    async def _allow_seat_admin():
        return User(id="admin-2", email="admin2@example.com", role="read")

    client = _build_client(monkeypatch, _allow_seat_admin)
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc(["2222222222"])):
        response = client.post(
            "/api/conversions/csv/upload",
            data={"source_type": "manual_csv", "buyer_id": "1111111111"},
            files={"file": ("events.csv", io.BytesIO(b"event_type,event_ts\npurchase,2026-03-04T00:00:00Z\n"), "text/csv")},
        )

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


def test_csv_upload_pins_buyer_override_so_rows_cannot_choose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-sudo caller is always pinned to their own seat.

    Without an override the ingestion service falls back to per-row
    buyer_id/buyer_account_id, which is how a caller could pick the victim.
    """

    async def _allow_seat_admin():
        return User(id="admin-3", email="admin3@example.com", role="read")

    client = _build_client(monkeypatch, _allow_seat_admin)
    with patch("api.dependencies.get_auth_service", return_value=_mock_auth_svc(["3333333333"])):
        response = client.post(
            "/api/conversions/csv/upload",
            data={"source_type": "manual_csv"},
            files={"file": ("events.csv", io.BytesIO(b"event_type,event_ts\npurchase,2026-03-04T00:00:00Z\n"), "text/csv")},
        )

    assert response.status_code == 200
    assert _LAST_INGEST_KWARGS["buyer_id_override"] == "3333333333"
