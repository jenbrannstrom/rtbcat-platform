"""API tests for optimizer economics endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import optimizer_economics as optimizer_economics_router


class _StubOptimizerEconomicsService:
    def __init__(self):
        self.calls: list[dict] = []
        self.assumed_value_calls: list[dict] = []

    async def get_effective_cpm(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "buyer_id": kwargs["buyer_id"],
            "billing_id": kwargs.get("billing_id"),
            "start_date": kwargs.get("start_date") or "2026-02-15",
            "end_date": kwargs.get("end_date") or "2026-02-28",
            "days": 14,
            "impressions": 100000,
            "media_spend_usd": 12.5,
            "monthly_hosting_cost_usd": 3000.0,
            "infra_cost_period_usd": 986.30137,
            "media_cpm_usd": 0.125,
            "infra_cpm_usd": 9.863014,
            "effective_cpm_usd": 9.988014,
            "cost_context_ready": True,
        }

    async def get_assumed_value(self, **kwargs):
        self.assumed_value_calls.append(kwargs)
        return {
            "buyer_id": kwargs["buyer_id"],
            "billing_id": kwargs.get("billing_id"),
            "start_date": kwargs.get("start_date") or "2026-02-15",
            "end_date": kwargs.get("end_date") or "2026-02-28",
            "days": 14,
            "assumed_value_score": 0.712345,
            "components": {
                "spend_level_score": 0.4,
                "spend_trend_score": 0.7,
                "bid_rate_score": 0.2,
                "win_rate_score": 0.18,
                "ctr_score": 0.35,
                "age_score": 1.0,
                "viewability_score": 0.9,
            },
            "metrics": {
                "spend_usd": 120.0,
                "avg_daily_spend_usd": 8.57,
                "recent_spend_usd": 70.0,
                "previous_spend_usd": 50.0,
                "impressions": 1000000,
                "clicks": 25000,
                "reached_queries": 3000000,
                "bids_in_auction": 600000,
                "auctions_won": 120000,
                "bid_rate": 0.2,
                "win_rate": 0.2,
                "ctr": 0.025,
                "viewability": 0.7,
                "account_age_months": 10.5,
            },
        }


def _build_client(
    stub_service: _StubOptimizerEconomicsService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    app = FastAPI()
    app.include_router(optimizer_economics_router.router, prefix="/api")
    app.dependency_overrides[optimizer_economics_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[optimizer_economics_router.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )

    async def _resolve_buyer_id(
        buyer_id: str | None,
        store=None,
        user=None,
    ) -> str | None:
        return buyer_id or "1111111111"

    monkeypatch.setattr(optimizer_economics_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(optimizer_economics_router, "OptimizerEconomicsService", lambda: stub_service)
    return TestClient(app)


def test_get_effective_cpm_endpoint(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerEconomicsService()
    client = _build_client(stub, monkeypatch)

    response = client.get(
        "/api/optimizer/economics/effective-cpm",
        params={
            "buyer_id": "1111111111",
            "billing_id": "cfg-1",
            "days": 14,
        },
    )

    assert response.status_code == 200
    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["buyer_id"] == "1111111111"
    assert call["billing_id"] == "cfg-1"
    assert call["days"] == 14
    payload = response.json()
    assert payload["impressions"] == 100000
    assert payload["effective_cpm_usd"] == 9.988014
    assert payload["cost_context_ready"] is True


def test_get_assumed_value_endpoint(monkeypatch: pytest.MonkeyPatch):
    stub = _StubOptimizerEconomicsService()
    client = _build_client(stub, monkeypatch)

    response = client.get(
        "/api/optimizer/economics/assumed-value",
        params={
            "buyer_id": "1111111111",
            "billing_id": "cfg-1",
            "days": 14,
        },
    )

    assert response.status_code == 200
    assert len(stub.assumed_value_calls) == 1
    call = stub.assumed_value_calls[0]
    assert call["buyer_id"] == "1111111111"
    assert call["billing_id"] == "cfg-1"
    payload = response.json()
    assert payload["assumed_value_score"] == 0.712345
    assert payload["metrics"]["bid_rate"] == 0.2
