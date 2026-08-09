"""Tests for the Agent API data-quality lane and provenance envelope.

Covers Phase 2 slice 1 of docs/MCP_READONLY_SERVER_PLAN.md: the
canonical-vs-allocated reconciliation service, GET /agent/v1/data-quality,
GET /agent/v1/buyers, and the provenance block on daily-spend.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException

from api.routers import agent as agent_router
from services.agent_data_quality_service import AgentDataQualityService
from services.agent_stats_service import AgentStatsService
from services.agent_token_service import AGENT_STATS_READ_SCOPE, AgentAuthContext, AgentTokenRecord
from services.auth_service import User
from tests.support.asgi_client import SyncASGIClient

BUYER = {
    "buyer_id": "buyer-1",
    "bidder_id": "bidder-1",
    "display_name": "Test Buyer",
    "active": True,
    "currency_code": "USD",
}


class _StubQualityRepo:
    def __init__(
        self,
        canonical: list[dict] | None = None,
        allocated: list[dict] | None = None,
        buyer: dict | None = BUYER,
    ) -> None:
        self.canonical = canonical or []
        self.allocated = allocated or []
        self.buyer = buyer

    async def get_buyer(self, _buyer_id: str):
        return self.buyer

    async def get_canonical_daily(self, _buyer_id, _start, _end):
        return self.canonical

    async def get_allocated_daily(self, _buyer_id, _start, _end):
        return self.allocated


def _service(**kwargs) -> AgentDataQualityService:
    return AgentDataQualityService(repo=_StubQualityRepo(**kwargs))


def _canonical_row(day: str, spend: int) -> dict:
    return {"metric_date": date.fromisoformat(day), "spend_micros": spend, "impressions": 10}


def _allocated_row(day: str, spend: int, creatives: int = 3) -> dict:
    return {
        "metric_date": date.fromisoformat(day),
        "spend_micros": spend,
        "impressions": 12,
        "distinct_creatives": creatives,
    }


# ---------------------------------------------------------------------------
# Reconciliation service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matching_lanes_reconcile() -> None:
    service = _service(
        canonical=[_canonical_row("2026-08-01", 1_000_000)],
        allocated=[_allocated_row("2026-08-01", 1_000_000)],
    )
    payload = await service.get_data_quality(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 1),
    )
    assert payload["allocation"]["allocation_status"] == "reconciled"
    assert payload["allocation"]["difference_micros"] == 0
    assert payload["warnings"] == []
    assert payload["provenance"]["allocation"]["allocation_status"] == "reconciled"


@pytest.mark.asyncio
async def test_overallocation_beyond_tolerance_is_non_reconciling() -> None:
    service = _service(
        canonical=[_canonical_row("2026-08-01", 1_000_000)],
        allocated=[_allocated_row("2026-08-01", 1_300_000)],
    )
    payload = await service.get_data_quality(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 1),
    )
    allocation = payload["allocation"]
    assert allocation["allocation_status"] == "non_reconciling"
    assert allocation["canonical_spend_micros"] == 1_000_000
    assert allocation["allocated_spend_micros"] == 1_300_000
    assert allocation["difference_micros"] == 300_000
    assert allocation["difference_pct"] == 30.0
    assert any("relative ranking" in warning for warning in payload["warnings"])


@pytest.mark.asyncio
async def test_difference_within_tolerance_reconciles() -> None:
    service = _service(
        canonical=[_canonical_row("2026-08-01", 1_000_000)],
        allocated=[_allocated_row("2026-08-01", 1_005_000)],
    )
    payload = await service.get_data_quality(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 1),
        tolerance_pct=1.0,
    )
    assert payload["allocation"]["allocation_status"] == "reconciled"


@pytest.mark.asyncio
async def test_allocated_spend_without_canonical_is_non_reconciling() -> None:
    service = _service(allocated=[_allocated_row("2026-08-01", 500_000)])
    payload = await service.get_data_quality(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 1),
    )
    assert payload["allocation"]["allocation_status"] == "non_reconciling"
    assert payload["allocation"]["difference_pct"] is None


@pytest.mark.asyncio
async def test_empty_window_reconciles_and_reports_missing_dates() -> None:
    service = _service()
    payload = await service.get_data_quality(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )
    assert payload["allocation"]["allocation_status"] == "reconciled"
    assert payload["canonical"]["missing_dates"] == ["2026-08-01", "2026-08-02"]
    assert payload["canonical"]["latest_complete_date"] is None
    assert any("missing" in warning for warning in payload["warnings"])


@pytest.mark.asyncio
async def test_partial_canonical_coverage_sets_latest_complete_date() -> None:
    service = _service(
        canonical=[_canonical_row("2026-08-01", 100), _canonical_row("2026-08-02", 100)],
        allocated=[],
    )
    payload = await service.get_data_quality(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
    )
    assert payload["canonical"]["latest_complete_date"] == "2026-08-02"
    assert payload["canonical"]["missing_dates"] == ["2026-08-03"]
    assert payload["provenance"]["latest_source_date"] == "2026-08-02"


@pytest.mark.asyncio
async def test_range_and_buyer_validation() -> None:
    service = _service()
    with pytest.raises(HTTPException) as exc:
        await service.get_data_quality(
            buyer_id="buyer-1",
            start_date=date(2026, 8, 2),
            end_date=date(2026, 8, 1),
        )
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        await service.get_data_quality(
            buyer_id="buyer-1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
    assert exc.value.status_code == 400

    missing_buyer = AgentDataQualityService(repo=_StubQualityRepo(buyer=None))
    with pytest.raises(HTTPException) as exc:
        await missing_buyer.get_data_quality(
            buyer_id="nope",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 1),
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Daily-spend provenance envelope
# ---------------------------------------------------------------------------


class _StubStatsRepo:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def get_buyer(self, _buyer_id: str):
        return BUYER

    async def get_daily_spend_rows(self, _buyer_id, _start, _end):
        return self.rows


@pytest.mark.asyncio
async def test_daily_spend_carries_canonical_provenance() -> None:
    rows = [
        {
            "metric_date": date(2026, 8, 1),
            "impressions": 10,
            "clicks": 1,
            "spend_micros": 1_000_000,
            "source_row_count": 1,
            "app_count": 0,
            "billing_count": 0,
        },
        {
            "metric_date": date(2026, 8, 2),
            "impressions": 0,
            "clicks": 0,
            "spend_micros": 0,
            "source_row_count": 0,
            "app_count": 0,
            "billing_count": 0,
        },
    ]
    service = AgentStatsService(repo=_StubStatsRepo(rows))
    payload = await service.get_daily_spend(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )
    provenance = payload["provenance"]
    assert provenance["metric_source"] == "rtb_buyer_spend_daily"
    assert provenance["is_canonical"] is True
    assert provenance["buyer_scope"] == "buyer-1"
    assert provenance["latest_complete_date"] == "2026-08-01"
    assert provenance["latest_source_date"] == "2026-08-01"
    assert provenance["missing_source_dates"] == ["2026-08-02"]
    assert provenance["allocation"]["allocation_status"] == "not_applicable"


# ---------------------------------------------------------------------------
# Router: /buyers and /data-quality
# ---------------------------------------------------------------------------


class _StubAuthService:
    def __init__(self, buyer_ids: list[str] | None = None) -> None:
        self.buyer_ids = buyer_ids or []
        self.audit_calls: list[dict] = []

    async def get_user_buyer_seat_ids(self, _user_id: str):
        return self.buyer_ids

    async def log_audit(self, **kwargs):
        self.audit_calls.append(kwargs)
        return kwargs


class _StubBuyersStatsService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def list_buyers(self, **kwargs):
        self.calls.append(kwargs)
        count = len(kwargs["buyer_ids"]) if kwargs["buyer_ids"] is not None else 99
        return {
            "api_version": "agent.v1",
            "scope": {"source": kwargs["scope_source"], "buyer_count": count},
            "buyers": [],
        }


class _StubRouterQualityService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def get_data_quality(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "api_version": "agent.v1",
            "allocation": {"allocation_status": "reconciled"},
        }


def _context(role: str = "read", token_buyer_id: str | None = "buyer-1") -> AgentAuthContext:
    return AgentAuthContext(
        user=User(id="agent-user", email="agent@example.com", role=role),
        token=AgentTokenRecord(
            id="token-1",
            name="Research token",
            token_prefix="cat_agent_testprefix",
            user_id="agent-user",
            buyer_id=token_buyer_id,
            scopes=[AGENT_STATS_READ_SCOPE],
            expires_at="2026-12-31T00:00:00+00:00",
            is_active=True,
        ),
    )


def _router_client(
    context: AgentAuthContext,
    auth: _StubAuthService,
    stats: _StubBuyersStatsService | None = None,
    quality: _StubRouterQualityService | None = None,
) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[agent_router.require_agent_context] = lambda: context
    app.dependency_overrides[agent_router.get_auth_service] = lambda: auth
    app.dependency_overrides[agent_router.get_store] = lambda: SimpleNamespace()
    if stats is not None:
        app.dependency_overrides[agent_router.get_agent_stats_service] = lambda: stats
    if quality is not None:
        app.dependency_overrides[agent_router.get_agent_data_quality_service] = lambda: quality
    return SyncASGIClient(app)


def test_buyers_uses_token_hard_scope_when_present() -> None:
    stats = _StubBuyersStatsService()
    auth = _StubAuthService(["buyer-1", "buyer-2"])
    client = _router_client(_context(token_buyer_id="buyer-1"), auth, stats=stats)

    response = client.get("/api/agent/v1/buyers")
    assert response.status_code == 200
    assert stats.calls[0] == {"buyer_ids": ["buyer-1"], "scope_source": "token_hard_scope"}
    assert auth.audit_calls[0]["action"] == "agent_buyers_read"


def test_buyers_falls_back_to_seat_grants_for_unscoped_token() -> None:
    stats = _StubBuyersStatsService()
    auth = _StubAuthService(["buyer-1", "buyer-2", "buyer-1"])
    client = _router_client(_context(token_buyer_id=None), auth, stats=stats)

    response = client.get("/api/agent/v1/buyers")
    assert response.status_code == 200
    assert stats.calls[0] == {
        "buyer_ids": ["buyer-1", "buyer-2"],
        "scope_source": "seat_grants",
    }


def test_buyers_reports_sudo_unscoped_tokens_honestly() -> None:
    stats = _StubBuyersStatsService()
    auth = _StubAuthService([])
    client = _router_client(_context(role="sudo", token_buyer_id=None), auth, stats=stats)

    response = client.get("/api/agent/v1/buyers")
    assert response.status_code == 200
    assert stats.calls[0] == {"buyer_ids": None, "scope_source": "sudo_unscoped_token"}
    assert response.json()["scope"]["source"] == "sudo_unscoped_token"


def test_data_quality_rejects_buyer_outside_token_scope() -> None:
    quality = _StubRouterQualityService()
    auth = _StubAuthService(["buyer-1", "buyer-2"])
    client = _router_client(_context(role="sudo", token_buyer_id="buyer-1"), auth, quality=quality)

    response = client.get(
        "/api/agent/v1/data-quality",
        params={"buyer_id": "buyer-2", "start_date": "2026-08-01", "end_date": "2026-08-01"},
    )
    assert response.status_code == 403
    assert quality.calls == []


def test_data_quality_returns_payload_and_audits_read() -> None:
    quality = _StubRouterQualityService()
    auth = _StubAuthService(["buyer-1"])
    client = _router_client(_context(role="sudo", token_buyer_id="buyer-1"), auth, quality=quality)

    response = client.get(
        "/api/agent/v1/data-quality",
        params={"buyer_id": "buyer-1", "start_date": "2026-08-01", "end_date": "2026-08-07"},
    )
    assert response.status_code == 200
    assert quality.calls[0]["buyer_id"] == "buyer-1"
    assert quality.calls[0]["tolerance_pct"] == 1.0
    audit = auth.audit_calls[0]
    assert audit["action"] == "agent_data_quality_read"
    assert "allocation_status=reconciled" in audit["details"]
