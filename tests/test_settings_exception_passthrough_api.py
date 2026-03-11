"""HTTPException passthrough tests for settings routes."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from tests.support.asgi_client import SyncASGIClient

from api.routers.settings import actions as actions_router
from api.routers.settings import changes as changes_router
from services.auth_service import User


def _allow_seat_admin():
    async def _allow():
        return User(id="admin-1", email="admin@example.com", role="read")

    return _allow


def test_actions_apply_all_preserves_http_exception_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubActionsService:
        async def apply_all_pending_changes(self, billing_id: str, dry_run: bool):
            _ = (billing_id, dry_run)
            raise HTTPException(status_code=409, detail="conflict from service")

    app = FastAPI()
    app.include_router(actions_router.router, prefix="/api")
    app.dependency_overrides[actions_router.require_seat_admin_or_sudo] = _allow_seat_admin()
    monkeypatch.setattr(actions_router, "ActionsService", _StubActionsService)

    client = SyncASGIClient(app)
    response = client.post("/api/settings/pretargeting/123/apply-all")

    assert response.status_code == 409
    assert "conflict" in response.json()["detail"].lower()


def test_changes_create_pending_change_preserves_not_found_http_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubChangesService:
        async def list_pending_changes(self, billing_id: str, status: str, limit: int):
            _ = (billing_id, status, limit)
            return []

        async def create_pending_change(self, **kwargs):
            _ = kwargs
            return 1

        async def get_pending_change(self, _change_id: int):
            return {
                "id": 1,
                "billing_id": "123",
                "config_id": "cfg-1",
                "change_type": "add_size",
                "field_name": "included_sizes",
                "value": "300x250",
                "reason": "test",
                "estimated_qps_impact": None,
                "created_at": "2026-03-04T00:00:00Z",
                "created_by": "ui",
                "status": "pending",
            }

    class _StubPretargetingService:
        async def get_config(self, _billing_id: str):
            return None

        async def list_pending_publisher_changes(self, _billing_id: str):
            return []

        async def add_history(self, **kwargs):
            _ = kwargs

    app = FastAPI()
    app.include_router(changes_router.router, prefix="/api")
    app.dependency_overrides[changes_router.require_seat_admin_or_sudo] = _allow_seat_admin()
    monkeypatch.setattr(changes_router, "ChangesService", _StubChangesService)
    monkeypatch.setattr(changes_router, "PretargetingService", _StubPretargetingService)

    client = SyncASGIClient(app)
    response = client.post(
        "/api/settings/pretargeting/pending-change",
        json={
            "billing_id": "123",
            "change_type": "add_size",
            "field_name": "included_sizes",
            "value": "300x250",
            "reason": "test",
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_changes_discard_all_preserves_http_exception_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubChangesService:
        async def cancel_pending_changes_for_billing(self, billing_id: str):
            _ = billing_id
            raise HTTPException(status_code=409, detail="discard conflict")

    class _StubPretargetingService:
        async def get_config(self, _billing_id: str):
            return {"billing_id": "123", "config_id": "cfg-1"}

        async def discard_pending_publisher_changes(self, _billing_id: str):
            return 0

    app = FastAPI()
    app.include_router(changes_router.router, prefix="/api")
    app.dependency_overrides[changes_router.require_seat_admin_or_sudo] = _allow_seat_admin()
    monkeypatch.setattr(changes_router, "ChangesService", _StubChangesService)
    monkeypatch.setattr(changes_router, "PretargetingService", _StubPretargetingService)

    client = SyncASGIClient(app)
    response = client.post("/api/settings/pretargeting/123/discard-all")

    assert response.status_code == 409
    assert "discard conflict" in response.json()["detail"].lower()
