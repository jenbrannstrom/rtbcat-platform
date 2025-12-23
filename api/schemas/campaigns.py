"""Campaign-related schema models."""

from typing import Optional
from pydantic import BaseModel, Field

from .common import PaginationMeta


class CampaignMetricsResponse(BaseModel):
    """Aggregated metrics for a campaign within a timeframe."""
    total_spend_micros: int = 0
    total_impressions: int = 0
    total_clicks: int = 0
    total_reached_queries: int = 0
    avg_cpm: Optional[float] = None
    avg_ctr: Optional[float] = None
    waste_score: Optional[float] = None


class CampaignWarningsResponse(BaseModel):
    """Warning counts for a campaign."""
    broken_video_count: int = 0
    zero_engagement_count: int = 0
    high_spend_low_performance: int = 0
    disapproved_count: int = 0
    non_standard_size_count: int = 0
    low_bid_rate_count: int = 0
    zero_bids_count: int = 0


class CampaignResponse(BaseModel):
    """Response model for campaign data with optional metrics."""
    id: str
    name: str
    creative_ids: list[str] = Field(default_factory=list)
    creative_count: int = 0
    timeframe_days: Optional[int] = None
    metrics: Optional[CampaignMetricsResponse] = None
    warnings: Optional[CampaignWarningsResponse] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PaginatedCampaignsResponse(BaseModel):
    """Paginated response for campaigns list."""
    data: list[CampaignResponse]
    meta: PaginationMeta


class AutoClusterResponse(BaseModel):
    """Response for auto-clustering operation."""
    status: str
    campaigns_created: int
    creatives_clustered: int
    message: str
