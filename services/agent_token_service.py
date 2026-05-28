"""Hashed bearer-token authentication for outside agent API clients."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable

from fastapi import HTTPException, Request

from services.auth_service import AuthService, User
from storage.postgres_repositories.agent_tokens_repo import AgentTokensRepository

AGENT_TOKEN_PREFIX = "cat_agent_"
AGENT_STATS_READ_SCOPE = "agent:stats:read"
AGENT_TOKEN_HEADER = "X-CatScan-Agent-Token"


@dataclass
class AgentTokenRecord:
    """Metadata for an agent token. Plaintext tokens are never stored here."""

    id: str
    name: str
    token_prefix: str
    user_id: str
    scopes: list[str]
    expires_at: str
    is_active: bool
    buyer_id: str | None = None
    user_email: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    revoked_at: str | None = None
    last_used_at: str | None = None


@dataclass
class AgentAuthContext:
    """Authenticated agent-token context attached to requests."""

    user: User
    token: AgentTokenRecord


@dataclass
class CreatedAgentToken:
    """Creation response, including the plaintext token shown once."""

    token: str
    record: AgentTokenRecord


def hash_agent_token(token: str) -> str:
    """Hash a high-entropy agent token for storage and lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_agent_token() -> str:
    """Generate a new high-entropy bearer token for outside agents."""
    return f"{AGENT_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def token_prefix(token: str) -> str:
    """Return a non-secret prefix for identifying tokens in logs/UI."""
    return token[:22]


def parse_scopes(value: str | Iterable[str] | None) -> list[str]:
    """Normalize token scopes from comma-separated text or an iterable."""
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.split(",")
    else:
        raw = [str(item) for item in value]
    scopes: list[str] = []
    seen: set[str] = set()
    for item in raw:
        scope = item.strip()
        if not scope or scope in seen:
            continue
        scopes.append(scope)
        seen.add(scope)
    return scopes


def serialize_scopes(scopes: Iterable[str]) -> str:
    """Serialize normalized scopes for database storage."""
    normalized = parse_scopes(scopes)
    if not normalized:
        normalized = [AGENT_STATS_READ_SCOPE]
    return ",".join(normalized)


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _is_active_db_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _user_from_token_row(row: dict) -> User:
    return User(
        id=str(row["user_id"]),
        email=str(row.get("user_email") or ""),
        display_name=row.get("user_display_name"),
        role=str(row.get("user_role") or "read"),
        is_active=_is_active_db_value(row.get("user_is_active", True)),
    )


def _record_from_row(row: dict) -> AgentTokenRecord:
    return AgentTokenRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        token_prefix=str(row["token_prefix"]),
        user_id=str(row["user_id"]),
        buyer_id=row.get("buyer_id"),
        scopes=parse_scopes(row.get("scopes")),
        is_active=_is_active_db_value(row.get("is_active")),
        expires_at=str(row.get("expires_at")),
        user_email=row.get("user_email"),
        created_at=str(row.get("created_at")) if row.get("created_at") else None,
        created_by=row.get("created_by"),
        revoked_at=str(row.get("revoked_at")) if row.get("revoked_at") else None,
        last_used_at=str(row.get("last_used_at")) if row.get("last_used_at") else None,
    )


class AgentTokenService:
    """Create, authenticate, list, and revoke outside-agent tokens."""

    def __init__(
        self,
        repo: AgentTokensRepository | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self._repo = repo or AgentTokensRepository()
        self._auth = auth_service or AuthService()

    async def create_token(
        self,
        *,
        name: str,
        user_id: str,
        created_by: str | None,
        buyer_id: str | None = None,
        scopes: Iterable[str] | None = None,
        expires_in_days: int = 90,
    ) -> CreatedAgentToken:
        user = await self._auth.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Agent user not found.")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Agent user is inactive.")

        safe_days = max(1, min(int(expires_in_days), 366))
        expires_at = datetime.now(UTC) + timedelta(days=safe_days)
        plaintext = generate_agent_token()
        record_row = await self._repo.create_token(
            token_id=str(uuid.uuid4()),
            name=name.strip(),
            token_hash=hash_agent_token(plaintext),
            token_prefix=token_prefix(plaintext),
            user_id=user_id,
            buyer_id=buyer_id,
            scopes=serialize_scopes(scopes or [AGENT_STATS_READ_SCOPE]),
            expires_at=expires_at.isoformat(),
            created_by=created_by,
        )
        return CreatedAgentToken(token=plaintext, record=_record_from_row(record_row))

    async def authenticate_token(
        self,
        token: str,
        *,
        required_scope: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AgentAuthContext | None:
        if not token or not token.startswith(AGENT_TOKEN_PREFIX):
            return None

        row = await self._repo.get_token_by_hash(hash_agent_token(token))
        if not row:
            raise HTTPException(status_code=401, detail="Invalid agent token.")

        record = _record_from_row(row)
        if not record.is_active or record.revoked_at:
            raise HTTPException(status_code=401, detail="Agent token is revoked.")

        expires_at = _parse_datetime(row.get("expires_at"))
        if expires_at is None or expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=401, detail="Agent token is expired.")

        user = _user_from_token_row(row)
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Agent user is inactive.")

        if required_scope and required_scope not in record.scopes:
            raise HTTPException(status_code=403, detail="Agent token lacks required scope.")

        await self._repo.mark_token_used(
            token_id=record.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return AgentAuthContext(user=user, token=record)

    async def authenticate_request(
        self,
        request: Request,
        *,
        required_scope: str | None = None,
    ) -> AgentAuthContext | None:
        token_header = request.headers.get(AGENT_TOKEN_HEADER, "").strip()
        if token_header:
            return await self.authenticate_token(
                token_header,
                required_scope=required_scope,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
            )

        header = request.headers.get("Authorization", "")
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return await self.authenticate_token(
            parts[1],
            required_scope=required_scope,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )

    async def list_tokens(
        self,
        *,
        user_id: str | None = None,
        buyer_id: str | None = None,
        active_only: bool = False,
        limit: int = 100,
    ) -> list[AgentTokenRecord]:
        rows = await self._repo.list_tokens(
            user_id=user_id,
            buyer_id=buyer_id,
            active_only=active_only,
            limit=limit,
        )
        return [_record_from_row(row) for row in rows]

    async def revoke_token(self, *, token_id: str, revoked_by: str | None) -> bool:
        return await self._repo.revoke_token(token_id=token_id, revoked_by=revoked_by)
