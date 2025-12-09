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
    creatives: list[CreativeResponse]
    total: int
    since_days: int
