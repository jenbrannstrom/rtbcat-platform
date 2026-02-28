"""Tests for optimizer proposal generation and workflow service."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from services.optimizer_proposals_service import OptimizerProposalsService


@pytest.mark.asyncio
async def test_generate_from_scores_creates_rows(monkeypatch: pytest.MonkeyPatch):
    inserts: list[tuple[str, tuple]] = []

    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM segment_scores" in sql
        return [
            {
                "score_id": "scr_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "score_date": "2026-02-28",
                "value_score": 0.9,
                "confidence": 0.8,
                "reason_codes": ["high_event_volume", "low_cpa"],
                "raw_response": {"impressions": 864000, "event_count": 20},
            },
            {
                "score_id": "scr_2",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-2",
                "score_date": "2026-02-28",
                "value_score": 0.2,
                "confidence": 0.5,
                "reason_codes": ["sparse_data"],
                "raw_response": {"impressions": 43200, "event_count": 1},
            },
        ]

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        inserts.append((sql, params))
        return 1

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query", _stub_query)
    monkeypatch.setattr("services.optimizer_proposals_service.pg_execute", _stub_execute)
    service = OptimizerProposalsService()
    payload = await service.generate_from_scores(
        model_id="mdl_rules",
        buyer_id="1111111111",
        days=7,
        min_confidence=0.3,
        max_delta_pct=0.25,
        limit=100,
    )

    assert payload["model_id"] == "mdl_rules"
    assert payload["buyer_id"] == "1111111111"
    assert payload["scores_considered"] == 2
    assert payload["proposals_created"] == 2
    assert len(payload["top_proposals"]) == 2
    assert inserts
    assert any("INSERT INTO qps_allocation_proposals" in sql for sql, _ in inserts)
    assert any("INSERT INTO qps_allocation_proposal_history" in sql for sql, _ in inserts)


@pytest.mark.asyncio
async def test_list_proposals_returns_meta(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM qps_allocation_proposals" in sql
        return [
            {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 120.0,
                "delta_qps": 20.0,
                "rationale": "test rationale",
                "projected_impact": {"expected_event_lift_pct": 10.0},
                "status": "draft",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": None,
            }
        ]

    async def _stub_query_one(sql: str, params: tuple = ()):
        return {"total_rows": 1}

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query", _stub_query)
    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    service = OptimizerProposalsService()
    payload = await service.list_proposals(
        buyer_id="1111111111",
        model_id="mdl_rules",
        status="draft",
        limit=20,
        offset=0,
    )

    assert payload["meta"]["total"] == 1
    assert payload["meta"]["returned"] == 1
    assert payload["rows"][0]["proposal_id"] == "prp_1"
    assert payload["rows"][0]["status"] == "draft"


@pytest.mark.asyncio
async def test_update_status_returns_row(monkeypatch: pytest.MonkeyPatch):
    executes: list[tuple[str, tuple]] = []

    async def _stub_query_one(sql: str, params: tuple = ()):
        if "FROM qps_allocation_proposals" in sql and "LIMIT 1" in sql:
            return {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 120.0,
                "delta_qps": 20.0,
                "rationale": "test rationale",
                "projected_impact": {"expected_event_lift_pct": 10.0},
                "status": "draft",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": None,
            }
        assert "UPDATE qps_allocation_proposals" in sql
        assert params[0] == "approved"
        return {
            "proposal_id": "prp_1",
            "model_id": "mdl_rules",
            "buyer_id": "1111111111",
            "billing_id": "cfg-1",
            "current_qps": 100.0,
            "proposed_qps": 120.0,
            "delta_qps": 20.0,
            "rationale": "test rationale",
            "projected_impact": {"expected_event_lift_pct": 10.0},
            "status": "approved",
            "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            "applied_at": None,
        }

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        executes.append((sql, params))
        return 1

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    monkeypatch.setattr("services.optimizer_proposals_service.pg_execute", _stub_execute)
    service = OptimizerProposalsService()
    payload = await service.update_status(
        proposal_id="prp_1",
        buyer_id="1111111111",
        status="approved",
    )

    assert payload is not None
    assert payload["proposal_id"] == "prp_1"
    assert payload["status"] == "approved"
    assert any("INSERT INTO qps_allocation_proposal_history" in sql for sql, _ in executes)


@pytest.mark.asyncio
async def test_update_status_rejects_invalid_status():
    service = OptimizerProposalsService()
    with pytest.raises(ValueError, match="status must be one of"):
        await service.update_status(
            proposal_id="prp_1",
            buyer_id="1111111111",
            status="invalid",
        )


@pytest.mark.asyncio
async def test_update_status_rejects_invalid_transition(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        if "FROM qps_allocation_proposals" in sql and "LIMIT 1" in sql:
            return {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 120.0,
                "delta_qps": 20.0,
                "rationale": "test rationale",
                "projected_impact": {"expected_event_lift_pct": 10.0},
                "status": "draft",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": None,
            }
        return None

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    service = OptimizerProposalsService()
    with pytest.raises(ValueError, match="Invalid status transition"):
        await service.update_status(
            proposal_id="prp_1",
            buyer_id="1111111111",
            status="applied",
            apply_mode="queue",
        )


@pytest.mark.asyncio
async def test_apply_status_queues_pending_qps_change(monkeypatch: pytest.MonkeyPatch):
    executes: list[tuple[str, tuple]] = []

    class _StubPretargetingService:
        async def get_config(self, billing_id: str):
            assert billing_id == "cfg-1"
            return {"config_id": "ptcfg-1", "bidder_id": "bidder-1"}

    class _StubChangesService:
        def __init__(self):
            self.calls: list[dict] = []

        async def create_pending_change(self, **kwargs):
            self.calls.append(kwargs)
            return 77

    class _StubActionsService:
        def __init__(self):
            self.calls: list[dict] = []

        async def apply_pending_change(self, **kwargs):
            self.calls.append(kwargs)
            return {"status": "applied"}

    changes_stub = _StubChangesService()
    actions_stub = _StubActionsService()

    async def _stub_query_one(sql: str, params: tuple = ()):
        if "FROM qps_allocation_proposals" in sql and "LIMIT 1" in sql:
            return {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 120.0,
                "delta_qps": 20.0,
                "rationale": "test rationale",
                "projected_impact": {"expected_event_lift_pct": 10.0},
                "status": "approved",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": None,
            }
        if "UPDATE qps_allocation_proposals" in sql:
            projected = json.loads(params[0]) if isinstance(params[0], str) else params[0]
            return {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 120.0,
                "delta_qps": 20.0,
                "rationale": "test rationale",
                "projected_impact": projected,
                "status": "applied",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            }
        return None

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        executes.append((sql, params))
        return 1

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    monkeypatch.setattr("services.optimizer_proposals_service.pg_execute", _stub_execute)
    service = OptimizerProposalsService(
        changes_service=changes_stub,
        pretargeting_service=_StubPretargetingService(),
        actions_service=actions_stub,
    )
    payload = await service.update_status(
        proposal_id="prp_1",
        buyer_id="1111111111",
        status="applied",
        apply_mode="queue",
        applied_by="u1",
    )

    assert payload is not None
    assert payload["status"] == "applied"
    assert payload["apply_details"]["mode"] == "queue"
    assert payload["apply_details"]["pending_change_id"] == 77
    assert payload["apply_details"]["queued_maximum_qps"] == 120
    assert len(changes_stub.calls) == 1
    call = changes_stub.calls[0]
    assert call["change_type"] == "set_maximum_qps"
    assert call["field_name"] == "maximum_qps"
    assert call["value"] == "120"
    assert actions_stub.calls == []
    assert any("INSERT INTO qps_allocation_proposal_history" in sql for sql, _ in executes)


@pytest.mark.asyncio
async def test_apply_status_live_executes_pending_change(monkeypatch: pytest.MonkeyPatch):
    executes: list[tuple[str, tuple]] = []

    class _StubPretargetingService:
        async def get_config(self, billing_id: str):
            return {"config_id": "ptcfg-1", "bidder_id": "bidder-1"}

    class _StubChangesService:
        async def create_pending_change(self, **kwargs):
            return 88

    class _StubActionsService:
        def __init__(self):
            self.calls: list[dict] = []

        async def apply_pending_change(self, **kwargs):
            self.calls.append(kwargs)
            return {"status": "applied", "change_id": kwargs["change_id"]}

    actions_stub = _StubActionsService()

    async def _stub_query_one(sql: str, params: tuple = ()):
        if "FROM qps_allocation_proposals" in sql and "LIMIT 1" in sql:
            return {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 119.6,
                "delta_qps": 19.6,
                "rationale": "test rationale",
                "projected_impact": {"expected_event_lift_pct": 10.0},
                "status": "approved",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": None,
            }
        if "UPDATE qps_allocation_proposals" in sql:
            projected = json.loads(params[0]) if isinstance(params[0], str) else params[0]
            return {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 119.6,
                "delta_qps": 19.6,
                "rationale": "test rationale",
                "projected_impact": projected,
                "status": "applied",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            }
        return None

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        executes.append((sql, params))
        return 1

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    monkeypatch.setattr("services.optimizer_proposals_service.pg_execute", _stub_execute)
    service = OptimizerProposalsService(
        changes_service=_StubChangesService(),
        pretargeting_service=_StubPretargetingService(),
        actions_service=actions_stub,
    )
    payload = await service.update_status(
        proposal_id="prp_1",
        buyer_id="1111111111",
        status="applied",
        apply_mode="live",
        applied_by="u1",
    )

    assert payload is not None
    assert payload["apply_details"]["mode"] == "live"
    assert payload["apply_details"]["pending_change_id"] == 88
    assert payload["apply_details"]["queued_maximum_qps"] == 120
    assert payload["apply_details"]["live_result"]["status"] == "applied"
    assert len(actions_stub.calls) == 1
    assert actions_stub.calls[0]["billing_id"] == "cfg-1"
    assert actions_stub.calls[0]["change_id"] == 88
    assert any("INSERT INTO qps_allocation_proposal_history" in sql for sql, _ in executes)


@pytest.mark.asyncio
async def test_get_proposal_returns_payload(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        assert "FROM qps_allocation_proposals" in sql
        return {
            "proposal_id": "prp_1",
            "model_id": "mdl_rules",
            "buyer_id": "1111111111",
            "billing_id": "cfg-1",
            "current_qps": 100.0,
            "proposed_qps": 120.0,
            "delta_qps": 20.0,
            "rationale": "test rationale",
            "projected_impact": {"expected_event_lift_pct": 10.0},
            "status": "draft",
            "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            "applied_at": None,
        }

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    service = OptimizerProposalsService()
    payload = await service.get_proposal(
        proposal_id="prp_1",
        buyer_id="1111111111",
    )

    assert payload is not None
    assert payload["proposal_id"] == "prp_1"
    assert payload["status"] == "draft"


@pytest.mark.asyncio
async def test_list_history_returns_meta(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM qps_allocation_proposal_history" in sql
        return [
            {
                "event_id": "prp_evt_1",
                "proposal_id": "prp_1",
                "buyer_id": "1111111111",
                "from_status": "draft",
                "to_status": "approved",
                "apply_mode": None,
                "changed_by": "u1",
                "details": {"transition": "manual_workflow"},
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            }
        ]

    async def _stub_query_one(sql: str, params: tuple = ()):
        assert "COUNT(*) AS total_rows" in sql
        return {"total_rows": 1}

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query", _stub_query)
    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    service = OptimizerProposalsService()
    payload = await service.list_history(
        proposal_id="prp_1",
        buyer_id="1111111111",
        limit=50,
        offset=0,
    )

    assert payload["meta"]["total"] == 1
    assert payload["meta"]["returned"] == 1
    assert payload["rows"][0]["event_id"] == "prp_evt_1"
    assert payload["rows"][0]["to_status"] == "approved"


@pytest.mark.asyncio
async def test_sync_apply_status_updates_projected_impact(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query_one(sql: str, params: tuple = ()):
        if "FROM qps_allocation_proposals" in sql and "LIMIT 1" in sql:
            return {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 120.0,
                "delta_qps": 20.0,
                "rationale": "test rationale",
                "projected_impact": {"apply": {"pending_change_id": 77, "mode": "queue"}},
                "status": "applied",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            }
        if "FROM pretargeting_pending_changes" in sql:
            assert params[0] == 77
            return {
                "id": 77,
                "status": "applied",
                "applied_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_by": "u1",
            }
        if "UPDATE qps_allocation_proposals" in sql:
            projected = json.loads(params[0]) if isinstance(params[0], str) else params[0]
            return {
                "proposal_id": "prp_1",
                "model_id": "mdl_rules",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "current_qps": 100.0,
                "proposed_qps": 120.0,
                "delta_qps": 20.0,
                "rationale": "test rationale",
                "projected_impact": projected,
                "status": "applied",
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
                "applied_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            }
        return None

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    service = OptimizerProposalsService()
    payload = await service.sync_apply_status(
        proposal_id="prp_1",
        buyer_id="1111111111",
    )

    assert payload is not None
    assert payload["proposal_id"] == "prp_1"
    assert payload["apply_details"]["pending_change_id"] == 77
    assert payload["apply_details"]["pending_change_status"] == "applied"
    assert payload["apply_details"]["pending_change_applied_by"] == "u1"
