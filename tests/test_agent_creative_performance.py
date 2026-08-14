"""Tests for the Agent API creative-performance batch contract."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from api.routers import agent_creatives as agent_creatives_router
from services.agent_creative_performance_service import (
    AgentCreativePerformanceService,
)
from services.agent_token_service import (
    AGENT_CREATIVE_PERFORMANCE_READ_SCOPE,
    AGENT_STATS_READ_SCOPE,
    AgentAuthContext,
    AgentTokenRecord,
)
from services.auth_service import User
from tests.support.asgi_client import SyncASGIClient


class _StubPerformanceRepo:
    def __init__(
        self,
        *,
        owners: list[dict] | None = None,
        summaries: list[dict] | None = None,
    ) -> None:
        self.owners = owners or []
        self.summaries = summaries or []
        self.calls: list[dict] = []

    async def get_creative_buyers(self, creative_ids):
        self.calls.append({"get_creative_buyers": creative_ids})
        return self.owners

    async def get_summaries(self, **kwargs):
        self.calls.append({"get_summaries": kwargs})
        return self.summaries


class _StubQualityService:
    def __init__(self, allocation: dict) -> None:
        self.allocation = allocation
        self.calls: list[dict] = []

    async def get_data_quality(self, **kwargs):
        self.calls.append(kwargs)
        return {"allocation": self.allocation}


class _StubAuthService:
    def __init__(self) -> None:
        self.audit_calls: list[dict] = []

    async def log_audit(self, **kwargs):
        self.audit_calls.append(kwargs)
        return kwargs


def _allocation(status: str = "reconciled") -> dict:
    allocated = 2_000_000 if status == "reconciled" else 2_600_000
    difference = allocated - 2_000_000
    return {
        "allocation_status": status,
        "canonical_spend_micros": 2_000_000,
        "allocated_spend_micros": allocated,
        "difference_micros": difference,
        "difference_pct": difference / 2_000_000 * 100,
        "tolerance_pct": 1.0,
    }


def _owners(*buyer_ids: str) -> list[dict]:
    return [
        {"creative_id": f"creative-{index}", "buyer_id": buyer_id}
        for index, buyer_id in enumerate(buyer_ids, start=1)
    ]


def _summary(
    creative_id: str = "creative-1",
    metric_source: str = "config_creative_daily",
) -> dict:
    return {
        "creative_id": creative_id,
        "total_impressions": 1_000,
        "total_spend_micros": 2_000_000,
        "days_with_data": 2,
        "source_dates": [date(2026, 8, 1), date(2026, 8, 2)],
        "metric_source": metric_source,
    }


def _context(
    *,
    buyer_id: str = "buyer-1",
    scopes: list[str] | None = None,
) -> AgentAuthContext:
    return AgentAuthContext(
        user=User(id="agent-user", email="agent@example.com", role="sudo"),
        token=AgentTokenRecord(
            id="token-1",
            name="Performance read token",
            token_prefix="cat_agent_testprefix",
            user_id="agent-user",
            buyer_id=buyer_id,
            scopes=scopes or [AGENT_CREATIVE_PERFORMANCE_READ_SCOPE],
            expires_at="2026-12-31T00:00:00+00:00",
            is_active=True,
        ),
    )


def _request_body(**overrides) -> dict:
    body = {
        "buyer_id": "buyer-1",
        "creative_ids": ["creative-1", "creative-2"],
        "start_date": "2026-08-01",
        "end_date": "2026-08-02",
        "tolerance_pct": 1.0,
    }
    body.update(overrides)
    return body


def _expected_mixed(allocation: dict | None = None) -> dict:
    allocation = allocation or _allocation()
    return {
        "api_version": "agent.v1",
        "buyer_id": "buyer-1",
        "period": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "days": 2,
        },
        "source_tables": [
            "config_creative_daily",
            "performance_metrics",
        ],
        "performance": [
            {
                "creative_id": "creative-1",
                "total_impressions": 1_000,
                "total_clicks": None,
                "total_spend_micros": 2_000_000,
                "avg_cpm_micros": 2_000_000,
                "days_with_data": 2,
                "has_data": True,
                "metric_source": "config_creative_daily",
                "clicks_available": False,
                "provenance": {
                    "metric_source": "config_creative_daily",
                    "is_canonical": False,
                    "buyer_scope": "buyer-1",
                    "latest_complete_date": "2026-08-02",
                    "latest_source_date": "2026-08-02",
                    "missing_source_dates": [],
                    "allocation": allocation,
                },
            },
            {
                "creative_id": "creative-2",
                "total_impressions": 0,
                "total_clicks": None,
                "total_spend_micros": 0,
                "avg_cpm_micros": None,
                "days_with_data": 0,
                "has_data": False,
                "metric_source": "unavailable",
                "clicks_available": False,
                "provenance": {
                    "metric_source": "unavailable",
                    "is_canonical": False,
                    "buyer_scope": "buyer-1",
                    "latest_complete_date": None,
                    "latest_source_date": None,
                    "missing_source_dates": ["2026-08-01", "2026-08-02"],
                    "allocation": allocation,
                },
            },
        ],
        "count": 2,
    }


def _service(
    *,
    owners: list[dict] | None = None,
    summaries: list[dict] | None = None,
    allocation: dict | None = None,
) -> tuple[AgentCreativePerformanceService, _StubPerformanceRepo, _StubQualityService]:
    repo = _StubPerformanceRepo(
        owners=owners or _owners("buyer-1", "buyer-1"),
        summaries=summaries or [_summary()],
    )
    quality = _StubQualityService(allocation or _allocation())
    return (
        AgentCreativePerformanceService(repo=repo, quality_service=quality),
        repo,
        quality,
    )


@pytest.mark.asyncio
async def test_batch_mixed_precompute_and_unavailable_full_schema() -> None:
    service, repo, quality = _service()

    payload = await service.get_batch(
        buyer_id="buyer-1",
        creative_ids=["creative-1", "creative-2"],
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )

    assert payload == _expected_mixed()
    assert repo.calls[0] == {
        "get_creative_buyers": ["creative-1", "creative-2"]
    }
    assert quality.calls[0]["tolerance_pct"] == 1.0


@pytest.mark.asyncio
async def test_batch_attaches_non_reconciling_allocation() -> None:
    allocation = _allocation("non_reconciling")
    service, _, _ = _service(allocation=allocation)

    payload = await service.get_batch(
        buyer_id="buyer-1",
        creative_ids=["creative-1", "creative-2"],
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )

    assert payload == _expected_mixed(allocation)
    assert {
        row["provenance"]["allocation"]["allocation_status"]
        for row in payload["performance"]
    } == {"non_reconciling"}


@pytest.mark.asyncio
async def test_batch_uses_secondary_precompute_source() -> None:
    service, _, _ = _service(
        owners=_owners("buyer-1"),
        summaries=[_summary(metric_source="performance_metrics")],
    )

    payload = await service.get_batch(
        buyer_id="buyer-1",
        creative_ids=["creative-1"],
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )

    row = payload["performance"][0]
    assert row["metric_source"] == "performance_metrics"
    assert row["provenance"]["metric_source"] == "performance_metrics"
    assert row["clicks_available"] is False


def _router_client(
    *,
    context: AgentAuthContext,
    service: AgentCreativePerformanceService,
    auth: _StubAuthService,
    enforce_real_scope: bool = False,
) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(agent_creatives_router.router, prefix="/api")
    if enforce_real_scope:

        @app.middleware("http")
        async def _set_context(request, call_next):
            request.state.agent_auth_context = context
            return await call_next(request)

    else:
        app.dependency_overrides[
            agent_creatives_router.require_agent_creative_performance_context
        ] = lambda: context
    app.dependency_overrides[
        agent_creatives_router.get_agent_creative_performance_service
    ] = lambda: service
    app.dependency_overrides[agent_creatives_router.get_auth_service] = lambda: auth
    app.dependency_overrides[agent_creatives_router.get_store] = (
        lambda: SimpleNamespace()
    )
    return SyncASGIClient(app)


def test_batch_rejects_creative_owned_by_other_buyer() -> None:
    service, repo, _ = _service(
        owners=_owners("buyer-1", "buyer-2"),
    )
    client = _router_client(
        context=_context(),
        service=service,
        auth=_StubAuthService(),
    )

    response = client.post(
        "/api/agent/v1/creative-performance/batch",
        json=_request_body(),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "One or more creatives are outside the requested buyer scope."
    }
    assert len(repo.calls) == 1


def test_batch_rejects_stats_only_scope() -> None:
    service, _, _ = _service()
    client = _router_client(
        context=_context(scopes=[AGENT_STATS_READ_SCOPE]),
        service=service,
        auth=_StubAuthService(),
        enforce_real_scope=True,
    )

    response = client.post(
        "/api/agent/v1/creative-performance/batch",
        json=_request_body(),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Agent token lacks required scope: "
            "agent:creative-performance:read."
        )
    }


def test_batch_router_returns_full_schema_and_audits() -> None:
    service, _, _ = _service()
    auth = _StubAuthService()
    client = _router_client(
        context=_context(),
        service=service,
        auth=auth,
    )

    response = client.post(
        "/api/agent/v1/creative-performance/batch",
        json=_request_body(),
    )

    assert response.status_code == 200
    assert response.json() == _expected_mixed()
    assert auth.audit_calls[0]["action"] == "agent_creative_performance_read"
    assert auth.audit_calls[0]["resource_id"] == "buyer-1"
    assert "creative_count=2" in auth.audit_calls[0]["details"]


def test_batch_size_is_bounded_at_100() -> None:
    service, _, _ = _service()
    client = _router_client(
        context=_context(),
        service=service,
        auth=_StubAuthService(),
    )

    response = client.post(
        "/api/agent/v1/creative-performance/batch",
        json=_request_body(
            creative_ids=[f"creative-{index}" for index in range(101)]
        ),
    )

    assert response.status_code == 422


def test_added_agent_modules_exclude_forbidden_source_name() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    modules = [
        "api/routers/agent_creatives.py",
        "api/schemas/agent_creatives.py",
        "api/schemas/agent_creative_performance.py",
        "services/agent_creatives_service.py",
        "services/agent_creative_performance_service.py",
    ]
    forbidden_source_name = "rtb" + "_daily"

    for module in modules:
        assert forbidden_source_name not in (
            repository_root / module
        ).read_text()
