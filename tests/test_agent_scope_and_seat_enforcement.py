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
                buyer_id=kwargs["buyer_id"],
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


def _token_admin_client(
    auth: _StubAuthService, token_service: _StubTokenService
) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[agent_router.require_token_admin] = lambda: User(
        id="admin-1", email="admin@example.com", role="sudo"
    )
    app.dependency_overrides[agent_router.get_auth_service] = lambda: auth
    app.dependency_overrides[agent_router.get_agent_token_service] = lambda: token_service
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
