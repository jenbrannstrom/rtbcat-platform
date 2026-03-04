"""BYOM optimizer scoring endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_current_user, get_store, resolve_buyer_id
from services.auth_service import User
from services.optimizer_scoring_service import OptimizerScoringService


router = APIRouter(prefix="/optimizer/scoring", tags=["Optimizer"])


class SegmentScoreRow(BaseModel):
    score_id: str
    model_id: str
    buyer_id: str
    billing_id: str
    country: str
    publisher_id: str
    app_id: str
    creative_size: str
    platform: str
    environment: str
    hour: Optional[int] = None
    score_date: Optional[str] = None
    value_score: float
    confidence: float
    reason_codes: list[str]
    raw_response: dict[str, Any]
    created_at: Optional[str] = None


class SegmentScoresMeta(BaseModel):
    start_date: str
    end_date: str
    total: int
    returned: int
    limit: int
    offset: int
    has_more: bool


class SegmentScoresResponse(BaseModel):
    rows: list[SegmentScoreRow]
    meta: SegmentScoresMeta


class RulesTopScore(BaseModel):
    score_id: str
    billing_id: str
    country: str
    publisher_id: str
    app_id: str
    score_date: str
    value_score: float
    confidence: float
    reason_codes: list[str]


class ScoringRunResponse(BaseModel):
    model_type: Optional[str] = None
    model_id: str
    buyer_id: str
    start_date: str
    end_date: str
    event_type: Optional[str] = None
    segments_scanned: int
    scores_written: int
    top_scores: list[RulesTopScore]


@router.post("/run", response_model=ScoringRunResponse)
async def run_scoring(
    model_id: str = Query(...),
    buyer_id: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    event_type: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> ScoringRunResponse:
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerScoringService()
    try:
        payload = await service.run_scoring(
            model_id=model_id,
            buyer_id=buyer_id or "unknown",
            days=days,
            start_date=start_date,
            end_date=end_date,
            event_type=event_type,
            limit=limit,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    return ScoringRunResponse(**payload)


@router.post("/rules/run", response_model=ScoringRunResponse)
async def run_rules_scoring(
    model_id: str = Query(...),
    buyer_id: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    event_type: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> ScoringRunResponse:
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerScoringService()
    try:
        payload = await service.run_rules_scoring(
            model_id=model_id,
            buyer_id=buyer_id or "unknown",
            days=days,
            start_date=start_date,
            end_date=end_date,
            event_type=event_type,
            limit=limit,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    payload["model_type"] = "rules"
    return ScoringRunResponse(**payload)


@router.get("/segments", response_model=SegmentScoresResponse)
async def list_segment_scores(
    model_id: Optional[str] = Query(None),
    buyer_id: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    billing_id: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    publisher_id: Optional[str] = Query(None),
    app_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> SegmentScoresResponse:
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = OptimizerScoringService()
    try:
        payload = await service.list_scores(
            model_id=model_id,
            buyer_id=buyer_id or "unknown",
            days=days,
            start_date=start_date,
            end_date=end_date,
            billing_id=billing_id,
            country=country,
            publisher_id=publisher_id,
            app_id=app_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SegmentScoresResponse(**payload)
