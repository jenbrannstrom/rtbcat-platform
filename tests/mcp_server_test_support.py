"""In-process Agent API and MCP harness for Phase 3 contract tests."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

from api.routers import agent as agent_router
from api.routers import agent_creatives as creative_router
from mcp_server.client import AgentAPIClient
from mcp_server.config import MCPConfig
from mcp_server.ratelimit import TokenBucketRateLimiter
from mcp_server.server import MCPApplication, create_app
from services.agent_token_service import (
    AGENT_ASSETS_READ_SCOPE,
    AGENT_CREATIVE_PERFORMANCE_READ_SCOPE,
    AGENT_CREATIVES_READ_SCOPE,
    AGENT_STATS_READ_SCOPE,
    AgentAuthContext,
    AgentTokenRecord,
)
from services.auth_service import User


BUYER_A = "buyer-alpha"
BUYER_B = "buyer-beta"
CREATIVE_A = "creative-alpha"
MISSING_CREATIVE = "creative-missing"
CURSOR = "WzIwMDAwMDAsImNyZWF0aXZlLWFscGhhIl0="

TOKEN_A = "cat_agent_synthetic_alpha"
TOKEN_B = "cat_agent_synthetic_beta"
TOKEN_STATS = "cat_agent_synthetic_stats"
TOKEN_INVALID = "cat_agent_synthetic_invalid"

ALL_SCOPES = [
    AGENT_STATS_READ_SCOPE,
    AGENT_CREATIVES_READ_SCOPE,
    AGENT_CREATIVE_PERFORMANCE_READ_SCOPE,
    AGENT_ASSETS_READ_SCOPE,
]


def allocation(status: str = "reconciled") -> dict[str, Any]:
    allocated = 2_000_000 if status == "reconciled" else 2_600_000
    return {
        "allocation_status": status,
        "canonical_spend_micros": 2_000_000,
        "allocated_spend_micros": allocated,
        "difference_micros": allocated - 2_000_000,
        "difference_pct": (allocated - 2_000_000) / 2_000_000 * 100,
        "tolerance_pct": 1.0,
    }


def provenance(
    *,
    buyer_id: str = BUYER_A,
    status: str = "reconciled",
    canonical: bool = False,
) -> dict[str, Any]:
    return {
        "metric_source": (
            "rtb_buyer_spend_daily" if canonical else "config_creative_daily"
        ),
        "is_canonical": canonical,
        "buyer_scope": buyer_id,
        "latest_complete_date": "2026-08-01",
        "latest_source_date": "2026-08-02",
        "missing_source_dates": ["2026-08-02"],
        "allocation": allocation(status),
    }


def buyers_payload() -> dict[str, Any]:
    return {
        "api_version": "agent.v1",
        "scope": {"source": "token_hard_scope", "buyer_count": 1},
        "buyers": [
            {
                "buyer_id": BUYER_A,
                "bidder_id": "bidder-synthetic",
                "display_name": "Synthetic Buyer Alpha",
                "active": True,
                "currency": "USD",
                "last_synced": "2026-08-02T00:00:00+00:00",
            }
        ],
    }


def creative_search_payload(status: str = "reconciled") -> dict[str, Any]:
    return {
        "api_version": "agent.v1",
        "buyer_id": BUYER_A,
        "period": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "days": 2,
        },
        "source_table": "config_creative_daily",
        "creatives": [
            {
                "creative_id": CREATIVE_A,
                "buyer_id": BUYER_A,
                "name": "Synthetic Creative Alpha",
                "format": "HTML",
                "approval_status": "APPROVED",
                "destination_url": "https://ads.example/alpha",
                "resolved_destination_url": "https://ads.example/alpha",
                "preview_reference": (
                    f"/agent/v1/creatives/{CREATIVE_A}/assets"
                ),
                "activity_status": "active",
                "metrics": {
                    "spend_micros": 2_000_000,
                    "impressions": 1_000,
                    "spend_rank": 1,
                    "provenance": provenance(status=status),
                },
            }
        ],
        "next_cursor": CURSOR,
        "has_more": True,
    }


def creative_detail_payload() -> dict[str, Any]:
    return {
        "api_version": "agent.v1",
        "source_table": "creatives",
        "creative_id": CREATIVE_A,
        "buyer_id": BUYER_A,
        "name": "Synthetic Creative Alpha",
        "format": "HTML",
        "approval_status": "APPROVED",
        "width": 300,
        "height": 250,
        "canonical_size": "300x250",
        "final_url": "https://ads.example/alpha",
        "display_url": "ads.example",
        "advertiser_name": "Synthetic Advertiser",
        "campaign_id": "campaign-alpha",
        "app_id": None,
        "app_name": None,
        "app_store": None,
        "disapproval_reasons": [],
        "serving_restrictions": [],
        "first_seen_at": None,
        "created_at": None,
        "updated_at": None,
        "destination_diagnostics": {
            "resolved_destination_url": "https://ads.example/alpha",
            "candidate_count": 1,
            "eligible_count": 1,
            "candidates": [
                {
                    "source": "final_url",
                    "url": "https://ads.example/alpha",
                    "eligible": True,
                    "reason": None,
                }
            ],
            "has_any_macro": False,
            "has_click_macro": False,
            "macro_tokens": [],
            "click_macro_tokens": [],
            "has_payload_click_macro": False,
            "has_payload_only_click_macro": False,
            "payload_click_macro_tokens": [],
        },
        "assets_reference": f"/agent/v1/creatives/{CREATIVE_A}/assets",
    }


def creative_assets_payload() -> dict[str, Any]:
    return {
        "api_version": "agent.v1",
        "source_table": "creatives",
        "creative_id": CREATIVE_A,
        "buyer_id": BUYER_A,
        "format": "HTML",
        "references_only": True,
        "assets": {
            "thumbnail_reference": f"/api/thumbnails/{CREATIVE_A}.jpg",
            "video_reference": None,
            "video_thumbnail_reference": None,
            "html_thumbnail_reference": (
                f"/api/thumbnails/{CREATIVE_A}.jpg"
            ),
            "native_image_reference": None,
            "native_logo_reference": None,
        },
    }


def daily_spend_payload(status: str = "reconciled") -> dict[str, Any]:
    return {
        "api_version": "agent.v1",
        "buyer": {"buyer_id": BUYER_A, "currency": "USD"},
        "period": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "days": 2,
        },
        "data_source": {
            "table": "rtb_buyer_spend_daily",
            "precomputed_only": True,
            "currency": "USD",
        },
        "rows": [
            {
                "metric_date": "2026-08-01",
                "buyer_account_id": BUYER_A,
                "impressions": 1_000,
                "clicks": 5,
                "spend_micros": 2_000_000,
                "source_status": "present",
            }
        ],
        "summary": {
            "latest_complete_date": "2026-08-01",
            "missing_dates": ["2026-08-02"],
            "total_spend_micros": 2_000_000,
        },
        "provenance": provenance(status=status, canonical=True),
    }


def performance_payload(status: str = "reconciled") -> dict[str, Any]:
    return {
        "api_version": "agent.v1",
        "buyer_id": BUYER_A,
        "period": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "days": 2,
        },
        "source_tables": ["config_creative_daily"],
        "performance": [
            {
                "creative_id": CREATIVE_A,
                "total_impressions": 1_000,
                "total_clicks": None,
                "total_spend_micros": 2_000_000,
                "avg_cpm_micros": 2_000_000,
                "days_with_data": 1,
                "has_data": True,
                "metric_source": "config_creative_daily",
                "clicks_available": False,
                "provenance": provenance(status=status),
            }
        ],
        "count": 1,
    }


def quality_payload(status: str = "reconciled") -> dict[str, Any]:
    return {
        "api_version": "agent.v1",
        "buyer_id": BUYER_A,
        "period": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "days": 2,
        },
        "allocation": allocation(status),
        "provenance": provenance(status=status),
    }


class StubStatsService:
    def __init__(self, state: "StubState") -> None:
        self.state = state

    async def list_buyers(self, **_kwargs: Any) -> dict[str, Any]:
        if self.state.fail_buyers:
            raise HTTPException(500, detail="Synthetic upstream failure.")
        return copy.deepcopy(buyers_payload())

    async def get_daily_spend(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs["end_date"] < kwargs["start_date"]:
            raise HTTPException(
                400,
                detail="end_date must be on or after start_date.",
            )
        return copy.deepcopy(daily_spend_payload(self.state.allocation_status))


class StubCreativeService:
    def __init__(self, state: "StubState") -> None:
        self.state = state

    async def list_creatives(self, **kwargs: Any) -> dict[str, Any]:
        self.state.creative_search_calls.append(kwargs)
        return copy.deepcopy(
            creative_search_payload(self.state.allocation_status)
        )

    async def get_creative_detail(self, creative_id: str) -> dict[str, Any]:
        if creative_id == MISSING_CREATIVE:
            raise HTTPException(404, detail="Creative not found.")
        return copy.deepcopy(creative_detail_payload())

    async def get_creative_assets(self, creative_id: str) -> dict[str, Any]:
        if creative_id == MISSING_CREATIVE:
            raise HTTPException(404, detail="Creative not found.")
        return copy.deepcopy(creative_assets_payload())


class StubPerformanceService:
    def __init__(self, state: "StubState") -> None:
        self.state = state

    async def get_batch(self, **_kwargs: Any) -> dict[str, Any]:
        return copy.deepcopy(performance_payload(self.state.allocation_status))


class StubQualityService:
    def __init__(self, state: "StubState") -> None:
        self.state = state

    async def get_data_quality(self, **_kwargs: Any) -> dict[str, Any]:
        return copy.deepcopy(quality_payload(self.state.allocation_status))


class StubAuthService:
    async def log_audit(self, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    async def get_user_buyer_seat_ids(self, _user_id: str) -> list[str]:
        return [BUYER_A]


class StubState:
    def __init__(self, allocation_status: str = "reconciled") -> None:
        self.allocation_status = allocation_status
        self.api_requests = 0
        self.fail_buyers = False
        self.creative_search_calls: list[dict[str, Any]] = []


def auth_context(
    *,
    token_id: str,
    buyer_id: str,
    scopes: list[str],
) -> AgentAuthContext:
    return AgentAuthContext(
        user=User(
            id=f"user-{buyer_id}",
            email=f"agent-{buyer_id}@example.com",
            role="sudo",
        ),
        token=AgentTokenRecord(
            id=token_id,
            name="Synthetic test credential",
            token_prefix="cat_agent_synthetic",
            user_id=f"user-{buyer_id}",
            buyer_id=buyer_id,
            scopes=scopes,
            expires_at="2026-12-31T00:00:00+00:00",
            is_active=True,
        ),
    )


class CountingAgentApp:
    """Count HTTP calls without Starlette's task-spawning middleware."""

    def __init__(self, app: FastAPI, state: StubState) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            self.state.api_requests += 1
        await self.app(scope, receive, send)


