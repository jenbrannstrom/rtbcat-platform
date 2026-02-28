"""API tests for optimizer proposal endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import optimizer_proposals as optimizer_proposals_router


class _StubOptimizerProposalsService:
    def __init__(self):
        self.generate_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.update_calls: list[dict] = []
        self.not_found_ids: set[str] = {"missing"}

    async def generate_from_scores(self, **kwargs):
        self.generate_calls.append(kwargs)
        return {
            "model_id": kwargs["model_id"],
            "buyer_id": kwargs["buyer_id"],
            "days": kwargs.get("days", 7),
            "min_confidence": kwargs.get("min_confidence", 0.3),
            "max_delta_pct": kwargs.get("max_delta_pct", 0.3),
            "scores_considered": 2,
            "proposals_created": 2,
            "top_proposals": [
                {
                    "proposal_id": "prp_1",
                    "billing_id": "cfg-1",
                    "current_qps": 100.0,
                    "proposed_qps": 120.0,
                    "delta_qps": 20.0,
                    "rationale": "test rationale",
                    "status": "draft",
                }
            ],
        }

    async def list_proposals(self, **kwargs):
        self.list_calls.append(kwargs)
        return {
            "rows": [
                {
                    "proposal_id": "prp_1",
                    "model_id": kwargs.get("model_id") or "mdl_rules",
                    "buyer_id": kwargs["buyer_id"],
                    "billing_id": "cfg-1",
                    "current_qps": 100.0,
                    "proposed_qps": 120.0,
                    "delta_qps": 20.0,
                    "rationale": "test rationale",
                    "projected_impact": {"expected_event_lift_pct": 10.0},
                    "status": "draft",
                    "created_at": "2026-02-28T00:00:00+00:00",
                    "updated_at": "2026-02-28T00:00:00+00:00",
                    "applied_at": None,
                }
            ],
            "meta": {
                "total": 1,
                "returned": 1,
                "limit": kwargs.get("limit", 200),
                "offset": kwargs.get("offset", 0),
                "has_more": False,
            },
        }

    async def update_status(self, **kwargs):
        self.update_calls.append(kwargs)
        if kwargs.get("proposal_id") in self.not_found_ids:
            return None
        return {
            "proposal_id": kwargs["proposal_id"],
            "status": kwargs["status"],
            "apply_details": (
                {
                    "mode": kwargs.get("apply_mode", "queue"),
                    "pending_change_id": 77,
                    "queued_maximum_qps": 120,
                }
                if kwargs.get("status") == "applied"
                else None
            ),
        }


def _build_client(
    stub_service: _StubOptimizerProposalsService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    app = FastAPI()
    app.include_router(optimizer_proposals_router.router, prefix="/api")
    app.dependency_overrides[optimizer_proposals_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[optimizer_proposals_router.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )

    async def _resolve_buyer_id(
        buyer_id: str | None,
        store=None,
        user=None,
    ) -> str | None:
        return buyer_id or "1111111111"

    monkeypatch.setattr(optimizer_proposals_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(optimizer_proposals_router, "OptimizerProposalsService", lambda: stub_service)
    return TestClient(app)


def test_generate_qps_proposals_endpoint(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerProposalsService()
    client = _build_client(stub, monkeypatch)

    response = client.post(
        "/api/optimizer/proposals/generate",
        params={
            "model_id": "mdl_rules",
            "buyer_id": "1111111111",
            "days": 7,
            "min_confidence": 0.4,
            "max_delta_pct": 0.25,
            "limit": 100,
        },
    )

    assert response.status_code == 200
    assert len(stub.generate_calls) == 1
    call = stub.generate_calls[0]
    assert call["model_id"] == "mdl_rules"
    assert call["buyer_id"] == "1111111111"
    assert call["min_confidence"] == 0.4
    payload = response.json()
    assert payload["proposals_created"] == 2
    assert payload["top_proposals"][0]["proposal_id"] == "prp_1"


def test_list_qps_proposals_endpoint(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerProposalsService()
    client = _build_client(stub, monkeypatch)

    response = client.get(
        "/api/optimizer/proposals",
        params={
            "buyer_id": "1111111111",
            "model_id": "mdl_rules",
            "status": "draft",
            "limit": 20,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    assert len(stub.list_calls) == 1
    call = stub.list_calls[0]
    assert call["buyer_id"] == "1111111111"
    assert call["model_id"] == "mdl_rules"
    assert call["status"] == "draft"
    payload = response.json()
    assert payload["meta"]["total"] == 1
    assert payload["rows"][0]["proposal_id"] == "prp_1"


def test_approve_reject_apply_proposal_endpoints(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerProposalsService()
    client = _build_client(stub, monkeypatch)

    approve = client.post("/api/optimizer/proposals/prp_1/approve", params={"buyer_id": "1111111111"})
    reject = client.post("/api/optimizer/proposals/prp_1/reject", params={"buyer_id": "1111111111"})
    apply = client.post(
        "/api/optimizer/proposals/prp_1/apply",
        params={"buyer_id": "1111111111", "mode": "live"},
    )

    assert approve.status_code == 200
    assert reject.status_code == 200
    assert apply.status_code == 200
    assert len(stub.update_calls) == 3
    assert stub.update_calls[0]["status"] == "approved"
    assert stub.update_calls[1]["status"] == "rejected"
    assert stub.update_calls[2]["status"] == "applied"
    assert stub.update_calls[2]["apply_mode"] == "live"
    assert stub.update_calls[2]["applied_by"] == "u1"
    assert approve.json()["status"] == "approved"
    assert reject.json()["status"] == "rejected"
    assert apply.json()["status"] == "applied"
    assert apply.json()["apply_details"]["mode"] == "live"
