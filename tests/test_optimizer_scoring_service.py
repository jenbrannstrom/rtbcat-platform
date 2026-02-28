"""Tests for rules-based optimizer scoring service."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from services.optimizer_scoring_service import OptimizerScoringService


@pytest.mark.asyncio
async def test_run_rules_scoring_requires_rules_model(monkeypatch: pytest.MonkeyPatch):
    async def _stub_get_model(self, *, model_id: str, buyer_id=None):
        return {
            "model_id": model_id,
            "buyer_id": buyer_id,
            "model_type": "api",
        }

    monkeypatch.setattr("services.optimizer_models_service.OptimizerModelsService.get_model", _stub_get_model)
    service = OptimizerScoringService()

    with pytest.raises(ValueError, match="model_type=rules"):
        await service.run_rules_scoring(
            model_id="mdl_1",
            buyer_id="1111111111",
            days=7,
        )


@pytest.mark.asyncio
async def test_run_rules_scoring_writes_scores(monkeypatch: pytest.MonkeyPatch):
    writes: list[tuple[str, tuple]] = []

    async def _stub_get_model(self, *, model_id: str, buyer_id=None):
        return {
            "model_id": model_id,
            "buyer_id": buyer_id,
            "model_type": "rules",
        }

    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM conversion_aggregates_daily" in sql
        return [
            {
                "score_date": date(2026, 2, 28),
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "country": "US",
                "publisher_id": "pub-1",
                "app_id": "com.example.app",
                "event_count": 20,
                "event_value_total": 200.0,
                "impressions": 5000,
                "clicks": 100,
                "spend_usd": 50.0,
            },
            {
                "score_date": date(2026, 2, 28),
                "buyer_id": "1111111111",
                "billing_id": "cfg-2",
                "country": "PH",
                "publisher_id": "pub-2",
                "app_id": "com.example.app2",
                "event_count": 0,
                "event_value_total": 0.0,
                "impressions": 80,
                "clicks": 2,
                "spend_usd": 5.0,
            },
        ]

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        writes.append((sql, params))
        return 1

    monkeypatch.setattr("services.optimizer_models_service.OptimizerModelsService.get_model", _stub_get_model)
    monkeypatch.setattr("services.optimizer_scoring_service.pg_query", _stub_query)
    monkeypatch.setattr("services.optimizer_scoring_service.pg_execute", _stub_execute)
    service = OptimizerScoringService()
    payload = await service.run_rules_scoring(
        model_id="mdl_rules",
        buyer_id="1111111111",
        days=14,
        limit=100,
    )

    assert payload["model_id"] == "mdl_rules"
    assert payload["buyer_id"] == "1111111111"
    assert payload["segments_scanned"] == 2
    assert payload["scores_written"] == 2
    assert len(payload["top_scores"]) == 2
    assert writes
    assert "INSERT INTO segment_scores" in writes[0][0]


@pytest.mark.asyncio
async def test_list_scores_shapes_rows(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM segment_scores" in sql
        return [
            {
                "score_id": "scr_1",
                "model_id": "mdl_1",
                "buyer_id": "1111111111",
                "billing_id": "cfg-1",
                "country": "US",
                "publisher_id": "pub-1",
                "app_id": "com.example.app",
                "creative_size": "",
                "platform": "",
                "environment": "",
                "hour": None,
                "score_date": date(2026, 2, 28),
                "value_score": 0.88,
                "confidence": 0.91,
                "reason_codes": ["high_event_volume", "low_cpa"],
                "raw_response": {"event_count": 20},
                "created_at": datetime(2026, 2, 28, tzinfo=timezone.utc),
            }
        ]

    async def _stub_query_one(sql: str, params: tuple = ()):
        return {"total_rows": 1}

    monkeypatch.setattr("services.optimizer_scoring_service.pg_query", _stub_query)
    monkeypatch.setattr("services.optimizer_scoring_service.pg_query_one", _stub_query_one)
    service = OptimizerScoringService()
    payload = await service.list_scores(
        model_id="mdl_1",
        buyer_id="1111111111",
        days=14,
        limit=20,
        offset=0,
    )

    assert payload["meta"]["total"] == 1
    assert payload["meta"]["returned"] == 1
    row = payload["rows"][0]
    assert row["score_id"] == "scr_1"
    assert row["value_score"] == 0.88
    assert row["confidence"] == 0.91
    assert row["reason_codes"] == ["high_event_volume", "low_cpa"]

