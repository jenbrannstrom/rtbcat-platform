"""Recommendations Router - Optimization recommendation endpoints.

The recommendation surface is temporarily contained because its legacy metric
queries aggregate data across buyers.  Keep every endpoint fail-closed until
the complete call graph and serving data are buyer-scoped.
"""

from typing import NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_current_user, require_seat_admin_or_sudo
from services.auth_service import User

router = APIRouter(tags=["Recommendations"])

RECOMMENDATIONS_UNAVAILABLE_DETAIL = (
    "Recommendations are temporarily unavailable while tenant isolation is upgraded."
)


def _raise_recommendations_unavailable() -> NoReturn:
    """Fail closed until recommendation inputs and persistence are buyer-safe."""
    raise HTTPException(
        status_code=503,
        detail=RECOMMENDATIONS_UNAVAILABLE_DETAIL,
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
    _user: User = Depends(get_current_user),
) -> list[RecommendationResponse]:
    """Fail closed while buyer-scoped recommendation generation is rebuilt."""
    _ = (days, min_severity)
    _raise_recommendations_unavailable()


@router.get("/recommendations/summary", response_model=RecommendationSummaryResponse)
async def get_recommendations_summary(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    _user: User = Depends(get_current_user),
) -> RecommendationSummaryResponse:
    """Fail closed while buyer-scoped recommendation summaries are rebuilt."""
    _ = days
    _raise_recommendations_unavailable()


@router.post("/recommendations/{recommendation_id}/resolve")
async def resolve_recommendation(
    recommendation_id: str,
    notes: Optional[str] = Query(None, description="Resolution notes"),
    _user: User = Depends(require_seat_admin_or_sudo),
) -> dict[str, str]:
    """Fail closed while recommendation ownership is made buyer-specific."""
    _ = (recommendation_id, notes)
    _raise_recommendations_unavailable()


@router.get(
    "/recommendations/by-type/{rec_type}", response_model=list[RecommendationResponse]
)
async def get_recommendations_by_type(
    rec_type: str,
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    _user: User = Depends(get_current_user),
) -> list[RecommendationResponse]:
    """Fail closed while buyer-scoped recommendation generation is rebuilt."""
    _ = (rec_type, days)
    _raise_recommendations_unavailable()
