from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI

from api.routers import agent as agent_router
from services.agent_token_service import AGENT_STATS_READ_SCOPE, AgentAuthContext, AgentTokenRecord
from services.auth_service import User
from tests.support.asgi_client import SyncASGIClient


class _StubStatsService:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.daily_spend_calls: list[dict] = []
        self.list_buyers_calls: list[dict] = []

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

    async def list_buyers(self, **kwargs):
        self.list_buyers_calls.append(kwargs)
        buyer_ids = kwargs["buyer_ids"] or []
        return {
            "api_version": "agent.v1",
            "scope": {"source": kwargs["scope_source"], "buyer_count": len(buyer_ids)},
            "buyers": [{"buyer_id": buyer_id} for buyer_id in buyer_ids],
        }

    async def get_daily_spend(self, **kwargs):
        self.daily_spend_calls.append(kwargs)
        return {
            "api_version": "agent.v1",
            "buyer": {"buyer_id": kwargs["buyer_id"]},
            "period": {
                "start_date": kwargs["start_date"].isoformat(),
                "end_date": kwargs["end_date"].isoformat(),
                "days": 1,
            },
            "data_source": {"table": "rtb_buyer_spend_daily", "precomputed_only": True},
            "rows": [
                {
                    "metric_date": kwargs["start_date"].isoformat(),
                    "buyer_account_id": kwargs["buyer_id"],
                    "impressions": 4200,
                    "clicks": 17,
                    "spend_micros": 12_500_000,
                    "source_row_count": 3,
                    "app_count": 2,
                    "billing_count": 1,
                    "source_status": "present",
                }
            ],
            "summary": {
                "requested_days": 1,
                "days_with_source_rows": 1,
                "total_impressions": 4200,
                "total_clicks": 17,
                "total_spend_micros": 12_500_000,
            },
            "warnings": [],
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


def _context(
    token_buyer_id: str | None = "buyer-1",
    token_buyer_ids: list[str] | None = None,
    role: str = "sudo",
) -> AgentAuthContext:
    return AgentAuthContext(
        user=User(id="agent-user", email="agent@example.com", role=role),
        token=AgentTokenRecord(
            id="token-1",
            name="Daily report",
            token_prefix="cat_agent_testprefix",
            user_id="agent-user",
            buyer_id=token_buyer_id,
            buyer_ids=token_buyer_ids,
            scopes=[AGENT_STATS_READ_SCOPE],
            expires_at="2026-12-31T00:00:00+00:00",
            is_active=True,
        ),
    )


def _client(stats: _StubStatsService, auth: _StubAuthService, context: AgentAuthContext) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[agent_router.require_agent_context] = lambda: context
    app.dependency_overrides[agent_router.require_agent_identity] = lambda: context
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


def test_daily_spend_returns_date_explicit_payload_and_audits_read() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()
    client = _client(stats, auth, _context())

    response = client.get(
        "/api/agent/v1/daily-spend?buyer_id=buyer-1&start_date=2026-07-01&end_date=2026-07-01"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_version"] == "agent.v1"
    assert payload["rows"][0]["metric_date"] == "2026-07-01"
    assert payload["rows"][0]["source_status"] == "present"
    assert payload["summary"]["total_spend_micros"] == 12_500_000
    assert stats.daily_spend_calls == [
        {
            "buyer_id": "buyer-1",
            "start_date": date(2026, 7, 1),
            "end_date": date(2026, 7, 1),
            "include_empty": True,
        }
    ]
    assert auth.audit_calls[0]["action"] == "agent_daily_spend_read"
    assert auth.audit_calls[0]["resource_id"] == "buyer-1"
    assert "start_date=2026-07-01" in auth.audit_calls[0]["details"]


def test_daily_spend_rejects_buyer_outside_token_hard_scope() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()
    client = _client(stats, auth, _context(token_buyer_id="buyer-2"))

    response = client.get(
        "/api/agent/v1/daily-spend?buyer_id=buyer-1&start_date=2026-07-01&end_date=2026-07-01"
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Agent token is not scoped to this buyer."
    assert stats.daily_spend_calls == []


def test_daily_spend_rejects_invalid_date_format_with_422() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()
    client = _client(stats, auth, _context())

    response = client.get(
        "/api/agent/v1/daily-spend?buyer_id=buyer-1&start_date=not-a-date&end_date=2026-07-01"
    )

    assert response.status_code == 422
    assert stats.daily_spend_calls == []


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
    assert response.json()["detail"].startswith(
        "buyer_id is required when agent user has multiple buyer grants"
    )


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


# ---------------------------------------------------------------------------
# Explicit buyer-list (buyer_ids) hard-scope
# ---------------------------------------------------------------------------

FINANCE_BUYER_IDS = ["1487810529", "6574658621", "6634662463", "7942355670", "8087233591"]
_DAILY_SPEND_WINDOW = "start_date=2026-07-01&end_date=2026-07-01"


def _list_context(role: str = "sudo", buyer_ids: list[str] | None = None) -> AgentAuthContext:
    return _context(
        token_buyer_id=None,
        token_buyer_ids=FINANCE_BUYER_IDS if buyer_ids is None else buyer_ids,
        role=role,
    )


def test_sudo_list_token_reads_daily_spend_for_each_listed_buyer() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()
    client = _client(stats, auth, _list_context())

    for buyer_id in FINANCE_BUYER_IDS:
        response = client.get(
            f"/api/agent/v1/daily-spend?buyer_id={buyer_id}&{_DAILY_SPEND_WINDOW}"
        )
        assert response.status_code == 200
        assert response.json()["buyer"]["buyer_id"] == buyer_id

    assert [call["buyer_id"] for call in stats.daily_spend_calls] == FINANCE_BUYER_IDS
    assert [call["resource_id"] for call in auth.audit_calls] == FINANCE_BUYER_IDS


def test_sudo_list_token_rejects_buyer_outside_the_list_on_every_stats_route() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()
    client = _client(stats, auth, _list_context())

    for path in (
        f"/api/agent/v1/daily-spend?buyer_id=299038253&{_DAILY_SPEND_WINDOW}",
        "/api/agent/v1/stats-summary?buyer_id=299038253",
        f"/api/agent/v1/data-quality?buyer_id=299038253&{_DAILY_SPEND_WINDOW}",
    ):
        response = client.get(path)
        assert response.status_code == 403
        assert response.json()["detail"] == "Agent token is not scoped to this buyer."

    assert stats.daily_spend_calls == []
    assert stats.calls == []
    assert auth.audit_calls == []


def test_list_token_with_empty_list_denies_every_buyer() -> None:
    stats = _StubStatsService()
    client = _client(stats, _StubAuthService(), _list_context(buyer_ids=[]))

    response = client.get(
        f"/api/agent/v1/daily-spend?buyer_id={FINANCE_BUYER_IDS[0]}&{_DAILY_SPEND_WINDOW}"
    )

    assert response.status_code == 403
    assert stats.daily_spend_calls == []


def test_me_reports_the_buyer_list() -> None:
    client = _client(_StubStatsService(), _StubAuthService(), _list_context())

    response = client.get("/api/agent/v1/me")

    assert response.status_code == 200
    assert response.json()["buyer_ids"] == FINANCE_BUYER_IDS
    assert response.json()["buyer_id"] is None


def test_me_for_single_buyer_token_is_unchanged() -> None:
    client = _client(_StubStatsService(), _StubAuthService(), _context())

    payload = client.get("/api/agent/v1/me").json()

    assert payload["buyer_id"] == "buyer-1"
    assert payload["buyer_ids"] is None


def test_buyer_listing_reports_exactly_the_listed_buyers() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()
    client = _client(stats, auth, _list_context())

    response = client.get("/api/agent/v1/buyers")

    assert response.status_code == 200
    assert [buyer["buyer_id"] for buyer in response.json()["buyers"]] == FINANCE_BUYER_IDS
    assert stats.list_buyers_calls == [
        {"buyer_ids": FINANCE_BUYER_IDS, "scope_source": "token_hard_scope"}
    ]
    assert auth.audit_calls[0]["resource_id"] == ",".join(FINANCE_BUYER_IDS)


def test_buyer_listing_for_non_sudo_list_token_drops_revoked_grants() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService(buyer_ids=FINANCE_BUYER_IDS[:2])
    client = _client(stats, auth, _list_context(role="read"))

    response = client.get("/api/agent/v1/buyers")

    assert response.status_code == 200
    assert stats.list_buyers_calls[0]["buyer_ids"] == FINANCE_BUYER_IDS[:2]


def test_buyer_listing_for_single_buyer_and_legacy_unscoped_tokens_is_unchanged() -> None:
    stats = _StubStatsService()
    auth = _StubAuthService()

    _client(stats, auth, _context()).get("/api/agent/v1/buyers")
    _client(stats, auth, _context(token_buyer_id=None)).get("/api/agent/v1/buyers")
    _client(stats, auth, _context(token_buyer_id=None, role="read")).get("/api/agent/v1/buyers")

    assert stats.list_buyers_calls == [
        {"buyer_ids": ["buyer-1"], "scope_source": "token_hard_scope"},
        {"buyer_ids": None, "scope_source": "sudo_unscoped_token"},
        {"buyer_ids": ["buyer-1"], "scope_source": "seat_grants"},
    ]
    assert [call["resource_id"] for call in auth.audit_calls] == [
        "buyer-1",
        "all-granted",
        "all-granted",
    ]
