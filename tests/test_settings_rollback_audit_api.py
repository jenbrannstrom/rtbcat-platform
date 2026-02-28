"""API tests for rollback audit context passthrough + history rendering."""

from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace

import pytest

# Avoid optional Google API dependency while importing settings routers.
if "collectors" not in sys.modules:
    fake_collectors = types.ModuleType("collectors")
    fake_collectors.PretargetingClient = object
    sys.modules["collectors"] = fake_collectors

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.settings import actions as actions_router
from api.routers.settings import pretargeting as pretargeting_router


class _StubActionsService:
    def __init__(self):
        self.rollback_calls: list[dict] = []

    async def rollback_to_snapshot(self, **kwargs):
        self.rollback_calls.append(kwargs)
        return {
            "status": "applied",
            "dry_run": kwargs.get("dry_run", False),
            "snapshot_id": kwargs["snapshot_id"],
            "changes_made": ["add_size: 320x50"],
            "message": "Rolled back to snapshot. Applied 1 changes.",
            "history_id": 991,
        }


def _build_actions_client(
    stub_service: _StubActionsService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    app = FastAPI()
    app.include_router(actions_router.router, prefix="/api")
    app.dependency_overrides[actions_router.get_current_user] = lambda: SimpleNamespace(
        id="u123", role="sudo", email="admin@example.com"
    )
    monkeypatch.setattr(actions_router, "ActionsService", lambda: stub_service)
    return TestClient(app)


def test_rollback_endpoint_forwards_proposal_context(monkeypatch: pytest.MonkeyPatch):
    stub = _StubActionsService()
    client = _build_actions_client(stub, monkeypatch)

    response = client.post(
        "/api/settings/pretargeting/cfg-1/rollback",
        json={
            "snapshot_id": 77,
            "dry_run": False,
            "reason": "Post-apply anomaly",
            "proposal_id": "prp_123",
        },
    )

    assert response.status_code == 200
    assert len(stub.rollback_calls) == 1
    call = stub.rollback_calls[0]
    assert call["billing_id"] == "cfg-1"
    assert call["snapshot_id"] == 77
    assert call["dry_run"] is False
    assert call["reason"] == "Post-apply anomaly"
    assert call["proposal_id"] == "prp_123"
    assert call["initiated_by"] == "u123"
    payload = response.json()
    assert payload["history_id"] == 991


class _StubPretargetingService:
    async def list_history(self, **kwargs):
        return [
            {
                "id": 1,
                "config_id": "cfg-1",
                "bidder_id": "buyer-1",
                "change_type": "rollback",
                "field_changed": "all",
                "old_value": None,
                "new_value": "snapshot_77",
                "changed_at": "2026-02-28T00:00:00+00:00",
                "changed_by": "u123",
                "change_source": "optimizer",
                "raw_config_snapshot": {
                    "proposal_id": "prp_123",
                    "reason": "Post-apply anomaly",
                },
            },
            {
                "id": 2,
                "config_id": "cfg-1",
                "bidder_id": "buyer-1",
                "change_type": "rollback",
                "field_changed": "all",
                "old_value": None,
                "new_value": "snapshot_76",
                "changed_at": "2026-02-27T00:00:00+00:00",
                "changed_by": "u124",
                "change_source": "optimizer",
                "raw_config_snapshot": json.dumps(
                    {
                        "proposal_id": "prp_122",
                        "reason": "Budget correction",
                    }
                ),
            },
            {
                "id": 3,
                "config_id": "cfg-1",
                "bidder_id": "buyer-1",
                "change_type": "update",
                "field_changed": "user_name",
                "old_value": "old",
                "new_value": "new",
                "changed_at": "2026-02-26T00:00:00+00:00",
                "changed_by": "u125",
                "change_source": "user",
                "raw_config_snapshot": {"proposal_id": "should_be_hidden"},
            },
        ]


def _build_pretargeting_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(pretargeting_router.router, prefix="/api")
    monkeypatch.setattr(pretargeting_router, "PretargetingService", lambda: _StubPretargetingService())
    return TestClient(app)


def test_history_endpoint_parses_rollback_context_from_dict_and_json(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _build_pretargeting_client(monkeypatch)

    response = client.get(
        "/api/settings/pretargeting/history",
        params={"billing_id": "cfg-1", "days": 30},
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3

    assert rows[0]["rollback_context"]["proposal_id"] == "prp_123"
    assert rows[1]["rollback_context"]["proposal_id"] == "prp_122"
    assert rows[1]["rollback_context"]["reason"] == "Budget correction"
    assert rows[2]["change_type"] == "update"
    assert rows[2]["rollback_context"] is None
