"""Common schema models shared across the API."""

from typing import Optional, TypeVar, Generic
from pydantic import BaseModel, Field

T = TypeVar('T')


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    timeframe_days: Optional[int] = None
    total: int
    returned: int
    limit: int
    offset: int
    has_more: bool


class VideoPreview(BaseModel):
    """Video creative preview data."""
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    vast_xml: Optional[str] = None
    duration: Optional[str] = None


class HtmlPreview(BaseModel):
    """HTML creative preview data."""
    snippet: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail_url: Optional[str] = None


class ImagePreview(BaseModel):
    """Image data for native creatives."""
    url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class NativePreview(BaseModel):
    """Native creative preview data."""
    headline: Optional[str] = None
    body: Optional[str] = None
    call_to_action: Optional[str] = None
    click_link_url: Optional[str] = None
    image: Optional[ImagePreview] = None
    logo: Optional[ImagePreview] = None


class ThumbnailStatusResponse(BaseModel):
    """Response model for thumbnail generation status."""
    status: Optional[str] = None
    error_reason: Optional[str] = None
    has_thumbnail: bool = False
    thumbnail_url: Optional[str] = None


class WasteFlagsResponse(BaseModel):
    """Response model for waste detection flags."""
    broken_video: bool = False
    zero_engagement: bool = False
