"""Creative-related schema models."""

from typing import Optional
from pydantic import BaseModel, Field

from .common import (
    VideoPreview,
    HtmlPreview,
    NativePreview,
    ThumbnailStatusResponse,
    WasteFlagsResponse,
    PaginationMeta,
)


class CreativeDataSource(BaseModel):
    """Source metadata for preview payload quality."""

    source: str = Field(..., description="live or cache")
    cached_at: Optional[str] = None
    fetched_at: Optional[str] = None
    stale_threshold_hours: Optional[int] = None
    stale_age_hours: Optional[float] = None
    is_stale: bool = False
    fallback_reason: Optional[str] = None


class CreativeResponse(BaseModel):
    """Response model for creative data."""
    id: str
    name: str
    format: str
    account_id: Optional[str] = None
    buyer_id: Optional[str] = None
    approval_status: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    final_url: Optional[str] = None
    display_url: Optional[str] = None
    resolved_destination_url: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    advertiser_name: Optional[str] = None
    campaign_id: Optional[str] = None
    cluster_id: Optional[str] = None
    seat_name: Optional[str] = None
    country: Optional[str] = None
    video: Optional[VideoPreview] = None
    html: Optional[HtmlPreview] = None
    native: Optional[NativePreview] = None
    thumbnail_status: Optional[ThumbnailStatusResponse] = None
    waste_flags: Optional[WasteFlagsResponse] = None
    # Phase 29: App info and disapproval tracking
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    app_store: Optional[str] = None
    is_disapproved: bool = False
    disapproval_reasons: Optional[list] = None
    serving_restrictions: Optional[list] = None
    # Language detection (Creative geo display)
    detected_language: Optional[str] = None
    detected_language_code: Optional[str] = None
    language_confidence: Optional[float] = None
    language_source: Optional[str] = None
    language_analyzed_at: Optional[str] = None
    language_analysis_error: Optional[str] = None
    # Live/cache preview source metadata
    data_source: Optional[CreativeDataSource] = None


class ClusterAssignment(BaseModel):
    """Request model for cluster assignment."""
    creative_id: str
    cluster_id: str


class PaginatedCreativesResponse(BaseModel):
    """Paginated response for creatives list."""
    data: list[CreativeResponse]
    meta: PaginationMeta


class NewlyUploadedCreativesResponse(BaseModel):
    """Response for newly uploaded creatives."""
    creatives: list[dict]
    total_count: int
    period_start: str
    period_end: str


class CreativeLiveResponse(BaseModel):
    """Response model for live creative endpoint."""

    creative: CreativeResponse
    source: str
    fetched_at: str
    message: Optional[str] = None


class CreativeCountryMetrics(BaseModel):
    """Country-level metrics for a creative."""

    country_code: str
    country_name: str
    country_iso3: Optional[str] = None
    spend_micros: int
    impressions: int
    clicks: int
    spend_percent: float


class CreativeCountryBreakdownResponse(BaseModel):
    """Response for creative country breakdown."""

    creative_id: str
    countries: list[CreativeCountryMetrics]
    total_countries: int
    period_days: int


class CreativeDestinationCandidate(BaseModel):
    source: str
    url: str
    eligible: bool
    reason: Optional[str] = None


class CreativeDestinationDiagnosticsResponse(BaseModel):
    creative_id: str
    buyer_id: Optional[str] = None
    resolved_destination_url: Optional[str] = None
    candidate_count: int
    eligible_count: int
    candidates: list[CreativeDestinationCandidate]
    has_any_macro: bool = False
    has_click_macro: bool = False
    macro_tokens: list[str] = Field(default_factory=list)
    click_macro_tokens: list[str] = Field(default_factory=list)


class CreativeClickMacroCoverageRow(BaseModel):
    creative_id: str
    creative_name: str
    buyer_id: Optional[str] = None
    format: Optional[str] = None
    approval_status: Optional[str] = None
    has_any_macro: bool = False
    has_click_macro: bool = False
    macro_tokens: list[str] = Field(default_factory=list)
    click_macro_tokens: list[str] = Field(default_factory=list)
    url_sources: list[str] = Field(default_factory=list)
    url_count: int = 0
    sample_url: Optional[str] = None
    has_appsflyer_url: bool = False
    has_appsflyer_clickid: bool = False
    sample_appsflyer_url: Optional[str] = None


class CreativeClickMacroCoverageSummary(BaseModel):
    creatives_with_click_macro: int
    creatives_without_click_macro: int
    creatives_with_any_macro: int
    creatives_with_appsflyer_url: int = 0
    creatives_with_appsflyer_clickid: int = 0


class CreativeClickMacroCoverageResponse(BaseModel):
    rows: list[CreativeClickMacroCoverageRow]
    total: int
    returned: int
    limit: int
    offset: int
    summary: CreativeClickMacroCoverageSummary
