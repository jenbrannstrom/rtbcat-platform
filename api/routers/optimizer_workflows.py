"""Composite optimizer workflow endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_current_user, get_store, resolve_buyer_id
from services.auth_service import User
from services.optimizer_proposals_service import OptimizerProposalsService
from services.optimizer_scoring_service import OptimizerScoringService


router = APIRouter(prefix="/optimizer/workflows", tags=["Optimizer"])

_WORKFLOW_PROFILES = {
    "safe": {
        "days": 14,
        "score_limit": 500,
        "proposal_limit": 100,
        "min_confidence": 0.45,
        "max_delta_pct": 0.2,
    },
    "balanced": {
        "days": 14,
        "score_limit": 1000,
        "proposal_limit": 200,
        "min_confidence": 0.3,
        "max_delta_pct": 0.3,
    },
    "aggressive": {
        "days": 7,
        "score_limit": 2000,
        "proposal_limit": 400,
        "min_confidence": 0.2,
        "max_delta_pct": 0.5,
    },
}


class ScoreAndProposeResponse(BaseModel):
    buyer_id: str
    model_id: str
    score_run: dict
    proposal_run: dict


@router.post("/score-and-propose", response_model=ScoreAndProposeResponse)
async def run_score_and_propose_workflow(
    model_id: str = Query(...),
    buyer_id: Optional[str] = Query(None),
    profile: Optional[Literal["safe", "balanced", "aggressive"]] = Query(None),
    days: Optional[int] = Query(None, ge=1, le=365),
    scoring_days: Optional[int] = Query(None, ge=1, le=365, description="Deprecated alias for days"),
    proposal_days: Optional[int] = Query(None, ge=1, le=365, description="Deprecated alias for days"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    event_type: Optional[str] = Query(None),
    score_limit: Optional[int] = Query(None, ge=1, le=5000),
    scoring_limit: Optional[int] = Query(None, ge=1, le=5000, description="Deprecated alias for score_limit"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    max_delta_pct: Optional[float] = Query(None, ge=0.05, le=1.0),
    proposal_limit: Optional[int] = Query(None, ge=1, le=2000),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    resolved_buyer_id = buyer_id or "unknown"
    defaults = dict(_WORKFLOW_PROFILES.get(profile or "balanced", _WORKFLOW_PROFILES["balanced"]))

    resolved_days = defaults["days"]
    if days is not None:
        resolved_days = days
    if proposal_days is not None:
        resolved_days = proposal_days
    if scoring_days is not None:
        resolved_days = scoring_days

    resolved_score_limit = defaults["score_limit"]
    if score_limit is not None:
        resolved_score_limit = score_limit
    if scoring_limit is not None:
        resolved_score_limit = scoring_limit

    resolved_proposal_limit = proposal_limit if proposal_limit is not None else defaults["proposal_limit"]
    resolved_min_confidence = min_confidence if min_confidence is not None else defaults["min_confidence"]
    resolved_max_delta_pct = max_delta_pct if max_delta_pct is not None else defaults["max_delta_pct"]

    scoring_service = OptimizerScoringService()
    proposals_service = OptimizerProposalsService()

    try:
        score_run = await scoring_service.run_scoring(
            model_id=model_id,
            buyer_id=resolved_buyer_id,
            days=resolved_days,
            start_date=start_date,
            end_date=end_date,
            event_type=event_type,
            limit=resolved_score_limit,
        )
        proposal_run = await proposals_service.generate_from_scores(
            model_id=model_id,
            buyer_id=resolved_buyer_id,
            days=resolved_days,
            min_confidence=resolved_min_confidence,
            max_delta_pct=resolved_max_delta_pct,
            limit=resolved_proposal_limit,
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
