"""Versioned API for outside reporting agents."""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.dependencies import get_store, require_admin, resolve_buyer_id
from services.agent_stats_service import AgentStatsService
from services.agent_token_service import (
    AGENT_STATS_READ_SCOPE,
    AgentAuthContext,
    AgentTokenRecord,
    AgentTokenService,
)
from services.auth_service import AuthService, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/v1", tags=["Agent API"])


class AgentTokenCreateRequest(BaseModel):
    """Request to mint an outside-agent bearer token."""

    name: str = Field(..., min_length=3, max_length=120)
    user_id: str = Field(..., min_length=1)
    buyer_id: str | None = Field(
        None,
        description="Optional buyer hard-scope for this token.",
    )
    scopes: list[str] = Field(default_factory=lambda: [AGENT_STATS_READ_SCOPE])
    expires_in_days: int = Field(90, ge=1, le=366)


class AgentTokenResponse(BaseModel):
    """Safe token metadata. Does not include token_hash."""

    id: str
    name: str
    token_prefix: str
    user_id: str
    buyer_id: str | None = None
    scopes: list[str]
    expires_at: str
    is_active: bool
    user_email: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    revoked_at: str | None = None
    last_used_at: str | None = None


class AgentTokenCreateResponse(BaseModel):
    """Token creation response. The plaintext token is returned once."""

    token: str
    token_type: str = "Bearer"
    token_record: AgentTokenResponse


class AgentTokenListResponse(BaseModel):
    """List response for agent token metadata."""

    tokens: list[AgentTokenResponse]


class AgentMeResponse(BaseModel):
    """Identity payload for validating agent auth wiring."""

    authenticated: bool
    user_id: str
    email: str
    role: str
    token_id: str
    token_name: str
    buyer_id: str | None
    scopes: list[str]


def get_agent_token_service() -> AgentTokenService:
    return AgentTokenService()


def get_agent_stats_service() -> AgentStatsService:
    return AgentStatsService()


def get_auth_service() -> AuthService:
    return AuthService()


def _token_response(record: AgentTokenRecord) -> AgentTokenResponse:
    return AgentTokenResponse(
        id=record.id,
        name=record.name,
        token_prefix=record.token_prefix,
        user_id=record.user_id,
        buyer_id=record.buyer_id,
        scopes=record.scopes,
        expires_at=record.expires_at,
        is_active=record.is_active,
        user_email=record.user_email,
        created_at=record.created_at,
        created_by=record.created_by,
        revoked_at=record.revoked_at,
        last_used_at=record.last_used_at,
    )


