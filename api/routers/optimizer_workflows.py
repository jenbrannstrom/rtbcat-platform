"""Composite optimizer workflow endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_current_user, get_store, resolve_buyer_id
from services.auth_service import User
from services.optimizer_proposals_service import OptimizerProposalsService
from services.optimizer_scoring_service import OptimizerScoringService


router = APIRouter(prefix="/optimizer/workflows", tags=["Optimizer"])


class ScoreAndProposeResponse(BaseModel):
    buyer_id: str
    model_id: str
    score_run: dict
    proposal_run: dict


@router.post("/score-and-propose", response_model=ScoreAndProposeResponse)
async def run_score_and_propose_workflow(
    model_id: str = Query(...),
    buyer_id: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    event_type: Optional[str] = Query(None),
    score_limit: int = Query(1000, ge=1, le=5000),
    min_confidence: float = Query(0.3, ge=0.0, le=1.0),
    max_delta_pct: float = Query(0.3, ge=0.05, le=1.0),
    proposal_limit: int = Query(200, ge=1, le=2000),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    resolved_buyer_id = buyer_id or "unknown"

    scoring_service = OptimizerScoringService()
    proposals_service = OptimizerProposalsService()

    try:
        score_run = await scoring_service.run_scoring(
            model_id=model_id,
            buyer_id=resolved_buyer_id,
            days=days,
            start_date=start_date,
            end_date=end_date,
            event_type=event_type,
            limit=score_limit,
        )
        proposal_run = await proposals_service.generate_from_scores(
            model_id=model_id,
            buyer_id=resolved_buyer_id,
            days=days,
            min_confidence=min_confidence,
            max_delta_pct=max_delta_pct,
            limit=proposal_limit,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc

    return ScoreAndProposeResponse(
        buyer_id=resolved_buyer_id,
        model_id=model_id,
        score_run=score_run,
        proposal_run=proposal_run,
    )

