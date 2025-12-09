"""System and health check schema models."""

from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    configured: bool
    has_credentials: bool = False
    database_exists: bool = False


class StatsResponse(BaseModel):
    """Response model for database statistics."""
    creative_count: int
    campaign_count: int
    cluster_count: int
    formats: dict[str, int]
    db_path: str


class SizesResponse(BaseModel):
    """Response model for available creative sizes."""
    sizes: list[str]


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    status: str
    api_version: str
    database_status: str
    creative_count: int
    campaign_count: int
    thumbnail_dir_exists: bool
    thumbnail_count: int
    ffmpeg_available: bool


class CollectRequest(BaseModel):
    """Request model for starting a collection job."""
    account_id: str
    filter_query: Optional[str] = None


class CollectResponse(BaseModel):
    """Response model for collection job."""
    status: str
    account_id: str
    filter_query: Optional[str] = None
    message: str
    creatives_collected: Optional[int] = None