async def require_agent_context(request: Request) -> AgentAuthContext:
    context = getattr(request.state, "agent_auth_context", None)
    if not context:
        context = await AgentTokenService().authenticate_request(
            request,
            required_scope=AGENT_STATS_READ_SCOPE,
        )
        if context:
            request.state.user = context.user
            request.state.agent_auth_context = context
            request.state.agent_token_authenticated = True
        else:
            raise HTTPException(
                status_code=401,
                detail="Agent bearer token required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    if AGENT_STATS_READ_SCOPE not in context.token.scopes:
        raise HTTPException(status_code=403, detail="Agent token lacks stats read scope.")
    return context


async def require_token_admin(request: Request, user: User = Depends(require_admin)) -> User:
    if getattr(request.state, "agent_token_authenticated", False):
        raise HTTPException(
            status_code=403,
            detail="Agent tokens cannot manage agent tokens.",
        )
    if getattr(request.state, "api_key_authenticated", False):
        raise HTTPException(
            status_code=403,
            detail="Global API-key automation cannot manage agent tokens. Use a sudo user session.",
        )
    return user


async def _validate_token_target(
    *,
    payload: AgentTokenCreateRequest,
    auth_service: AuthService,
) -> str:
    target_user = await auth_service.get_user_by_id(payload.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Agent user not found.")
    if not target_user.is_active:
        raise HTTPException(status_code=400, detail="Agent user is inactive.")

    if target_user.role == "sudo":
        if not payload.buyer_id:
            raise HTTPException(
                status_code=400,
                detail="buyer_id is required when creating an agent token for a sudo user.",
            )
        return payload.buyer_id

    buyer_ids = await auth_service.get_user_buyer_seat_ids(target_user.id)
    if payload.buyer_id:
        if payload.buyer_id not in buyer_ids:
            raise HTTPException(
                status_code=400,
                detail="Agent user does not have read access to the requested buyer.",
            )
        return payload.buyer_id

    if len(buyer_ids) == 1:
        return buyer_ids[0]

    if not buyer_ids:
        raise HTTPException(
            status_code=400,
            detail="Agent user has no buyer read grants.",
        )
    raise HTTPException(
        status_code=400,
        detail="buyer_id is required when agent user has multiple buyer grants.",
    )


async def _audit_agent_read(
    *,
    request: Request,
    context: AgentAuthContext,
    buyer_id: str,
    days: int,
    top_limit: int,
    auth_service: AuthService,
) -> None:
    await auth_service.log_audit(
        audit_id=str(uuid.uuid4()),
        action="agent_stats_summary_read",
        user_id=context.user.id,
        resource_type="agent_api",
        resource_id=buyer_id,
        details=(
            f"token_id={context.token.id}; buyer_id={buyer_id}; "
            f"days={days}; top_limit={top_limit}"
        ),
        ip_address=request.client.host if request.client else None,
    )


@router.get("/me", response_model=AgentMeResponse)
async def agent_me(context: AgentAuthContext = Depends(require_agent_context)) -> AgentMeResponse:
    """Validate an outside-agent bearer token and report its effective identity."""
    return AgentMeResponse(
        authenticated=True,
        user_id=context.user.id,
        email=context.user.email,
        role=context.user.role,
        token_id=context.token.id,
        token_name=context.token.name,
        buyer_id=context.token.buyer_id,
        scopes=context.token.scopes,
    )


@router.get("/stats-summary")
async def get_agent_stats_summary(
    request: Request,
    buyer_id: str | None = Query(None, description="Buyer seat ID. Optional for one-buyer agent users."),
    days: int = Query(7, ge=1, le=30),
    top_limit: int = Query(10, ge=1, le=25),
    store=Depends(get_store),
    context: AgentAuthContext = Depends(require_agent_context),
    stats_service: AgentStatsService = Depends(get_agent_stats_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Return precomputed stats shaped for an external email-summary agent."""
    resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=context.user)
    if not resolved_buyer_id:
        raise HTTPException(status_code=400, detail="buyer_id is required.")
    if context.token.buyer_id and context.token.buyer_id != resolved_buyer_id:
        raise HTTPException(
            status_code=403,
            detail="Agent token is not scoped to this buyer.",
        )

    payload = await stats_service.get_stats_summary(
        buyer_id=resolved_buyer_id,
        days=days,
        top_limit=top_limit,
    )
    await _audit_agent_read(
        request=request,
        context=context,
        buyer_id=resolved_buyer_id,
        days=days,
        top_limit=top_limit,
        auth_service=auth_service,
    )
    return payload


@router.get("/daily-spend")
async def get_agent_daily_spend(
    request: Request,
    start_date: date = Query(..., description="Inclusive start metric date (YYYY-MM-DD)."),
    end_date: date = Query(..., description="Inclusive end metric date (YYYY-MM-DD). Must be >= start_date."),
    buyer_id: str | None = Query(None, description="Buyer seat ID. Optional for one-buyer agent users."),
    include_empty: bool = Query(True, description="Return a row for every requested date, even without source rows."),
    store=Depends(get_store),
    context: AgentAuthContext = Depends(require_agent_context),
    stats_service: AgentStatsService = Depends(get_agent_stats_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Return date-explicit, buyer-scoped daily spend rows from precomputed data."""
    resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=context.user)
    if not resolved_buyer_id:
        raise HTTPException(status_code=400, detail="buyer_id is required.")
    if context.token.buyer_id and context.token.buyer_id != resolved_buyer_id:
        raise HTTPException(
            status_code=403,
            detail="Agent token is not scoped to this buyer.",
        )

    payload = await stats_service.get_daily_spend(
        buyer_id=resolved_buyer_id,
        start_date=start_date,
        end_date=end_date,
        include_empty=include_empty,
    )
    await auth_service.log_audit(
        audit_id=str(uuid.uuid4()),
        action="agent_daily_spend_read",
        user_id=context.user.id,
        resource_type="agent_api",
        resource_id=resolved_buyer_id,
        details=(
            f"token_id={context.token.id}; buyer_id={resolved_buyer_id}; "
            f"start_date={start_date.isoformat()}; end_date={end_date.isoformat()}; "
            f"include_empty={include_empty}"
        ),
        ip_address=request.client.host if request.client else None,
    )
    return payload


@router.post("/tokens", response_model=AgentTokenCreateResponse)
async def create_agent_token(
    payload: AgentTokenCreateRequest,
    admin_user: User = Depends(require_token_admin),
    token_service: AgentTokenService = Depends(get_agent_token_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> AgentTokenCreateResponse:
    """Create a revocable bearer token for a buyer-scoped agent user."""
    allowed_scopes = {AGENT_STATS_READ_SCOPE}
    requested_scopes = set(payload.scopes or [AGENT_STATS_READ_SCOPE])
    if not requested_scopes.issubset(allowed_scopes):
        raise HTTPException(status_code=400, detail="Unsupported agent token scope.")

    token_buyer_id = await _validate_token_target(payload=payload, auth_service=auth_service)
    created = await token_service.create_token(
        name=payload.name,
        user_id=payload.user_id,
        buyer_id=token_buyer_id,
        scopes=payload.scopes,
        expires_in_days=payload.expires_in_days,
        created_by=admin_user.id,
    )
    await auth_service.log_audit(
        audit_id=str(uuid.uuid4()),
        action="agent_token_create",
        user_id=admin_user.id,
        resource_type="agent_api_token",
        resource_id=created.record.id,
        details=f"user_id={payload.user_id}; buyer_id={token_buyer_id}; scopes={','.join(created.record.scopes)}",
    )
    return AgentTokenCreateResponse(
        token=created.token,
        token_record=_token_response(created.record),
    )


@router.get("/tokens", response_model=AgentTokenListResponse)
async def list_agent_tokens(
    user_id: str | None = Query(None),
    buyer_id: str | None = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    _admin_user: User = Depends(require_token_admin),
    token_service: AgentTokenService = Depends(get_agent_token_service),
) -> AgentTokenListResponse:
    """List outside-agent tokens without exposing plaintext secrets."""
    records = await token_service.list_tokens(
        user_id=user_id,
        buyer_id=buyer_id,
        active_only=active_only,
        limit=limit,
    )
    return AgentTokenListResponse(tokens=[_token_response(record) for record in records])


@router.delete("/tokens/{token_id}")
async def revoke_agent_token(
    token_id: str,
    admin_user: User = Depends(require_token_admin),
    token_service: AgentTokenService = Depends(get_agent_token_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Revoke an outside-agent token."""
    revoked = await token_service.revoke_token(token_id=token_id, revoked_by=admin_user.id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Agent token not found or already revoked.")
    await auth_service.log_audit(
        audit_id=str(uuid.uuid4()),
        action="agent_token_revoke",
        user_id=admin_user.id,
        resource_type="agent_api_token",
        resource_id=token_id,
    )
    return {"status": "revoked", "token_id": token_id}
