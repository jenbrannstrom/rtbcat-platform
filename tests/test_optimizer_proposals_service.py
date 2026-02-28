"""Tests for optimizer proposal generation and workflow service."""

from __future__ import annotations

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
    assert "INSERT INTO qps_allocation_proposals" in inserts[0][0]


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
    async def _stub_query_one(sql: str, params: tuple = ()):
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

    monkeypatch.setattr("services.optimizer_proposals_service.pg_query_one", _stub_query_one)
    service = OptimizerProposalsService()
    payload = await service.update_status(
        proposal_id="prp_1",
        buyer_id="1111111111",
        status="approved",
    )

    assert payload is not None
    assert payload["proposal_id"] == "prp_1"
    assert payload["status"] == "approved"


@pytest.mark.asyncio
async def test_update_status_rejects_invalid_status():
    service = OptimizerProposalsService()
    with pytest.raises(ValueError, match="status must be one of"):
        await service.update_status(
            proposal_id="prp_1",
            buyer_id="1111111111",
            status="invalid",
        )

