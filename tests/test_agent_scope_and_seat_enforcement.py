"""Phase 1 authorization regression tests.

Covers the read-only MCP prerequisite fixes (docs/MCP_READONLY_SERVER_PLAN.md):
per-route agent scopes, multi-seat widening in get_allowed_buyer_ids, the
sanctioned all-granted-buyers token shape, and the buyer check on the
thumbnail byte route.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException

import api.dependencies as deps
from api.routers import agent as agent_router
from api.routers import system as system_router
from services.agent_token_service import (
    AGENT_ASSETS_READ_SCOPE,
    AGENT_CREATIVE_PERFORMANCE_READ_SCOPE,
    AGENT_CREATIVES_READ_SCOPE,
    AGENT_STATS_READ_SCOPE,
    AGENT_TOKEN_SCOPES,
    AgentAuthContext,
    AgentTokenRecord,
)
from services.auth_service import User
from tests.support.asgi_client import SyncASGIClient


def _context(scopes: list[str], token_buyer_id: str | None = "buyer-1") -> AgentAuthContext:
    return AgentAuthContext(
        user=User(id="agent-user", email="agent@example.com", role="read"),
        token=AgentTokenRecord(
            id="token-1",
            name="Research token",
            token_prefix="cat_agent_testprefix",
            user_id="agent-user",
            buyer_id=token_buyer_id,
            scopes=scopes,
            expires_at="2026-12-31T00:00:00+00:00",
            is_active=True,
        ),
    )


def _request_with_context(context: AgentAuthContext) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(agent_auth_context=context))


class _StubAuthService:
    def __init__(self, buyer_ids: list[str]) -> None:
        self.buyer_ids = buyer_ids
        self.audit_calls: list[dict] = []

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
                buyer_id=kwargs["buyer_id"] if kwargs.get("buyer_ids") is None else None,
                buyer_ids=kwargs.get("buyer_ids"),
                scopes=kwargs["scopes"],
                expires_at="2026-12-31T00:00:00+00:00",
                is_active=True,
                user_email="agent@example.com",
            ),
        )


# ---------------------------------------------------------------------------
# require_agent_scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scope_dependency_rejects_token_missing_required_scope() -> None:
    dependency = agent_router.require_agent_scope(AGENT_CREATIVES_READ_SCOPE)
    request = _request_with_context(_context(scopes=[AGENT_STATS_READ_SCOPE]))
    with pytest.raises(HTTPException) as exc:
        await dependency(request)
    assert exc.value.status_code == 403
    assert AGENT_CREATIVES_READ_SCOPE in exc.value.detail


@pytest.mark.asyncio
async def test_scope_dependency_accepts_token_with_required_scope() -> None:
    dependency = agent_router.require_agent_scope(AGENT_CREATIVES_READ_SCOPE)
    context = _context(scopes=[AGENT_STATS_READ_SCOPE, AGENT_CREATIVES_READ_SCOPE])
    assert await dependency(_request_with_context(context)) is context


@pytest.mark.asyncio
async def test_identity_dependency_accepts_any_valid_token() -> None:
    context = _context(scopes=[AGENT_ASSETS_READ_SCOPE])
    assert await agent_router.require_agent_identity(_request_with_context(context)) is context


def test_stats_dependency_object_is_preserved_for_existing_routes() -> None:
    # Route wiring and test overrides key on this module-level object.
    assert callable(agent_router.require_agent_context)


# ---------------------------------------------------------------------------
# get_allowed_buyer_ids / resolve_buyer_id multi-seat widening
# ---------------------------------------------------------------------------


def _reader() -> User:
    return User(id="multi-seat-user", email="reader@example.com", role="read")


@pytest.mark.asyncio
async def test_multi_seat_user_sees_all_granted_buyers(monkeypatch) -> None:
    monkeypatch.setattr(
        deps, "get_auth_service", lambda: _StubAuthService(["buyer-1", "buyer-2", "buyer-1"])
    )
    allowed = await deps.get_allowed_buyer_ids(store=SimpleNamespace(), user=_reader())
    assert allowed == ["buyer-1", "buyer-2"]


@pytest.mark.asyncio
async def test_resolve_buyer_id_requires_explicit_buyer_for_multi_seat_user(monkeypatch) -> None:
    monkeypatch.setattr(
        deps, "get_auth_service", lambda: _StubAuthService(["buyer-1", "buyer-2"])
    )
    with pytest.raises(HTTPException) as exc:
        await deps.resolve_buyer_id(None, store=SimpleNamespace(), user=_reader())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_resolve_buyer_id_accepts_any_granted_seat(monkeypatch) -> None:
    monkeypatch.setattr(
        deps, "get_auth_service", lambda: _StubAuthService(["buyer-1", "buyer-2"])
    )
    resolved = await deps.resolve_buyer_id("buyer-2", store=SimpleNamespace(), user=_reader())
    assert resolved == "buyer-2"


@pytest.mark.asyncio
async def test_resolve_buyer_id_rejects_ungranted_seat(monkeypatch) -> None:
    monkeypatch.setattr(
        deps, "get_auth_service", lambda: _StubAuthService(["buyer-1", "buyer-2"])
    )
    with pytest.raises(HTTPException) as exc:
        await deps.resolve_buyer_id("buyer-3", store=SimpleNamespace(), user=_reader())
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Token creation: new scopes and all_granted_buyers
# ---------------------------------------------------------------------------


class _StubSeatsRepo:
    def __init__(self, active_buyer_ids: list[str] | None = None) -> None:
        self.active_buyer_ids = active_buyer_ids
        self.calls: list[dict] = []

    async def get_buyer_seats_by_ids(self, buyer_ids, bidder_id=None, active_only=True):
        self.calls.append({"buyer_ids": list(buyer_ids), "active_only": active_only})
        active = buyer_ids if self.active_buyer_ids is None else self.active_buyer_ids
        return [{"buyer_id": buyer_id} for buyer_id in buyer_ids if buyer_id in active]


def _token_admin_client(
    auth: _StubAuthService,
    token_service: _StubTokenService,
    seats_repo: _StubSeatsRepo | None = None,
) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[agent_router.require_token_admin] = lambda: User(
        id="admin-1", email="admin@example.com", role="sudo"
    )
    app.dependency_overrides[agent_router.get_auth_service] = lambda: auth
    app.dependency_overrides[agent_router.get_agent_token_service] = lambda: token_service
    app.dependency_overrides[agent_router.get_seats_repo] = lambda: seats_repo or _StubSeatsRepo()
    return SyncASGIClient(app)


def test_create_token_accepts_all_new_read_scopes() -> None:
    auth = _StubAuthService(["buyer-1"])
    token_service = _StubTokenService()
    client = _token_admin_client(auth, token_service)

    scopes = sorted(AGENT_TOKEN_SCOPES)
    response = client.post(
        "/api/agent/v1/tokens",
        json={"name": "Research token", "user_id": "agent-user", "scopes": scopes},
    )
    assert response.status_code == 200
    assert sorted(token_service.create_calls[0]["scopes"]) == scopes


def test_create_token_still_rejects_unknown_scope() -> None:
    auth = _StubAuthService(["buyer-1"])
    client = _token_admin_client(auth, _StubTokenService())

    response = client.post(
        "/api/agent/v1/tokens",
        json={
            "name": "Bad token",
            "user_id": "agent-user",
            "scopes": ["agent:creatives:write"],
        },
    )
    assert response.status_code == 400


def test_all_granted_buyers_mints_unscoped_token_for_multi_seat_user() -> None:
    auth = _StubAuthService(["buyer-1", "buyer-2"])
    token_service = _StubTokenService()
    client = _token_admin_client(auth, token_service)

    response = client.post(
        "/api/agent/v1/tokens",
        json={
            "name": "Research token",
            "user_id": "agent-user",
            "all_granted_buyers": True,
            "scopes": [AGENT_STATS_READ_SCOPE, AGENT_CREATIVE_PERFORMANCE_READ_SCOPE],
        },
    )
    assert response.status_code == 200
    assert token_service.create_calls[0]["buyer_id"] is None


def test_all_granted_buyers_conflicts_with_explicit_buyer_id() -> None:
    auth = _StubAuthService(["buyer-1", "buyer-2"])
    client = _token_admin_client(auth, _StubTokenService())

    response = client.post(
        "/api/agent/v1/tokens",
        json={
            "name": "Research token",
            "user_id": "agent-user",
            "buyer_id": "buyer-1",
            "all_granted_buyers": True,
        },
    )
    assert response.status_code == 400


def test_all_granted_buyers_rejected_for_sudo_target() -> None:
    class _SudoAuthService(_StubAuthService):
        async def get_user_by_id(self, user_id: str):
            return User(id=user_id, email="sudo@example.com", role="sudo", is_active=True)

    client = _token_admin_client(_SudoAuthService(["buyer-1"]), _StubTokenService())

    response = client.post(
        "/api/agent/v1/tokens",
        json={"name": "Sudo token", "user_id": "sudo-user", "all_granted_buyers": True},
    )
    assert response.status_code == 400


def test_all_granted_buyers_requires_at_least_one_grant() -> None:
    auth = _StubAuthService([])
    client = _token_admin_client(auth, _StubTokenService())

    response = client.post(
        "/api/agent/v1/tokens",
        json={"name": "Research token", "user_id": "agent-user", "all_granted_buyers": True},
    )
    assert response.status_code == 400


def test_multi_seat_user_without_buyer_id_still_requires_choice() -> None:
    auth = _StubAuthService(["buyer-1", "buyer-2"])
    client = _token_admin_client(auth, _StubTokenService())

    response = client.post(
        "/api/agent/v1/tokens",
        json={"name": "Research token", "user_id": "agent-user"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Token creation: explicit buyer list (buyer_ids)
# ---------------------------------------------------------------------------

FINANCE_BUYER_IDS = ["1487810529", "6574658621", "6634662463", "7942355670", "8087233591"]


class _SudoAuthService(_StubAuthService):
    async def get_user_by_id(self, user_id: str):
        return User(id=user_id, email="sudo@example.com", role="sudo", is_active=True)


def _mint(client: SyncASGIClient, **body):
    return client.post(
        "/api/agent/v1/tokens",
        json={"name": "Finance spend", "user_id": "target-user", **body},
    )


def test_sudo_user_can_mint_token_for_explicit_buyer_list() -> None:
    auth = _SudoAuthService([])
    token_service = _StubTokenService()
    seats_repo = _StubSeatsRepo()
    client = _token_admin_client(auth, token_service, seats_repo)

    response = _mint(client, buyer_ids=FINANCE_BUYER_IDS, scopes=[AGENT_STATS_READ_SCOPE])

    assert response.status_code == 200
    assert token_service.create_calls[0]["buyer_ids"] == FINANCE_BUYER_IDS
    assert token_service.create_calls[0]["buyer_id"] is None
    assert token_service.create_calls[0]["scopes"] == [AGENT_STATS_READ_SCOPE]
    record = response.json()["token_record"]
    assert record["buyer_ids"] == FINANCE_BUYER_IDS
    assert record["buyer_id"] is None
    assert seats_repo.calls == [{"buyer_ids": FINANCE_BUYER_IDS, "active_only": True}]
    audit = auth.audit_calls[0]
    assert audit["action"] == "agent_token_create"
    assert f"buyer_ids={','.join(FINANCE_BUYER_IDS)}" in audit["details"]


def test_sudo_user_without_any_buyer_scope_is_still_rejected() -> None:
    token_service = _StubTokenService()
    client = _token_admin_client(_SudoAuthService([]), token_service)

    response = _mint(client)

    assert response.status_code == 400
    assert token_service.create_calls == []


def test_sudo_user_with_all_granted_buyers_is_still_rejected() -> None:
    token_service = _StubTokenService()
    client = _token_admin_client(_SudoAuthService(FINANCE_BUYER_IDS), token_service)

    response = _mint(client, all_granted_buyers=True)

    assert response.status_code == 400
    assert "all_granted_buyers is not allowed for sudo users" in response.json()["detail"]
    assert token_service.create_calls == []


def test_non_sudo_user_can_mint_buyer_list_within_grants() -> None:
    auth = _StubAuthService(["buyer-1", "buyer-2", "buyer-3"])
    token_service = _StubTokenService()
    client = _token_admin_client(auth, token_service)

    response = _mint(client, buyer_ids=["buyer-1", "buyer-3"])

    assert response.status_code == 200
    assert token_service.create_calls[0]["buyer_ids"] == ["buyer-1", "buyer-3"]


def test_non_sudo_user_buyer_list_outside_grants_is_rejected() -> None:
    token_service = _StubTokenService()
    client = _token_admin_client(_StubAuthService(["buyer-1", "buyer-2"]), token_service)

    response = _mint(client, buyer_ids=["buyer-1", "buyer-9"])

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Agent user does not have read access to every requested buyer."
    )
    assert token_service.create_calls == []


@pytest.mark.parametrize(
    "body",
    [
        {"buyer_ids": ["buyer-1"], "buyer_id": "buyer-1"},
        {"buyer_ids": ["buyer-1"], "all_granted_buyers": True},
        {"buyer_ids": []},
        {"buyer_ids": ["buyer-1", "buyer-1"]},
        {"buyer_ids": ["buyer-1", ""]},
        {"buyer_ids": ["buyer-1", " buyer-2"]},
        {"buyer_ids": [f"buyer-{index}" for index in range(51)]},
    ],
    ids=[
        "with-buyer-id",
        "with-all-granted",
        "empty-list",
        "duplicate",
        "empty-string",
        "whitespace-padded",
        "over-50",
    ],
)
def test_malformed_buyer_list_is_rejected_for_sudo_and_non_sudo(body: dict) -> None:
    granted = [f"buyer-{index}" for index in range(51)]
    for auth in (_SudoAuthService(granted), _StubAuthService(granted)):
        token_service = _StubTokenService()
        client = _token_admin_client(auth, token_service)

        response = _mint(client, **body)

        assert response.status_code == 400
        assert token_service.create_calls == []


def test_buyer_list_accepts_fifty_buyers() -> None:
    buyer_ids = [f"buyer-{index}" for index in range(50)]
    token_service = _StubTokenService()
    client = _token_admin_client(_SudoAuthService([]), token_service)

    assert _mint(client, buyer_ids=buyer_ids).status_code == 200
    assert token_service.create_calls[0]["buyer_ids"] == buyer_ids


def test_buyer_list_with_unknown_or_inactive_seat_is_rejected() -> None:
    token_service = _StubTokenService()
    seats_repo = _StubSeatsRepo(active_buyer_ids=FINANCE_BUYER_IDS[:4])
    client = _token_admin_client(_SudoAuthService([]), token_service, seats_repo)

    response = _mint(client, buyer_ids=FINANCE_BUYER_IDS)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Every buyer in buyer_ids must be an existing, active buyer seat."
    )
    assert token_service.create_calls == []


def test_sudo_single_buyer_mint_is_unchanged() -> None:
    token_service = _StubTokenService()
    client = _token_admin_client(_SudoAuthService([]), token_service)

    response = _mint(client, buyer_id="buyer-1")

    assert response.status_code == 200
    assert token_service.create_calls[0]["buyer_id"] == "buyer-1"
    assert token_service.create_calls[0]["buyer_ids"] is None
    assert response.json()["token_record"]["buyer_id"] == "buyer-1"
    assert response.json()["token_record"]["buyer_ids"] is None


def test_enforce_token_buyer_covers_single_list_and_unscoped_tokens() -> None:
    single = _context([AGENT_STATS_READ_SCOPE], token_buyer_id="buyer-1")
    agent_router._enforce_token_buyer(single, "buyer-1")
    with pytest.raises(HTTPException) as exc:
        agent_router._enforce_token_buyer(single, "buyer-2")
    assert exc.value.status_code == 403

    listed = _context([AGENT_STATS_READ_SCOPE], token_buyer_id=None)
    listed.token.buyer_ids = ["buyer-1", "buyer-2"]
    agent_router._enforce_token_buyer(listed, "buyer-2")
    with pytest.raises(HTTPException) as exc:
        agent_router._enforce_token_buyer(listed, "buyer-3")
    assert exc.value.status_code == 403
    assert exc.value.detail == "Agent token is not scoped to this buyer."

    unscoped = _context([AGENT_STATS_READ_SCOPE], token_buyer_id=None)
    agent_router._enforce_token_buyer(unscoped, "buyer-3")


# ---------------------------------------------------------------------------
# Thumbnail route buyer authorization
# ---------------------------------------------------------------------------


def _thumbnail_client(creative, user: User, monkeypatch, seat_ids: list[str]) -> SyncASGIClient:
    monkeypatch.setattr(deps, "get_auth_service", lambda: _StubAuthService(seat_ids))

    async def _get_creative(_creative_id: str):
        return creative

    store = SimpleNamespace(get_creative=_get_creative)
    app = FastAPI()
    app.include_router(system_router.router)
    app.dependency_overrides[system_router.get_store] = lambda: store
    app.dependency_overrides[system_router.get_current_user] = lambda: user
    return SyncASGIClient(app)


def test_thumbnail_denied_for_unassigned_buyer(monkeypatch) -> None:
    creative = SimpleNamespace(buyer_id="buyer-2")
    client = _thumbnail_client(creative, _reader(), monkeypatch, seat_ids=["buyer-1"])
    response = client.get("/thumbnails/creative-1.jpg")
    assert response.status_code == 403


def test_thumbnail_missing_creative_is_not_found(monkeypatch) -> None:
    client = _thumbnail_client(None, _reader(), monkeypatch, seat_ids=["buyer-1"])
    response = client.get("/thumbnails/creative-1.jpg")
    assert response.status_code == 404


def test_thumbnail_allowed_buyer_reaches_file_lookup(monkeypatch) -> None:
    creative = SimpleNamespace(buyer_id="buyer-1")
    client = _thumbnail_client(creative, _reader(), monkeypatch, seat_ids=["buyer-1"])
    # Unique ID so no real file under ~/.catscan/thumbnails can ever match.
    response = client.get("/thumbnails/test-no-such-creative-2b7c1f.jpg")
    # Authorization passed; only the (absent) file stops the response.
    assert response.status_code == 404
    assert response.json()["detail"] == "Thumbnail not found"


def test_thumbnail_null_buyer_creative_denied_for_non_sudo(monkeypatch) -> None:
    creative = SimpleNamespace(buyer_id=None)
    client = _thumbnail_client(creative, _reader(), monkeypatch, seat_ids=["buyer-1"])
    response = client.get("/thumbnails/creative-1.jpg")
    assert response.status_code == 403
