"""HTTPException passthrough tests for performance routes."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.routers import performance as performance_router
from services.auth_service import User


def _allow_seat_admin():
    async def _allow():
        return User(id="admin-1", email="admin@example.com", role="read")

    return _allow


def test_import_csv_preserves_http_exception_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubUploadsRepository:
        async def start_ingestion_run(self, **kwargs):
            _ = kwargs
            raise HTTPException(status_code=409, detail="ingestion blocked")

        async def finish_ingestion_run(self, **kwargs):
            _ = kwargs

    app = FastAPI()
    app.include_router(performance_router.router, prefix="/api")
    app.dependency_overrides[performance_router.require_seat_admin_or_sudo] = _allow_seat_admin()
    monkeypatch.setattr(performance_router, "UploadsRepository", _StubUploadsRepository)

    client = TestClient(app)
    response = client.post(
        "/api/performance/import-csv",
        files={"file": ("sample.csv", b"Day,Creative ID\n2026-03-04,cr-1\n", "text/csv")},
    )

    assert response.status_code == 409
    assert "blocked" in response.json()["detail"].lower()
