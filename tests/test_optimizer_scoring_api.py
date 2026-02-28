"""API tests for BYOM optimizer scoring endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import optimizer_scoring as optimizer_scoring_router


class _StubOptimizerScoringService:
    def __init__(self):
        self.run_calls: list[dict] = []
        self.list_calls: list[dict] = []

    async def run_rules_scoring(self, **kwargs):
        self.run_calls.append(kwargs)
        return {
            "model_id": kwargs["model_id"],
            "buyer_id": kwargs["buyer_id"],
            "start_date": kwargs.get("start_date") or "2026-02-15",
            "end_date": kwargs.get("end_date") or "2026-02-28",
            "event_type": kwargs.get("event_type"),
            "segments_scanned": 2,
            "scores_written": 2,
            "top_scores": [
                {
                    "score_id": "scr_1",
                    "billing_id": "cfg-1",
                    "country": "US",
                    "publisher_id": "pub-1",
                    "app_id": "com.example.app",
                    "score_date": "2026-02-28",
                    "value_score": 0.91,
                    "confidence": 0.88,
                    "reason_codes": ["high_event_volume"],
                }
            ],
        }

    async def list_scores(self, **kwargs):
        self.list_calls.append(kwargs)
        return {
            "rows": [
                {
                    "score_id": "scr_1",
                    "model_id": kwargs.get("model_id") or "mdl_rules",
                    "buyer_id": kwargs["buyer_id"],
                    "billing_id": "cfg-1",
                    "country": "US",
                    "publisher_id": "pub-1",
                    "app_id": "com.example.app",
                    "creative_size": "",
                    "platform": "",
                    "environment": "",
                    "hour": None,
                    "score_date": "2026-02-28",
                    "value_score": 0.91,
                    "confidence": 0.88,
                    "reason_codes": ["high_event_volume"],
                    "raw_response": {"event_count": 20},
                    "created_at": "2026-02-28T00:00:00+00:00",
                }
            ],
            "meta": {
                "start_date": kwargs.get("start_date") or "2026-02-15",
                "end_date": kwargs.get("end_date") or "2026-02-28",
                "total": 1,
                "returned": 1,
                "limit": kwargs.get("limit", 200),
                "offset": kwargs.get("offset", 0),
                "has_more": False,
            },
        }


def _build_client(
    stub_service: _StubOptimizerScoringService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    app = FastAPI()
    app.include_router(optimizer_scoring_router.router, prefix="/api")
    app.dependency_overrides[optimizer_scoring_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[optimizer_scoring_router.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )

    async def _resolve_buyer_id(
        buyer_id: str | None,
        store=None,
        user=None,
    ) -> str | None:
        return buyer_id or "1111111111"

    monkeypatch.setattr(optimizer_scoring_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(optimizer_scoring_router, "OptimizerScoringService", lambda: stub_service)
    return TestClient(app)


def test_run_rules_scoring_endpoint(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerScoringService()
    client = _build_client(stub, monkeypatch)

    response = client.post(
        "/api/optimizer/scoring/rules/run",
        params={
            "model_id": "mdl_rules",
            "buyer_id": "1111111111",
            "days": 14,
            "event_type": "first_deposit",
            "limit": 500,
        },
    )

    assert response.status_code == 200
    assert len(stub.run_calls) == 1
    call = stub.run_calls[0]
    assert call["model_id"] == "mdl_rules"
    assert call["buyer_id"] == "1111111111"
    assert call["event_type"] == "first_deposit"
    assert call["limit"] == 500
    payload = response.json()
    assert payload["segments_scanned"] == 2
    assert payload["top_scores"][0]["score_id"] == "scr_1"


def test_list_segment_scores_endpoint(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerScoringService()
    client = _build_client(stub, monkeypatch)

    response = client.get(
        "/api/optimizer/scoring/segments",
        params={
            "model_id": "mdl_rules",
            "buyer_id": "1111111111",
            "days": 14,
            "billing_id": "cfg-1",
            "limit": 50,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    assert len(stub.list_calls) == 1
    call = stub.list_calls[0]
    assert call["model_id"] == "mdl_rules"
    assert call["buyer_id"] == "1111111111"
    assert call["billing_id"] == "cfg-1"
    assert call["limit"] == 50
    payload = response.json()
    assert payload["meta"]["total"] == 1
    assert payload["rows"][0]["score_id"] == "scr_1"

