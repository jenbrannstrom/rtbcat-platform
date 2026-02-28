"""BYOM optimizer QPS proposal endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_current_user, get_store, resolve_buyer_id
from services.auth_service import User
from services.optimizer_proposals_service import OptimizerProposalsService


router = APIRouter(prefix="/optimizer/proposals", tags=["Optimizer"])


class ProposalRow(BaseModel):
    proposal_id: str
    model_id: str
    buyer_id: str
    billing_id: str
    current_qps: float
    proposed_qps: float
    delta_qps: float
    rationale: str
    projected_impact: dict[str, Any]
    apply_details: Optional[dict[str, Any]] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    applied_at: Optional[str] = None


class ProposalMeta(BaseModel):
    total: int
    returned: int
    limit: int
    offset: int
    has_more: bool


class ProposalListResponse(BaseModel):
    rows: list[ProposalRow]
    meta: ProposalMeta


class ProposalHistoryRow(BaseModel):
    event_id: str
    proposal_id: str
    buyer_id: str
    from_status: Optional[str] = None
    to_status: str
    apply_mode: Optional[str] = None
    changed_by: Optional[str] = None
    details: dict[str, Any]
    created_at: Optional[str] = None


class ProposalHistoryResponse(BaseModel):
    rows: list[ProposalHistoryRow]
    meta: ProposalMeta


class ProposalGenerateTop(BaseModel):
    proposal_id: str
    billing_id: str
    current_qps: float
    proposed_qps: float
    delta_qps: float
    rationale: str
    status: str


class ProposalGenerateResponse(BaseModel):
    model_id: str
    buyer_id: str
    days: int
    min_confidence: float
    max_delta_pct: float
    scores_considered: int
    proposals_created: int
    top_proposals: list[ProposalGenerateTop]


class ProposalStatusResponse(BaseModel):
    proposal_id: str
    status: str
    apply_details: Optional[dict[str, Any]] = None


@router.post("/generate", response_model=ProposalGenerateResponse)
async def generate_qps_proposals(
    model_id: str = Query(...),
    buyer_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    min_confidence: float = Query(0.3, ge=0.0, le=1.0),
    max_delta_pct: float = Query(0.3, ge=0.05, le=1.0),
    limit: int = Query(200, ge=1, le=2000),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerProposalsService()
    try:
        payload = await service.generate_from_scores(
            model_id=model_id,
            buyer_id=buyer_id or "unknown",
            days=days,
            min_confidence=min_confidence,
            max_delta_pct=max_delta_pct,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProposalGenerateResponse(**payload)


@router.get("", response_model=ProposalListResponse)
async def list_qps_proposals(
    buyer_id: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    billing_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="draft | approved | applied | rejected"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerProposalsService()
    try:
        payload = await service.list_proposals(
            buyer_id=buyer_id or "unknown",
            model_id=model_id,
            billing_id=billing_id,
            status=status,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProposalListResponse(**payload)


@router.get("/{proposal_id}", response_model=ProposalRow)
async def get_qps_proposal(
    proposal_id: str,
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerProposalsService()
    payload = await service.get_proposal(
        proposal_id=proposal_id,
        buyer_id=resolved_buyer_id or "unknown",
    )
    if not payload:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ProposalRow(**payload)


@router.get("/{proposal_id}/history", response_model=ProposalHistoryResponse)
async def list_qps_proposal_history(
    proposal_id: str,
    buyer_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerProposalsService()
    payload = await service.list_history(
        proposal_id=proposal_id,
        buyer_id=resolved_buyer_id or "unknown",
        limit=limit,
        offset=offset,
    )
    return ProposalHistoryResponse(**payload)


async def _update_proposal_status(
    *,
    proposal_id: str,
    status: str,
    apply_mode: str = "queue",
    buyer_id: Optional[str],
    store,
    user: User,
) -> ProposalStatusResponse:
    resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerProposalsService()
    try:
        payload = await service.update_status(
            proposal_id=proposal_id,
            buyer_id=resolved_buyer_id or "unknown",
            status=status,
            apply_mode=apply_mode,
            applied_by=getattr(user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not payload:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ProposalStatusResponse(
        proposal_id=payload["proposal_id"],
        status=payload["status"],
        apply_details=payload.get("apply_details"),
    )


@router.post("/{proposal_id}/approve", response_model=ProposalStatusResponse)
async def approve_qps_proposal(
    proposal_id: str,
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    return await _update_proposal_status(
        proposal_id=proposal_id,
        status="approved",
        buyer_id=buyer_id,
        store=store,
        user=user,
    )


@router.post("/{proposal_id}/reject", response_model=ProposalStatusResponse)
async def reject_qps_proposal(
    proposal_id: str,
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    return await _update_proposal_status(
        proposal_id=proposal_id,
        status="rejected",
        buyer_id=buyer_id,
        store=store,
        user=user,
    )


@router.post("/{proposal_id}/apply", response_model=ProposalStatusResponse)
async def apply_qps_proposal(
    proposal_id: str,
    mode: str = Query("queue", description="queue | live"),
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    return await _update_proposal_status(
        proposal_id=proposal_id,
        status="applied",
        apply_mode=mode,
        buyer_id=buyer_id,
        store=store,
        user=user,
    )


@router.post("/{proposal_id}/sync-apply-status", response_model=ProposalRow)
async def sync_qps_proposal_apply_status(
    proposal_id: str,
    buyer_id: Optional[str] = Query(None),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerProposalsService()
    payload = await service.sync_apply_status(
        proposal_id=proposal_id,
        buyer_id=resolved_buyer_id or "unknown",
    )
    if not payload:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ProposalRow(**payload)
