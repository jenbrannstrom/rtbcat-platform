"""Recommendation engine schema models."""

from typing import Optional
from pydantic import BaseModel


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
