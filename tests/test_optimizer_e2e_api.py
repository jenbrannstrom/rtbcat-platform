"""End-to-end API flow test for BYOM score/propose/approve/apply workflow."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import optimizer_proposals as optimizer_proposals_router
from api.routers import optimizer_workflows as optimizer_workflows_router


class _StubOptimizerScoringService:
    async def run_scoring(self, **kwargs):
        return {
            "model_type": "rules",
            "model_id": kwargs["model_id"],
            "buyer_id": kwargs["buyer_id"],
            "start_date": kwargs.get("start_date") or "2026-02-15",
            "end_date": kwargs.get("end_date") or "2026-02-28",
            "event_type": kwargs.get("event_type"),
            "segments_scanned": 1,
            "scores_written": 1,
            "top_scores": [
                {
                    "score_id": "scr_1",
                    "billing_id": "cfg-1",
                    "value_score": 0.9,
                    "confidence": 0.8,
                }
            ],
        }


class _StatefulOptimizerProposalsService:
    def __init__(self):
        self._seq = 0
        self._proposals: dict[str, dict] = {}
        self._history: dict[str, list[dict]] = {}

    def _next_proposal_id(self) -> str:
        self._seq += 1
        return f"prp_{self._seq}"

    def _next_event_id(self, proposal_id: str) -> str:
        idx = len(self._history.get(proposal_id, [])) + 1
        return f"{proposal_id}_evt_{idx}"

    def _record_history(
        self,
        *,
        proposal_id: str,
        buyer_id: str,
        from_status: str | None,
        to_status: str,
        apply_mode: str | None = None,
        changed_by: str | None = None,
    ) -> None:
        rows = self._history.setdefault(proposal_id, [])
        rows.append(
            {
                "event_id": self._next_event_id(proposal_id),
                "proposal_id": proposal_id,
                "buyer_id": buyer_id,
                "from_status": from_status,
                "to_status": to_status,
                "apply_mode": apply_mode,
                "changed_by": changed_by,
                "details": {"transition": "workflow"},
                "created_at": "2026-02-28T00:00:00+00:00",
            }
        )

    async def generate_from_scores(self, **kwargs):
        proposal_id = self._next_proposal_id()
        proposal = {
            "proposal_id": proposal_id,
            "model_id": kwargs["model_id"],
            "buyer_id": kwargs["buyer_id"],
            "billing_id": "cfg-1",
            "current_qps": 100.0,
            "proposed_qps": 120.0,
            "delta_qps": 20.0,
            "rationale": "raise qps for higher-value segment",
            "projected_impact": {"expected_event_lift_pct": 12.0},
            "apply_details": None,
            "status": "draft",
            "created_at": "2026-02-28T00:00:00+00:00",
            "updated_at": "2026-02-28T00:00:00+00:00",
            "applied_at": None,
        }
        self._proposals[proposal_id] = proposal
        self._record_history(
            proposal_id=proposal_id,
            buyer_id=kwargs["buyer_id"],
            from_status=None,
            to_status="draft",
            changed_by="optimizer",
        )
        return {
            "model_id": kwargs["model_id"],
            "buyer_id": kwargs["buyer_id"],
            "days": kwargs.get("days", 14),
            "min_confidence": kwargs.get("min_confidence", 0.3),
            "max_delta_pct": kwargs.get("max_delta_pct", 0.3),
            "scores_considered": 1,
            "proposals_created": 1,
            "top_proposals": [
                {
                    "proposal_id": proposal_id,
                    "billing_id": "cfg-1",
                    "current_qps": 100.0,
                    "proposed_qps": 120.0,
                    "delta_qps": 20.0,
                    "rationale": "raise qps for higher-value segment",
                    "status": "draft",
                }
            ],
        }

    async def list_proposals(self, **kwargs):
        rows = [
            row
            for row in self._proposals.values()
            if row["buyer_id"] == kwargs["buyer_id"]
        ]
        return {
            "rows": rows,
            "meta": {
                "total": len(rows),
                "returned": len(rows),
                "limit": kwargs.get("limit", 200),
                "offset": kwargs.get("offset", 0),
                "has_more": False,
            },
        }

    async def get_proposal(self, **kwargs):
        row = self._proposals.get(kwargs["proposal_id"])
        if not row:
            return None
        if row["buyer_id"] != kwargs["buyer_id"]:
            return None
        return row

    async def list_history(self, **kwargs):
        rows = list(self._history.get(kwargs["proposal_id"], []))
        return {
            "rows": rows,
            "meta": {
                "total": len(rows),
                "returned": len(rows),
                "limit": kwargs.get("limit", 100),
                "offset": kwargs.get("offset", 0),
                "has_more": False,
            },
        }

    async def update_status(self, **kwargs):
        row = self._proposals.get(kwargs["proposal_id"])
        if not row:
            return None

        status = kwargs["status"]
        from_status = row["status"]
        allowed = {
            "draft": {"approved", "rejected"},
            "approved": {"applied", "rejected"},
            "applied": set(),
            "rejected": set(),
        }
        if status not in allowed.get(from_status, set()):
            raise ValueError(f"Invalid proposal status transition: {from_status} -> {status}")

        row["status"] = status
        row["updated_at"] = "2026-02-28T00:01:00+00:00"
        if status == "applied":
            row["applied_at"] = "2026-02-28T00:01:30+00:00"
            row["apply_details"] = {
                "mode": kwargs.get("apply_mode", "queue"),
                "pending_change_id": 77,
                "pending_change_status": "queued",
            }

        self._record_history(
            proposal_id=row["proposal_id"],
            buyer_id=row["buyer_id"],
            from_status=from_status,
            to_status=status,
            apply_mode=kwargs.get("apply_mode"),
            changed_by=kwargs.get("applied_by"),
        )
        return {
            "proposal_id": row["proposal_id"],
            "status": row["status"],
            "apply_details": row.get("apply_details"),
        }

    async def sync_apply_status(self, **kwargs):
        return await self.get_proposal(**kwargs)


def _build_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    scoring_stub = _StubOptimizerScoringService()
    proposals_stub = _StatefulOptimizerProposalsService()

    app = FastAPI()
    app.include_router(optimizer_workflows_router.router, prefix="/api")
    app.include_router(optimizer_proposals_router.router, prefix="/api")

    app.dependency_overrides[optimizer_workflows_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[optimizer_workflows_router.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )
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

    monkeypatch.setattr(optimizer_workflows_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(optimizer_proposals_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(optimizer_workflows_router, "OptimizerScoringService", lambda: scoring_stub)
    monkeypatch.setattr(optimizer_workflows_router, "OptimizerProposalsService", lambda: proposals_stub)
    monkeypatch.setattr(optimizer_proposals_router, "OptimizerProposalsService", lambda: proposals_stub)
    return TestClient(app)


def test_end_to_end_optimizer_workflow(monkeypatch: pytest.MonkeyPatch):
    client = _build_client(monkeypatch)

    workflow_response = client.post(
        "/api/optimizer/workflows/score-and-propose",
        params={
            "model_id": "mdl_rules",
            "buyer_id": "1111111111",
            "days": 14,
            "min_confidence": 0.3,
            "max_delta_pct": 0.3,
        },
    )
    assert workflow_response.status_code == 200
    workflow_payload = workflow_response.json()
    assert workflow_payload["score_run"]["scores_written"] == 1
    assert workflow_payload["proposal_run"]["proposals_created"] == 1
    proposal_id = workflow_payload["proposal_run"]["top_proposals"][0]["proposal_id"]

    list_response = client.get("/api/optimizer/proposals", params={"buyer_id": "1111111111"})
    assert list_response.status_code == 200
    rows = list_response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["proposal_id"] == proposal_id
    assert rows[0]["status"] == "draft"

    approve_response = client.post(
        f"/api/optimizer/proposals/{proposal_id}/approve",
        params={"buyer_id": "1111111111"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    apply_response = client.post(
        f"/api/optimizer/proposals/{proposal_id}/apply",
        params={"buyer_id": "1111111111", "mode": "queue"},
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "applied"
    assert apply_response.json()["apply_details"]["mode"] == "queue"

    sync_response = client.post(
        f"/api/optimizer/proposals/{proposal_id}/sync-apply-status",
        params={"buyer_id": "1111111111"},
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["status"] == "applied"

    history_response = client.get(
        f"/api/optimizer/proposals/{proposal_id}/history",
        params={"buyer_id": "1111111111", "limit": 10, "offset": 0},
    )
    assert history_response.status_code == 200
    history_rows = history_response.json()["rows"]
    transitions = [(row["from_status"], row["to_status"]) for row in history_rows]
    assert (None, "draft") in transitions
    assert ("draft", "approved") in transitions
    assert ("approved", "applied") in transitions
