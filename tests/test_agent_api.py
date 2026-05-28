from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI

from api.routers import agent as agent_router
from services.agent_token_service import AGENT_STATS_READ_SCOPE, AgentAuthContext, AgentTokenRecord
from services.auth_service import User
from tests.support.asgi_client import SyncASGIClient


class _StubStatsService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def get_stats_summary(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "api_version": "agent.v1",
            "buyer": {"buyer_id": kwargs["buyer_id"]},
            "period": {"days": kwargs["days"]},
            "totals": {"impressions": 100},
            "email_summary": {
                "subject": "Buyer 7-day Cat-Scan performance summary",
                "bullets": ["Reached 1,000 queries."],
                "markdown": "- Reached 1,000 queries.",
            },
        }


class _StubAuthService:
    def __init__(self, buyer_ids: list[str] | None = None) -> None:
        self.audit_calls: list[dict] = []
        self.buyer_ids = buyer_ids or ["buyer-1"]

    async def get_user_by_id(self, user_id: str):
        return User(id=user_id, email="agent@example.com", role="read", is_active=True)

    async def get_user_buyer_seat_ids(self, _user_id: str):
        return self.buyer_ids

    async def log_audit(self, **kwargs):
        self.audit_calls.append(kwargs)
        return kwargs


class _StubTokenService:
    def __init__(self) -> None:
        self.create_calls: list[dict] = []

    async def create_token(self, **kwargs):
        self.create_calls.append(kwargs)
        return SimpleNamespace(
            token="cat_agent_plaintext",
            record=AgentTokenRecord(
                id="token-1",
                name=kwargs["name"],
                token_prefix="cat_agent_plain",
                user_id=kwargs["user_id"],
                buyer_id=kwargs["buyer_id"],
                scopes=kwargs["scopes"],
                expires_at="2026-12-31T00:00:00+00:00",
                is_active=True,
                user_email="agent@example.com",
            ),
        )


def _context(token_buyer_id: str | None = "buyer-1") -> AgentAuthContext:
    return AgentAuthContext(
        user=User(id="agent-user", email="agent@example.com", role="sudo"),
        token=AgentTokenRecord(
            id="token-1",
            name="Daily report",
            token_prefix="cat_agent_testprefix",
            user_id="agent-user",
            buyer_id=token_buyer_id,
            scopes=[AGENT_STATS_READ_SCOPE],
            expires_at="2026-12-31T00:00:00+00:00",
            is_active=True,
        ),
    )


def _client(stats: _StubStatsService, auth: _StubAuthService, context: AgentAuthContext) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[agent_router.require_agent_context] = lambda: context
    app.dependency_overrides[agent_router.get_agent_stats_service] = lambda: stats
    app.dependency_overrides[agent_router.get_auth_service] = lambda: auth
    app.dependency_overrides[agent_router.get_store] = lambda: SimpleNamespace()
    return SyncASGIClient(app)


def test_stats_summary_returns_email_ready_payload_and_audits_read() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()
    client = _client(stats, auth, _context())

    response = client.get("/api/agent/v1/stats-summary?buyer_id=buyer-1&days=7&top_limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_version"] == "agent.v1"
    assert payload["email_summary"]["markdown"].startswith("- Reached")
    assert stats.calls == [{"buyer_id": "buyer-1", "days": 7, "top_limit": 10}]
    assert auth.audit_calls[0]["action"] == "agent_stats_summary_read"
    assert auth.audit_calls[0]["resource_id"] == "buyer-1"


def test_stats_summary_rejects_buyer_outside_token_hard_scope() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()
    client = _client(stats, auth, _context(token_buyer_id="buyer-2"))

    response = client.get("/api/agent/v1/stats-summary?buyer_id=buyer-1")

    assert response.status_code == 403
    assert response.json()["detail"] == "Agent token is not scoped to this buyer."
    assert stats.calls == []


def test_create_token_defaults_to_single_buyer_hard_scope() -> None:
    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    auth = _StubAuthService(buyer_ids=["buyer-1"])
    token_service = _StubTokenService()
    app.dependency_overrides[agent_router.require_token_admin] = lambda: User(
        id="admin-user",
        email="admin@example.com",
        role="sudo",
    )
    app.dependency_overrides[agent_router.get_auth_service] = lambda: auth
    app.dependency_overrides[agent_router.get_agent_token_service] = lambda: token_service
    client = SyncASGIClient(app)

    response = client.post(
        "/api/agent/v1/tokens",
        json={
            "name": "Daily report",
            "user_id": "agent-user",
            "expires_in_days": 30,
        },
    )

    assert response.status_code == 200
    assert token_service.create_calls[0]["buyer_id"] == "buyer-1"
    assert response.json()["token"].startswith("cat_agent_")
    assert response.json()["token_record"]["buyer_id"] == "buyer-1"


def test_create_token_requires_buyer_id_for_multi_buyer_user() -> None:
    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[agent_router.require_token_admin] = lambda: User(
        id="admin-user",
        email="admin@example.com",
        role="sudo",
    )
    app.dependency_overrides[agent_router.get_auth_service] = lambda: _StubAuthService(
        buyer_ids=["buyer-1", "buyer-2"]
    )
    app.dependency_overrides[agent_router.get_agent_token_service] = lambda: _StubTokenService()
    client = SyncASGIClient(app)

    response = client.post(
        "/api/agent/v1/tokens",
        json={
            "name": "Daily report",
            "user_id": "agent-user",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "buyer_id is required when agent user has multiple buyer grants."


def test_global_api_key_context_cannot_manage_agent_tokens() -> None:
    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")

    async def api_key_admin():
        return User(id="api-key-automation", email="api-key@automation.local", role="sudo")

    app.dependency_overrides[agent_router.require_admin] = api_key_admin

    @app.middleware("http")
    async def mark_api_key_auth(request, call_next):
        request.state.api_key_authenticated = True
        return await call_next(request)

    client = SyncASGIClient(app)

    response = client.post(
        "/api/agent/v1/tokens",
        json={
            "name": "Daily report",
            "user_id": "agent-user",
            "buyer_id": "buyer-1",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Global API-key automation cannot manage agent tokens. Use a sudo user session."
    )
