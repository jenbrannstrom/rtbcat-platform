"""Buyer-scoped creative reads for outside agents."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.dependencies import get_store, resolve_buyer_id
from api.routers.agent import _enforce_token_buyer, get_auth_service, require_agent_scope
from api.schemas.agent_creative_performance import (
    AgentCreativePerformanceBatchRequest,
    AgentCreativePerformanceBatchResponse,
)
from api.schemas.agent_creatives import (
    AgentCreativeAssetsResponse,
    AgentCreativeDetailResponse,
    AgentCreativeListResponse,
)
from services.agent_creative_performance_service import AgentCreativePerformanceService
from services.agent_creatives_service import AgentCreativesService
from services.agent_token_service import (
    AGENT_ASSETS_READ_SCOPE,
    AGENT_CREATIVE_PERFORMANCE_READ_SCOPE,
    AGENT_CREATIVES_READ_SCOPE,
    AgentAuthContext,
)
from services.auth_service import AuthService

router = APIRouter(prefix="/agent/v1", tags=["Agent API"])

require_agent_creatives_context = require_agent_scope(AGENT_CREATIVES_READ_SCOPE)
require_agent_assets_context = require_agent_scope(AGENT_ASSETS_READ_SCOPE)
require_agent_creative_performance_context = require_agent_scope(
    AGENT_CREATIVE_PERFORMANCE_READ_SCOPE
)


def get_agent_creatives_service() -> AgentCreativesService:
    return AgentCreativesService()


def get_agent_creative_performance_service() -> AgentCreativePerformanceService:
    return AgentCreativePerformanceService()


async def _audit_creative_read(
    *,
    request: Request,
    context: AgentAuthContext,
    auth_service: AuthService,
    action: str,
    resource_id: str,
    details: str,
) -> None:
    await auth_service.log_audit(
        audit_id=str(uuid.uuid4()),
        action=action,
        user_id=context.user.id,
        resource_type="agent_api",
        resource_id=resource_id,
        details=f"token_id={context.token.id}; {details}",
        ip_address=request.client.host if request.client else None,
    )


def _creative_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Creative not found.")


async def _enforce_creative_buyer_access(
    *,
    context: AgentAuthContext,
    buyer_id: str,
    auth_service: AuthService,
) -> None:
    try:
        _enforce_token_buyer(context, buyer_id)
    except HTTPException:
        raise _creative_not_found() from None

    if context.user.role == "sudo":
        return
    allowed_buyer_ids = await auth_service.get_user_buyer_seat_ids(
        context.user.id
    )
    if buyer_id not in allowed_buyer_ids:
        raise _creative_not_found()


@router.get("/creatives", response_model=AgentCreativeListResponse)
async def list_agent_creatives(
    request: Request,
    start_date: date = Query(
        ..., description="Inclusive start metric date (YYYY-MM-DD)."
    ),
    end_date: date = Query(
        ..., description="Inclusive end metric date (YYYY-MM-DD)."
    ),
    buyer_id: str | None = Query(
        None, description="Buyer seat ID. Optional for one-buyer agent users."
    ),
    domain: str | None = Query(
        None, description="Final/display destination host, including subdomains."
    ),
    format: str | None = Query(
        None, description="Exact creative format, case-insensitive."
    ),
    approval_filter: str = Query(
        "all", pattern="^(all|approved|not_approved)$"
    ),
    activity: str = Query("all", pattern="^(all|active|inactive)$"),
    search: str | None = Query(
        None, description="Search ID, name, advertiser, or UTM campaign."
    ),
    sort_by: str = Query("spend", pattern="^spend$"),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    store=Depends(get_store),
    context: AgentAuthContext = Depends(require_agent_creatives_context),
    creatives_service: AgentCreativesService = Depends(get_agent_creatives_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> AgentCreativeListResponse:
    """Search a buyer's creatives using precomputed spend-ranked evidence."""
    resolved_buyer_id = await resolve_buyer_id(
        buyer_id, store=store, user=context.user
    )
    if not resolved_buyer_id:
        raise HTTPException(status_code=400, detail="buyer_id is required.")
    _enforce_token_buyer(context, resolved_buyer_id)

    payload = await creatives_service.list_creatives(
        buyer_id=resolved_buyer_id,
        start_date=start_date,
        end_date=end_date,
        domain=domain,
        creative_format=format,
        approval_filter=approval_filter,
        activity=activity,
        search=search,
        cursor=cursor,
        limit=limit,
    )
    await _audit_creative_read(
        request=request,
        context=context,
        auth_service=auth_service,
        action="agent_creatives_read",
        resource_id=resolved_buyer_id,
        details=(
            f"buyer_id={resolved_buyer_id}; start_date={start_date.isoformat()}; "
            f"end_date={end_date.isoformat()}; returned={len(payload['creatives'])}; "
            f"has_more={payload['has_more']}"
        ),
    )
    return AgentCreativeListResponse(**payload)


