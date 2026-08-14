"""Tests for Agent API creative search, detail, and asset contracts."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from api.routers import agent_creatives as agent_creatives_router
from services.agent_creatives_service import AgentCreativesService, _encode_cursor
from services.agent_token_service import (
    AGENT_ASSETS_READ_SCOPE,
    AGENT_CREATIVES_READ_SCOPE,
    AGENT_STATS_READ_SCOPE,
    AgentAuthContext,
    AgentTokenRecord,
)
from services.auth_service import User
from tests.support.asgi_client import SyncASGIClient


def _creative_row(
    creative_id: str,
    spend_micros: int,
    spend_rank: int,
) -> dict:
    return {
        "creative_id": creative_id,
        "buyer_id": "buyer-1",
        "name": f"Creative {creative_id}",
        "format": "HTML",
        "approval_status": "APPROVED",
        "final_url": f"https://ads.example/{creative_id}",
        "display_url": "ads.example",
        "raw_data": {
            "declaredClickThroughUrls": [f"https://ads.example/{creative_id}"]
        },
        "spend_micros": spend_micros,
        "impressions": spend_micros // 100,
        "source_dates": [date(2026, 8, 1), date(2026, 8, 2)],
        "spend_rank": spend_rank,
    }


class _StubCreativesRepo:
    def __init__(
        self,
        rows: list[dict] | None = None,
        detail: dict | None = None,
    ) -> None:
        self.rows = rows or []
        self.detail = detail
        self.calls: list[dict] = []

    async def list_creatives(self, **kwargs):
        self.calls.append(kwargs)
        rows = sorted(
            self.rows,
            key=lambda row: (-row["spend_micros"], row["creative_id"]),
        )
        cursor = kwargs["cursor"]
        if cursor:
            rows = [
                row
                for row in rows
                if row["spend_micros"] < cursor[0]
                or (
                    row["spend_micros"] == cursor[0]
                    and row["creative_id"] > cursor[1]
                )
            ]
        return rows[: kwargs["limit"]]

    async def get_creative(self, creative_id: str):
        self.calls.append({"creative_id": creative_id})
        return self.detail


class _StubAuthService:
    def __init__(self) -> None:
        self.audit_calls: list[dict] = []

    async def log_audit(self, **kwargs):
        self.audit_calls.append(kwargs)
        return kwargs


def _context(
    *,
    buyer_id: str | None = "buyer-1",
    scopes: list[str] | None = None,
) -> AgentAuthContext:
    return AgentAuthContext(
        user=User(id="agent-user", email="agent@example.com", role="sudo"),
        token=AgentTokenRecord(
            id="token-1",
            name="Creative read token",
            token_prefix="cat_agent_testprefix",
            user_id="agent-user",
            buyer_id=buyer_id,
            scopes=scopes or [AGENT_CREATIVES_READ_SCOPE],
            expires_at="2026-12-31T00:00:00+00:00",
            is_active=True,
        ),
    )


def _router_client(
    *,
    context: AgentAuthContext,
    repo: _StubCreativesRepo,
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
            agent_creatives_router.require_agent_creatives_context
        ] = lambda: context
        app.dependency_overrides[
            agent_creatives_router.require_agent_assets_context
        ] = lambda: context
    service = AgentCreativesService(repo=repo)
    app.dependency_overrides[
        agent_creatives_router.get_agent_creatives_service
    ] = lambda: service
    app.dependency_overrides[agent_creatives_router.get_auth_service] = lambda: auth
    app.dependency_overrides[agent_creatives_router.get_store] = (
        lambda: SimpleNamespace()
    )
    return SyncASGIClient(app)


def _list_params(**overrides) -> dict:
    params = {
        "buyer_id": "buyer-1",
        "start_date": "2026-08-01",
        "end_date": "2026-08-02",
    }
    params.update(overrides)
    return params


@pytest.mark.asyncio
async def test_creatives_list_full_schema_and_filter_semantics() -> None:
    repo = _StubCreativesRepo([_creative_row("creative-a", 2_000, 1)])
    service = AgentCreativesService(repo=repo)

    payload = await service.list_creatives(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        domain="https://ADS.EXAMPLE/path",
        creative_format="html",
        approval_filter="not_approved",
        activity="active",
        search="campaign term",
        limit=50,
    )

    assert payload == {
        "api_version": "agent.v1",
        "buyer_id": "buyer-1",
        "period": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "days": 2,
        },
        "source_table": "config_creative_daily",
        "creatives": [
            {
                "creative_id": "creative-a",
                "buyer_id": "buyer-1",
                "name": "Creative creative-a",
                "format": "HTML",
                "approval_status": "APPROVED",
                "destination_url": "https://ads.example/creative-a",
                "resolved_destination_url": "https://ads.example/creative-a",
                "preview_reference": (
                    "/api/agent/v1/creatives/creative-a/assets"
                ),
                "activity_status": "active",
                "metrics": {
                    "spend_micros": 2_000,
                    "impressions": 20,
                    "spend_rank": 1,
                    "provenance": {
                        "metric_source": "config_creative_daily",
                        "is_canonical": False,
                        "buyer_scope": "buyer-1",
                        "latest_complete_date": "2026-08-02",
                        "latest_source_date": "2026-08-02",
                        "missing_source_dates": [],
                        "allocation": {
                            "allocation_status": "not_applicable",
                            "canonical_spend_micros": None,
                            "allocated_spend_micros": None,
                            "difference_micros": None,
                            "difference_pct": None,
                            "tolerance_pct": None,
                        },
                    },
                },
            }
        ],
        "next_cursor": None,
        "has_more": False,
    }
    assert repo.calls == [
        {
            "buyer_id": "buyer-1",
            "start_date": date(2026, 8, 1),
            "end_date": date(2026, 8, 2),
            "domain": "ads.example",
            "creative_format": "HTML",
            "approval_filter": "not_approved",
            "activity": "active",
            "search": "campaign term",
            "cursor": None,
            "limit": 51,
        }
    ]


@pytest.mark.asyncio
async def test_creatives_list_cursor_is_stable_across_two_pages() -> None:
    rows = [
        _creative_row("creative-a", 2_000, 1),
        _creative_row("creative-b", 1_000, 2),
        _creative_row("creative-c", 1_000, 3),
    ]
    service = AgentCreativesService(repo=_StubCreativesRepo(rows))

    first = await service.list_creatives(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        limit=2,
    )
    second = await service.list_creatives(
        buyer_id="buyer-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        cursor=first["next_cursor"],
        limit=2,
    )

    assert [row["creative_id"] for row in first["creatives"]] == [
        "creative-a",
        "creative-b",
    ]
    assert first["next_cursor"] == _encode_cursor(1_000, "creative-b")
    assert first["has_more"] is True
    assert [row["creative_id"] for row in second["creatives"]] == ["creative-c"]
    assert second["next_cursor"] is None
    assert second["has_more"] is False


def test_creatives_list_rejects_buyer_outside_token_scope() -> None:
    repo = _StubCreativesRepo()
    client = _router_client(
        context=_context(buyer_id="buyer-1"),
        repo=repo,
        auth=_StubAuthService(),
    )

    response = client.get(
        "/api/agent/v1/creatives",
        params=_list_params(buyer_id="buyer-2"),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Agent token is not scoped to this buyer."
    }
    assert repo.calls == []


def test_creatives_list_rejects_stats_only_scope() -> None:
    client = _router_client(
        context=_context(scopes=[AGENT_STATS_READ_SCOPE]),
        repo=_StubCreativesRepo(),
        auth=_StubAuthService(),
        enforce_real_scope=True,
    )

    response = client.get("/api/agent/v1/creatives", params=_list_params())

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Agent token lacks required scope: agent:creatives:read."
        )
    }


def test_creatives_list_router_returns_full_schema_and_audits() -> None:
    repo = _StubCreativesRepo([_creative_row("creative-a", 2_000, 1)])
    auth = _StubAuthService()
    client = _router_client(
        context=_context(),
        repo=repo,
        auth=auth,
    )

    response = client.get("/api/agent/v1/creatives", params=_list_params())

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "api_version",
        "buyer_id",
        "period",
        "source_table",
        "creatives",
        "next_cursor",
        "has_more",
    }
    assert set(body["creatives"][0]) == {
        "creative_id",
        "buyer_id",
        "name",
        "format",
        "approval_status",
        "destination_url",
        "resolved_destination_url",
        "preview_reference",
        "activity_status",
        "metrics",
    }
    assert set(body["creatives"][0]["metrics"]["provenance"]) == {
        "metric_source",
        "is_canonical",
        "buyer_scope",
        "latest_complete_date",
        "latest_source_date",
        "missing_source_dates",
        "allocation",
    }
    assert auth.audit_calls[0]["action"] == "agent_creatives_read"
    assert auth.audit_calls[0]["resource_id"] == "buyer-1"


def test_creatives_list_rejects_clicks_sort() -> None:
    repo = _StubCreativesRepo()
    client = _router_client(
        context=_context(),
        repo=repo,
        auth=_StubAuthService(),
    )

    response = client.get(
        "/api/agent/v1/creatives",
        params=_list_params(sort_by="clicks"),
    )

    assert response.status_code == 422
    assert repo.calls == []

def _detail_row(*, buyer_id: str = "buyer-1") -> dict:
    return {
        "creative_id": "creative-a",
        "buyer_id": buyer_id,
        "name": "Creative creative-a",
        "format": "HTML",
        "approval_status": "APPROVED",
        "width": 300,
        "height": 250,
        "canonical_size": "300x250",
        "final_url": "https://ads.example/landing",
        "display_url": "ads.example",
        "advertiser_name": "Synthetic Advertiser",
        "campaign_id": "campaign-1",
        "app_id": None,
        "app_name": None,
        "app_store": None,
        "disapproval_reasons": [],
        "serving_restrictions": ["US"],
        "first_seen_at": None,
        "created_at": None,
        "updated_at": None,
        "raw_data": {
            "declaredClickThroughUrls": ["https://ads.example/landing"],
            "html": {"snippet": "<a href='https://ads.example/landing'>Ad</a>"},
        },
    }


def _expected_detail(*, buyer_id: str = "buyer-1") -> dict:
    return {
        "api_version": "agent.v1",
        "source_table": "creatives",
        "creative_id": "creative-a",
        "buyer_id": buyer_id,
        "name": "Creative creative-a",
        "format": "HTML",
        "approval_status": "APPROVED",
        "width": 300,
        "height": 250,
        "canonical_size": "300x250",
        "final_url": "https://ads.example/landing",
        "display_url": "ads.example",
        "advertiser_name": "Synthetic Advertiser",
        "campaign_id": "campaign-1",
        "app_id": None,
        "app_name": None,
        "app_store": None,
        "disapproval_reasons": [],
        "serving_restrictions": ["US"],
        "first_seen_at": None,
        "created_at": None,
        "updated_at": None,
        "destination_diagnostics": {
            "resolved_destination_url": "https://ads.example/landing",
            "candidate_count": 4,
            "eligible_count": 1,
            "candidates": [
                {
                    "source": "final_url",
                    "url": "https://ads.example/landing",
                    "eligible": True,
                    "reason": None,
                },
                {
                    "source": "display_url",
                    "url": "ads.example",
                    "eligible": False,
                    "reason": "unsupported_scheme",
                },
                {
                    "source": "declared_click_through_url",
                    "url": "https://ads.example/landing",
                    "eligible": False,
                    "reason": "duplicate",
                },
                {
                    "source": "html_snippet",
                    "url": "https://ads.example/landing",
                    "eligible": False,
                    "reason": "duplicate",
                },
            ],
            "has_any_macro": False,
            "has_click_macro": False,
            "macro_tokens": [],
            "click_macro_tokens": [],
            "has_payload_click_macro": False,
            "has_payload_only_click_macro": False,
            "payload_click_macro_tokens": [],
        },
        "assets_reference": "/api/agent/v1/creatives/creative-a/assets",
    }


@pytest.mark.asyncio
async def test_creative_detail_full_schema_with_destination_diagnostics() -> None:
    repo = _StubCreativesRepo(detail=_detail_row())
    service = AgentCreativesService(repo=repo)

    payload = await service.get_creative_detail("creative-a")

    assert payload == _expected_detail()
    assert repo.calls == [{"creative_id": "creative-a"}]


def test_creative_detail_outside_buyer_matches_missing_shape() -> None:
    outside_repo = _StubCreativesRepo(detail=_detail_row(buyer_id="buyer-2"))
    outside_client = _router_client(
        context=_context(buyer_id="buyer-1"),
        repo=outside_repo,
        auth=_StubAuthService(),
    )
    missing_client = _router_client(
        context=_context(buyer_id="buyer-1"),
        repo=_StubCreativesRepo(detail=None),
        auth=_StubAuthService(),
    )

    outside_response = outside_client.get(
        "/api/agent/v1/creatives/creative-a"
    )
    missing_response = missing_client.get(
        "/api/agent/v1/creatives/creative-a"
    )

    assert outside_response.status_code == 404
    assert missing_response.status_code == 404
    assert outside_response.json() == missing_response.json() == {
        "detail": "Creative not found."
    }


def test_creative_detail_rejects_stats_only_scope() -> None:
    client = _router_client(
        context=_context(scopes=[AGENT_STATS_READ_SCOPE]),
        repo=_StubCreativesRepo(detail=_detail_row()),
        auth=_StubAuthService(),
        enforce_real_scope=True,
    )

    response = client.get("/api/agent/v1/creatives/creative-a")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Agent token lacks required scope: agent:creatives:read."
    }


def test_creative_detail_router_returns_full_schema_and_audits() -> None:
    auth = _StubAuthService()
    client = _router_client(
        context=_context(),
        repo=_StubCreativesRepo(detail=_detail_row()),
        auth=auth,
    )

    response = client.get("/api/agent/v1/creatives/creative-a")

    assert response.status_code == 200
    assert response.json() == _expected_detail()
    assert auth.audit_calls[0]["action"] == "agent_creatives_read"
    assert auth.audit_calls[0]["resource_id"] == "creative-a"
    assert "read=detail" in auth.audit_calls[0]["details"]


def _expected_assets(*, buyer_id: str = "buyer-1") -> dict:
    return {
        "api_version": "agent.v1",
        "source_table": "creatives",
        "creative_id": "creative-a",
        "buyer_id": buyer_id,
        "format": "HTML",
        "references_only": True,
        "assets": {
            "thumbnail_reference": "/api/thumbnails/creative-a.jpg",
            "video_reference": None,
            "video_thumbnail_reference": None,
            "html_thumbnail_reference": "/api/thumbnails/creative-a.jpg",
            "native_image_reference": None,
            "native_logo_reference": None,
        },
    }


@pytest.mark.asyncio
async def test_creative_assets_full_reference_only_schema() -> None:
    repo = _StubCreativesRepo(detail=_detail_row())
    service = AgentCreativesService(repo=repo)

    payload = await service.get_creative_assets("creative-a")

    assert payload == _expected_assets()
    assert "snippet" not in str(payload)
    assert repo.calls == [{"creative_id": "creative-a"}]


def test_creative_assets_outside_buyer_matches_missing_shape() -> None:
    outside_client = _router_client(
        context=_context(
            buyer_id="buyer-1",
            scopes=[AGENT_ASSETS_READ_SCOPE],
        ),
        repo=_StubCreativesRepo(detail=_detail_row(buyer_id="buyer-2")),
        auth=_StubAuthService(),
    )
    missing_client = _router_client(
        context=_context(
            buyer_id="buyer-1",
            scopes=[AGENT_ASSETS_READ_SCOPE],
        ),
        repo=_StubCreativesRepo(detail=None),
        auth=_StubAuthService(),
    )

    outside_response = outside_client.get(
        "/api/agent/v1/creatives/creative-a/assets"
    )
    missing_response = missing_client.get(
        "/api/agent/v1/creatives/creative-a/assets"
    )

    assert outside_response.status_code == 404
    assert missing_response.status_code == 404
    assert outside_response.json() == missing_response.json() == {
        "detail": "Creative not found."
    }


def test_creative_assets_rejects_stats_only_scope() -> None:
    client = _router_client(
        context=_context(scopes=[AGENT_STATS_READ_SCOPE]),
        repo=_StubCreativesRepo(detail=_detail_row()),
        auth=_StubAuthService(),
        enforce_real_scope=True,
    )

    response = client.get(
        "/api/agent/v1/creatives/creative-a/assets"
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Agent token lacks required scope: agent:assets:read."
    }


def test_creative_assets_router_returns_full_schema_and_audits() -> None:
    auth = _StubAuthService()
    client = _router_client(
        context=_context(scopes=[AGENT_ASSETS_READ_SCOPE]),
        repo=_StubCreativesRepo(detail=_detail_row()),
        auth=auth,
    )

    response = client.get(
        "/api/agent/v1/creatives/creative-a/assets"
    )

    assert response.status_code == 200
    assert response.json() == _expected_assets()
    assert auth.audit_calls[0]["action"] == "agent_asset_read"
    assert auth.audit_calls[0]["resource_id"] == "creative-a"
    assert "read=asset_references" in auth.audit_calls[0]["details"]
