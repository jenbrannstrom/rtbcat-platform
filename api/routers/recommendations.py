"""Recommendations Router - Optimization recommendation endpoints.

Handles generation, listing, and resolution of actionable optimization recommendations.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_current_user, get_store, require_seat_admin_or_sudo
from services.auth_service import User
from services.recommendations_service import RecommendationsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Recommendations"])


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
    min_severity: str = Query("low", description="Minimum severity: low, medium, high, critical"),
    _user: User = Depends(get_current_user),
    store=Depends(get_store),
):
    """
    Get actionable optimization recommendations.

    Phase 25: Core Analytics Engine
    Returns recommendations sorted by impact (highest wasted QPS first).
    """
    try:
        service = RecommendationsService(store)
        return await service.generate(days=days, min_severity=min_severity)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/summary", response_model=RecommendationSummaryResponse)
async def get_recommendations_summary(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    _user: User = Depends(get_current_user),
    store=Depends(get_store),
):
    """
    Get high-level waste summary with recommendation counts.

    Phase 25: Core Analytics Engine
    Returns summary metrics including total waste and recommendation breakdown.
    """
    try:
        service = RecommendationsService(store)
        return await service.summary(days=days)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recommendations summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendations/{recommendation_id}/resolve")
async def resolve_recommendation(
    recommendation_id: str,
    notes: Optional[str] = Query(None, description="Resolution notes"),
    _user: User = Depends(require_seat_admin_or_sudo),
    store=Depends(get_store),
):
    """
    Mark a recommendation as resolved.

    Phase 25: Core Analytics Engine
    Updates the recommendation status and records resolution notes.
    """
    try:
        service = RecommendationsService(store)
        success = await service.resolve(recommendation_id, notes)

        if not success:
            raise HTTPException(status_code=404, detail="Recommendation not found")

        return {"status": "resolved", "id": recommendation_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/by-type/{rec_type}", response_model=list[RecommendationResponse])
async def get_recommendations_by_type(
    rec_type: str,
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    _user: User = Depends(get_current_user),
    store=Depends(get_store),
):
    """
    Get recommendations filtered by type.

    Phase 25: Core Analytics Engine
    Types: size_mismatch, config_inefficiency, publisher_block, app_block,
           geo_exclusion, creative_pause, creative_review, fraud_alert
    """
    try:
        service = RecommendationsService(store)
        return await service.by_type(rec_type, days)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recommendations by type: {e}")
        raise HTTPException(status_code=500, detail=str(e))