@router.get("/creatives/{creative_id}", response_model=AgentCreativeDetailResponse)
async def get_agent_creative(
    creative_id: str,
    request: Request,
    context: AgentAuthContext = Depends(require_agent_creatives_context),
    creatives_service: AgentCreativesService = Depends(get_agent_creatives_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> AgentCreativeDetailResponse:
    """Return creative detail and click-destination diagnostics."""
    payload = await creatives_service.get_creative_detail(creative_id)
    await _enforce_creative_buyer_access(
        context=context,
        buyer_id=payload["buyer_id"],
        auth_service=auth_service,
    )
    await _audit_creative_read(
        request=request,
        context=context,
        auth_service=auth_service,
        action="agent_creatives_read",
        resource_id=creative_id,
        details=(
            f"buyer_id={payload['buyer_id']}; creative_id={creative_id}; "
            "read=detail"
        ),
    )
    return AgentCreativeDetailResponse(**payload)

@router.get(
    "/creatives/{creative_id}/assets",
    response_model=AgentCreativeAssetsResponse,
)
async def get_agent_creative_assets(
    creative_id: str,
    request: Request,
    context: AgentAuthContext = Depends(require_agent_assets_context),
    creatives_service: AgentCreativesService = Depends(get_agent_creatives_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> AgentCreativeAssetsResponse:
    """Return preview-derived asset references without serving bytes."""
    payload = await creatives_service.get_creative_assets(creative_id)
    await _enforce_creative_buyer_access(
        context=context,
        buyer_id=payload["buyer_id"],
        auth_service=auth_service,
    )
    await _audit_creative_read(
        request=request,
        context=context,
        auth_service=auth_service,
        action="agent_asset_read",
        resource_id=creative_id,
        details=(
            f"buyer_id={payload['buyer_id']}; creative_id={creative_id}; "
            "read=asset_references"
        ),
    )
    return AgentCreativeAssetsResponse(**payload)


@router.post(
    "/creative-performance/batch",
    response_model=AgentCreativePerformanceBatchResponse,
)
async def get_agent_creative_performance_batch(
    payload: AgentCreativePerformanceBatchRequest,
    request: Request,
    store=Depends(get_store),
    context: AgentAuthContext = Depends(
        require_agent_creative_performance_context
    ),
    performance_service: AgentCreativePerformanceService = Depends(
        get_agent_creative_performance_service
    ),
    auth_service: AuthService = Depends(get_auth_service),
) -> AgentCreativePerformanceBatchResponse:
    """Return buyer-scoped precomputed evidence for a creative batch."""
    resolved_buyer_id = await resolve_buyer_id(
        payload.buyer_id,
        store=store,
        user=context.user,
    )
    if not resolved_buyer_id:
        raise HTTPException(status_code=400, detail="buyer_id is required.")
    _enforce_token_buyer(context, resolved_buyer_id)

    response = await performance_service.get_batch(
        buyer_id=resolved_buyer_id,
        creative_ids=payload.creative_ids,
        start_date=payload.start_date,
        end_date=payload.end_date,
        tolerance_pct=payload.tolerance_pct,
    )
    await _audit_creative_read(
        request=request,
        context=context,
        auth_service=auth_service,
        action="agent_creative_performance_read",
        resource_id=resolved_buyer_id,
        details=(
            f"buyer_id={resolved_buyer_id}; "
            f"start_date={payload.start_date.isoformat()}; "
            f"end_date={payload.end_date.isoformat()}; "
            f"creative_count={response['count']}"
        ),
    )
    return AgentCreativePerformanceBatchResponse(**response)
