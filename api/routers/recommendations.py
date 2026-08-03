"""Buyer-scoped optimization recommendation endpoints."""

import logging
from typing import NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from analytics.recommendation_data import RecommendationDataUnavailable
from api.dependencies import (
    get_current_user,
    get_store,
    resolve_admin_buyer_id,
    resolve_buyer_id,
)
from services.auth_service import User
from services.recommendations_service import RecommendationsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Recommendations"])

RECOMMENDATION_DATA_UNAVAILABLE_DETAIL = (
    "Buyer-scoped recommendation metrics are temporarily unavailable."
)


def _require_recommendation_buyer_id(buyer_id: Optional[str]) -> str:
    """Recommendation analysis never permits a global buyer scope."""
    if not buyer_id:
        raise HTTPException(
            status_code=400,
            detail="buyer_id is required for recommendation endpoints.",
        )
    return buyer_id


def _raise_data_unavailable() -> NoReturn:
    raise HTTPException(
        status_code=503,
        detail=RECOMMENDATION_DATA_UNAVAILABLE_DETAIL,
    )


# =============================================================================
# Pydantic Models
# =============================================================================


class EvidenceResponse(BaseModel):
    """Evidence supporting a recommendation."""

    metric_name: str
    metric_value: float
    threshold: float
    comparison: str
    time_period_days: int
    sample_size: int
    trend: Optional[str] = None


class ImpactResponse(BaseModel):
    """Quantified impact of an issue."""

    wasted_qps: float
    wasted_queries_daily: int
    wasted_spend_usd: float
    percent_of_total_waste: float
    potential_savings_monthly: float


class ActionResponse(BaseModel):
    """Recommended action to take."""

    action_type: str
    target_type: str
    target_id: str
    target_name: str
    pretargeting_field: Optional[str] = None
    api_example: Optional[str] = None


class RecommendationResponse(BaseModel):
    """A complete optimization recommendation."""

    id: str
    type: str
    severity: str
    confidence: str
    title: str
    description: str
    evidence: list[EvidenceResponse]
    impact: ImpactResponse
    actions: list[ActionResponse]
    affected_creatives: list[str]
    affected_campaigns: list[str]
    generated_at: str
    expires_at: Optional[str] = None
    status: str


class RecommendationSummaryResponse(BaseModel):
    """Summary of recommendations by severity."""

    analysis_period_days: int
    total_queries: int
    total_impressions: int
    total_waste_queries: int
    total_waste_rate: float
    total_wasted_qps: float
    total_spend_usd: float
    recommendation_count: dict[str, int]
    total_recommendations: int
    generated_at: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/recommendations", response_model=list[RecommendationResponse])
async def get_recommendations(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    min_severity: str = Query(
        "low", description="Minimum severity: low, medium, high, critical"
    ),
    buyer_id: Optional[str] = Query(None, description="Buyer seat ID"),
    user: User = Depends(get_current_user),
    store=Depends(get_store),
) -> list[RecommendationResponse]:
    """Generate recommendations for one authorized buyer."""
    try:
        resolved_buyer_id = _require_recommendation_buyer_id(
            await resolve_buyer_id(buyer_id, store=store, user=user)
        )
        service = RecommendationsService(store)
        return await service.generate(
            buyer_id=resolved_buyer_id,
            days=days,
            min_severity=min_severity,
        )
    except HTTPException:
        raise
    except RecommendationDataUnavailable:
        _raise_data_unavailable()
    except Exception:
        logger.exception("Failed to generate buyer-scoped recommendations")
        raise HTTPException(
            status_code=500, detail="Failed to generate recommendations"
        )


@router.get("/recommendations/summary", response_model=RecommendationSummaryResponse)
async def get_recommendations_summary(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    buyer_id: Optional[str] = Query(None, description="Buyer seat ID"),
    user: User = Depends(get_current_user),
    store=Depends(get_store),
) -> RecommendationSummaryResponse:
    """Return summary metrics for one authorized buyer."""
    try:
        resolved_buyer_id = _require_recommendation_buyer_id(
            await resolve_buyer_id(buyer_id, store=store, user=user)
        )
        return await RecommendationsService(store).summary(
            buyer_id=resolved_buyer_id,
            days=days,
        )
    except HTTPException:
        raise
    except RecommendationDataUnavailable:
        _raise_data_unavailable()
    except Exception:
        logger.exception("Failed to summarize buyer-scoped recommendations")
        raise HTTPException(
            status_code=500, detail="Failed to summarize recommendations"
        )


@router.post("/recommendations/{recommendation_id}/resolve")
async def resolve_recommendation(
    recommendation_id: str,
    notes: Optional[str] = Query(None, description="Resolution notes"),
    buyer_id: Optional[str] = Query(None, description="Buyer seat ID"),
    user: User = Depends(get_current_user),
    store=Depends(get_store),
) -> dict[str, str]:
    """Resolve a recommendation owned by one administered buyer."""
    try:
        resolved_buyer_id = _require_recommendation_buyer_id(
            await resolve_admin_buyer_id(buyer_id, store=store, user=user)
        )
        success = await RecommendationsService(store).resolve(
            buyer_id=resolved_buyer_id,
            recommendation_id=recommendation_id,
            notes=notes,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        return {"status": "resolved", "id": recommendation_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to resolve buyer-owned recommendation")
        raise HTTPException(status_code=500, detail="Failed to resolve recommendation")


@router.get(
    "/recommendations/by-type/{rec_type}", response_model=list[RecommendationResponse]
)
async def get_recommendations_by_type(
    rec_type: str,
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    buyer_id: Optional[str] = Query(None, description="Buyer seat ID"),
    user: User = Depends(get_current_user),
    store=Depends(get_store),
) -> list[RecommendationResponse]:
    """Return one recommendation type for an authorized buyer."""
    try:
        resolved_buyer_id = _require_recommendation_buyer_id(
            await resolve_buyer_id(buyer_id, store=store, user=user)
        )
        return await RecommendationsService(store).by_type(
            buyer_id=resolved_buyer_id,
            rec_type=rec_type,
            days=days,
        )
    except HTTPException:
        raise
    except RecommendationDataUnavailable:
        _raise_data_unavailable()
    except Exception:
        logger.exception("Failed to filter buyer-scoped recommendations")
        raise HTTPException(status_code=500, detail="Failed to filter recommendations")
