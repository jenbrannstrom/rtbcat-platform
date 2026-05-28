from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.agent_token_service import (
    AGENT_STATS_READ_SCOPE,
    AGENT_TOKEN_PREFIX,
    AgentTokenService,
    hash_agent_token,
)
from services.auth_service import User


class _FakeAuthService:
    def __init__(self, user: User | None = None) -> None:
        self.user = user or User(
            id="agent-user",
            email="agent@example.com",
            display_name="Agent",
            role="read",
            is_active=True,
        )

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self.user if self.user and self.user.id == user_id else None


class _FakeAgentTokenRepo:
    def __init__(self) -> None:
        self.rows_by_id: dict[str, dict] = {}
        self.rows_by_hash: dict[str, dict] = {}
        self.last_used: list[dict] = []

    async def create_token(self, **kwargs):
        row = {
            "id": kwargs["token_id"],
            "name": kwargs["name"],
            "token_hash": kwargs["token_hash"],
            "token_prefix": kwargs["token_prefix"],
            "user_id": kwargs["user_id"],
            "buyer_id": kwargs["buyer_id"],
            "scopes": kwargs["scopes"],
            "is_active": True,
            "expires_at": kwargs["expires_at"],
            "created_at": datetime.now(UTC).isoformat(),
            "created_by": kwargs["created_by"],
            "revoked_at": None,
            "user_email": "agent@example.com",
            "user_display_name": "Agent",
            "user_role": "read",
            "user_is_active": True,
        }
        self.rows_by_id[row["id"]] = row
        self.rows_by_hash[row["token_hash"]] = row
        return row

    async def get_token_by_id(self, token_id: str):
        return self.rows_by_id.get(token_id)

    async def get_token_by_hash(self, token_hash: str):
        return self.rows_by_hash.get(token_hash)

    async def mark_token_used(self, **kwargs) -> None:
        self.last_used.append(kwargs)


@pytest.mark.asyncio
async def test_create_token_returns_plaintext_once_and_stores_hash() -> None:
    repo = _FakeAgentTokenRepo()
    service = AgentTokenService(repo=repo, auth_service=_FakeAuthService())

    created = await service.create_token(
        name="Daily report",
        user_id="agent-user",
        buyer_id="buyer-1",
        scopes=[AGENT_STATS_READ_SCOPE],
        expires_in_days=30,
        created_by="admin-user",
    )

    assert created.token.startswith(AGENT_TOKEN_PREFIX)
    assert created.record.buyer_id == "buyer-1"
    assert created.record.scopes == [AGENT_STATS_READ_SCOPE]
    stored_row = repo.rows_by_id[created.record.id]
    assert stored_row["token_hash"] == hash_agent_token(created.token)
    assert created.token not in stored_row.values()


@pytest.mark.asyncio
async def test_authenticate_token_returns_user_context_and_marks_used() -> None:
    repo = _FakeAgentTokenRepo()
    service = AgentTokenService(repo=repo, auth_service=_FakeAuthService())
    created = await service.create_token(
        name="Daily report",
        user_id="agent-user",
        buyer_id="buyer-1",
        scopes=[AGENT_STATS_READ_SCOPE],
        expires_in_days=30,
        created_by="admin-user",
    )

    context = await service.authenticate_token(
        created.token,
        required_scope=AGENT_STATS_READ_SCOPE,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert context is not None
    assert context.user.email == "agent@example.com"
    assert context.token.id == created.record.id
    assert repo.last_used == [
        {
            "token_id": created.record.id,
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
        }
    ]


@pytest.mark.asyncio
async def test_authenticate_request_accepts_agent_token_header() -> None:
    repo = _FakeAgentTokenRepo()
    service = AgentTokenService(repo=repo, auth_service=_FakeAuthService())
    created = await service.create_token(
        name="Daily report",
        user_id="agent-user",
        buyer_id="buyer-1",
        scopes=[AGENT_STATS_READ_SCOPE],
        expires_in_days=30,
        created_by="admin-user",
    )

    request = SimpleNamespace(
        headers={
            "X-CatScan-Agent-Token": created.token,
            "User-Agent": "pytest",
        },
        client=SimpleNamespace(host="127.0.0.1"),
    )

    context = await service.authenticate_request(
        request,
        required_scope=AGENT_STATS_READ_SCOPE,
    )

    assert context is not None
    assert context.token.id == created.record.id


@pytest.mark.asyncio
async def test_authenticate_token_rejects_expired_token() -> None:
    repo = _FakeAgentTokenRepo()
    service = AgentTokenService(repo=repo, auth_service=_FakeAuthService())
    created = await service.create_token(
        name="Daily report",
        user_id="agent-user",
        buyer_id="buyer-1",
        scopes=[AGENT_STATS_READ_SCOPE],
        expires_in_days=1,
        created_by="admin-user",
    )
    repo.rows_by_id[created.record.id]["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(HTTPException) as exc:
        await service.authenticate_token(created.token, required_scope=AGENT_STATS_READ_SCOPE)

    assert exc.value.status_code == 401
    assert "expired" in str(exc.value.detail)