def build_agent_app(state: StubState) -> CountingAgentApp:
    app = FastAPI()
    app.include_router(agent_router.router)
    app.include_router(creative_router.router)

    contexts = {
        TOKEN_A: auth_context(
            token_id="credential-alpha",
            buyer_id=BUYER_A,
            scopes=ALL_SCOPES,
        ),
        TOKEN_B: auth_context(
            token_id="credential-beta",
            buyer_id=BUYER_B,
            scopes=ALL_SCOPES,
        ),
        TOKEN_STATS: auth_context(
            token_id="credential-stats",
            buyer_id=BUYER_A,
            scopes=[AGENT_STATS_READ_SCOPE],
        ),
    }

    def require_context(required_scope: str):
        async def dependency(request: Request) -> AgentAuthContext:
            authorization = request.headers.get("authorization", "")
            scheme, separator, token = authorization.partition(" ")
            context = (
                contexts.get(token) if scheme.lower() == "bearer" else None
            )
            if not separator or context is None:
                raise HTTPException(
                    status_code=401,
                    detail="Agent bearer token required.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if required_scope not in context.token.scopes:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Agent token lacks required scope: "
                        f"{required_scope}."
                    ),
                )
            return context

        return dependency

    async def require_identity(request: Request) -> AgentAuthContext:
        authorization = request.headers.get("authorization", "")
        scheme, separator, token = authorization.partition(" ")
        context = contexts.get(token) if scheme.lower() == "bearer" else None
        if not separator or context is None:
            raise HTTPException(
                status_code=401,
                detail="Agent bearer token required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return context

    stats = StubStatsService(state)
    creatives = StubCreativeService(state)
    performance = StubPerformanceService(state)
    quality = StubQualityService(state)
    auth = StubAuthService()

    async def stats_dependency() -> StubStatsService:
        return stats

    async def quality_dependency() -> StubQualityService:
        return quality

    async def creative_dependency() -> StubCreativeService:
        return creatives

    async def performance_dependency() -> StubPerformanceService:
        return performance

    async def auth_dependency() -> StubAuthService:
        return auth

    async def store_dependency() -> SimpleNamespace:
        return SimpleNamespace()

    app.dependency_overrides[
        agent_router.get_agent_stats_service
    ] = stats_dependency
    app.dependency_overrides[
        agent_router.get_agent_data_quality_service
    ] = quality_dependency
    app.dependency_overrides[agent_router.get_auth_service] = auth_dependency
    app.dependency_overrides[agent_router.get_store] = store_dependency
    app.dependency_overrides[agent_router.require_agent_identity] = require_identity
    app.dependency_overrides[agent_router.require_agent_context] = require_context(
        AGENT_STATS_READ_SCOPE
    )
    app.dependency_overrides[
        creative_router.get_agent_creatives_service
    ] = creative_dependency
    app.dependency_overrides[
        creative_router.get_agent_creative_performance_service
    ] = performance_dependency
    app.dependency_overrides[
        creative_router.get_auth_service
    ] = auth_dependency
    app.dependency_overrides[
        creative_router.get_store
    ] = store_dependency
    app.dependency_overrides[
        creative_router.require_agent_creatives_context
    ] = require_context(AGENT_CREATIVES_READ_SCOPE)
    app.dependency_overrides[
        creative_router.require_agent_assets_context
    ] = require_context(AGENT_ASSETS_READ_SCOPE)
    app.dependency_overrides[
        creative_router.require_agent_creative_performance_context
    ] = require_context(AGENT_CREATIVE_PERFORMANCE_READ_SCOPE)
    return CountingAgentApp(app, state)


class MCPHarness:
    """Own both ASGI transports and the MCP server lifespan for one test."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        rate_limit: int = 60,
        allocation_status: str = "reconciled",
        limiter: TokenBucketRateLimiter | None = None,
        upstream_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.state = StubState(allocation_status)
        self.agent_app = build_agent_app(self.state)
        self.upstream_transport = upstream_transport or httpx.ASGITransport(
            app=self.agent_app
        )
        self.upstream_http = httpx.AsyncClient(
            transport=self.upstream_transport,
            base_url="http://agent.test",
        )
        self.agent_client = AgentAPIClient(
            "http://agent.test",
            client=self.upstream_http,
        )
        self.app: MCPApplication = create_app(
            MCPConfig(
                enabled=enabled,
                api_base_url="http://agent.test",
                rate_limit_per_minute=rate_limit,
            ),
            client=self.agent_client,
            rate_limiter=limiter,
        )
        self.mcp_http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://mcp.test",
        )
        self.direct_http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.agent_app),
            base_url="http://agent.test",
        )
        self._lifespan = self.app.mcp_app.router.lifespan_context(
            self.app.mcp_app
        )

    async def __aenter__(self) -> "MCPHarness":
        await self._lifespan.__aenter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.mcp_http.aclose()
        await self.direct_http.aclose()
        await self._lifespan.__aexit__(*args)
        await self.upstream_http.aclose()

    async def mcp_request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        token: str | None = TOKEN_A,
    ) -> httpx.Response:
        headers = {"accept": "application/json, text/event-stream"}
        if token is not None:
            headers["authorization"] = f"Bearer {token}"
        return await self.mcp_http.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            },
        )

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        token: str | None = TOKEN_A,
    ) -> dict[str, Any]:
        response = await self.mcp_request(
            "tools/call",
            {"name": name, "arguments": arguments},
            token=token,
        )
        assert response.status_code == 200, response.text
        return response.json()

    @staticmethod
    def tool_payload(message: dict[str, Any]) -> dict[str, Any]:
        text = message["result"]["content"][0]["text"]
        payload = json.loads(text)
        assert isinstance(payload, dict)
        return payload

    async def direct_request(
        self,
        method: str,
        path: str,
        *,
        token: str = TOKEN_A,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self.direct_http.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            json=json_body,
        )


SEARCH_ARGUMENTS = {
    "buyer_id": BUYER_A,
    "start_date": "2026-08-01",
    "end_date": "2026-08-02",
    "limit": 50,
}

PERFORMANCE_ARGUMENTS = {
    "buyer_id": BUYER_A,
    "creative_ids": [CREATIVE_A],
    "start_date": "2026-08-01",
    "end_date": "2026-08-02",
}

WINDOW_ARGUMENTS = {
    "buyer_id": BUYER_A,
    "start_date": "2026-08-01",
    "end_date": "2026-08-02",
}
