"""API tests for composite optimizer workflows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import optimizer_workflows as optimizer_workflows_router


class _StubOptimizerScoringService:
    def __init__(self):
        self.calls: list[dict] = []

    async def run_scoring(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "model_type": "rules",
            "model_id": kwargs["model_id"],
            "buyer_id": kwargs["buyer_id"],
            "start_date": kwargs.get("start_date") or "2026-02-15",
            "end_date": kwargs.get("end_date") or "2026-02-28",
            "event_type": kwargs.get("event_type"),
            "segments_scanned": 2,
            "scores_written": 2,
            "top_scores": [],
        }


class _StubOptimizerProposalsService:
    def __init__(self):
        self.calls: list[dict] = []

    async def generate_from_scores(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "model_id": kwargs["model_id"],
            "buyer_id": kwargs["buyer_id"],
            "days": kwargs.get("days", 14),
            "min_confidence": kwargs.get("min_confidence", 0.3),
            "max_delta_pct": kwargs.get("max_delta_pct", 0.3),
            "scores_considered": 2,
            "proposals_created": 2,
            "top_proposals": [],
        }


def _build_client(
    scoring_stub: _StubOptimizerScoringService,
    proposals_stub: _StubOptimizerProposalsService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    app = FastAPI()
    app.include_router(optimizer_workflows_router.router, prefix="/api")
    app.dependency_overrides[optimizer_workflows_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[optimizer_workflows_router.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )

    async def _resolve_buyer_id(
        buyer_id: str | None,
        store=None,
        user=None,
    ) -> str | None:
        return buyer_id or "1111111111"

    monkeypatch.setattr(optimizer_workflows_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(optimizer_workflows_router, "OptimizerScoringService", lambda: scoring_stub)
    monkeypatch.setattr(optimizer_workflows_router, "OptimizerProposalsService", lambda: proposals_stub)
    return TestClient(app)


def test_run_score_and_propose_workflow(monkeypatch: pytest.MonkeyPatch):
    scoring_stub = _StubOptimizerScoringService()
    proposals_stub = _StubOptimizerProposalsService()
    client = _build_client(scoring_stub, proposals_stub, monkeypatch)

    response = client.post(
        "/api/optimizer/workflows/score-and-propose",
        params={
            "model_id": "mdl_rules",
            "buyer_id": "1111111111",
            "days": 14,
            "event_type": "first_deposit",
            "score_limit": 500,
            "min_confidence": 0.4,
            "max_delta_pct": 0.25,
            "proposal_limit": 100,
        },
    )

    assert response.status_code == 200
    assert len(scoring_stub.calls) == 1
    assert len(proposals_stub.calls) == 1
    scoring_call = scoring_stub.calls[0]
    proposal_call = proposals_stub.calls[0]
    assert scoring_call["model_id"] == "mdl_rules"
    assert scoring_call["event_type"] == "first_deposit"
    assert scoring_call["limit"] == 500
    assert proposal_call["min_confidence"] == 0.4
    assert proposal_call["max_delta_pct"] == 0.25
    assert proposal_call["limit"] == 100
    payload = response.json()
    assert payload["buyer_id"] == "1111111111"
    assert payload["model_id"] == "mdl_rules"
    assert payload["score_run"]["scores_written"] == 2
    assert payload["proposal_run"]["proposals_created"] == 2

