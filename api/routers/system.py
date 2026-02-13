"""System and Thumbnails router for Cat-Scan Creative Intelligence.

This module provides system status and thumbnail management endpoints.
"""

import logging
import os
from pathlib import Path

from storage.postgres_database import pg_query_one
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.dependencies import get_store, get_config, get_current_user, resolve_buyer_id
from services.auth_service import User
from config import ConfigManager
from services.thumbnails_service import ThumbnailsService
from services.system_service import SystemService
from services.secrets_health_service import get_secrets_health
from services.data_health_service import DataHealthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


def get_version() -> str:
    """Get app version from IMAGE_TAG / APP_VERSION env (sha-based).

    The canonical version identifier is the git SHA set via IMAGE_TAG
    in docker-compose.gcp.yml.  The legacy VERSION file is ignored.
    """
    if version := os.environ.get("APP_VERSION"):
        return version
    # Fall back to git sha so local dev also shows a useful identifier
    return get_git_sha()


def get_git_sha() -> str:
    """Get git SHA from env or from .git metadata baked into image."""
    try:
        repo_root = Path(__file__).resolve().parent.parent.parent
        git_dir = repo_root / ".git"
        head = (git_dir / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref_path = git_dir / head.replace("ref: ", "", 1)
            if ref_path.exists():
                return ref_path.read_text().strip()[:8]
        return head[:8]
    except Exception:
        pass

    if git_sha := os.environ.get("GIT_SHA"):
        return git_sha
    return "unknown"


# =============================================================================
# Pydantic Models
# =============================================================================


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    git_sha: str = "unknown"
    configured: bool
    has_credentials: bool = False
    database_exists: bool = False


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    python_version: str
    node_available: bool
    node_version: Optional[str] = None
    ffmpeg_available: bool
    ffmpeg_version: Optional[str] = None
    database_size_mb: float
    thumbnails_count: int
    disk_space_gb: float
    creatives_count: int
    videos_count: int


class ThumbnailGenerateRequest(BaseModel):
    """Request model for generating thumbnail for a single creative."""
    creative_id: str = Field(..., description="The creative ID to generate thumbnail for")


class ThumbnailGenerateResponse(BaseModel):
    """Response model for single thumbnail generation."""
    creative_id: str
    status: str  # 'success', 'failed', 'skipped', 'no_video_url'
    error_reason: Optional[str] = None
    thumbnail_url: Optional[str] = None


class ThumbnailBatchRequest(BaseModel):
    """Request model for batch thumbnail generation."""
    seat_id: Optional[str] = Field(None, description="Generate for specific seat only")
    limit: int = Field(50, ge=1, le=500, description="Maximum thumbnails to generate")
    force: bool = Field(False, description="Retry previously failed thumbnails")


class ThumbnailBatchResponse(BaseModel):
    """Response model for batch thumbnail generation."""
    status: str  # 'started', 'completed'
    total_processed: int
    success_count: int
    failed_count: int
    skipped_count: int
    results: list[ThumbnailGenerateResponse]


class ThumbnailStatusSummary(BaseModel):
    """Summary of thumbnail generation status."""
    total_videos: int
    with_thumbnails: int
    pending: int
    failed: int
    coverage_percent: float
    ffmpeg_available: bool


class ThumbnailFailureMetricsResponse(BaseModel):
    no_url: int
    timeout: int
    ffmpeg: int
    parse: int
    other: int


class HTMLThumbnailRequest(BaseModel):
    """Request model for HTML thumbnail extraction."""
    limit: int = Field(100, ge=1, le=1000, description="Maximum creatives to process")
    force_retry: bool = Field(False, description="Retry previously failed extractions")


class HTMLThumbnailResponse(BaseModel):
    """Response model for HTML thumbnail extraction."""
    status: str
    processed: int
    success: int
    failed: int
    no_image_found: int
    message: Optional[str] = None


class SecretKeyStatus(BaseModel):
    key: str
    configured: bool


class SecretFeatureStatus(BaseModel):
    name: str
    description: str
    enabled: bool
    healthy: bool
    required_keys: list[SecretKeyStatus]
    missing_keys: list[str]


class SecretsHealthSummary(BaseModel):
    enabled_features: int
    required_keys: int
    configured_keys: int
    missing_keys: int


class SecretsHealthResponse(BaseModel):
    checked_at: str
    strict_mode: bool
    healthy: bool
    backend: str
    prefer_env: bool
    name_prefix: str
    summary: SecretsHealthSummary
    missing_required_keys: list[str]
    features: list[SecretFeatureStatus]


class DataHealthTableState(BaseModel):
    rows: int
    max_metric_date: Optional[str] = None


class DataHealthSourceFreshness(BaseModel):
    rtb_daily: DataHealthTableState
    rtb_geo_daily: DataHealthTableState


class DataHealthServingFreshness(BaseModel):
    home_geo_daily: DataHealthTableState
    config_geo_daily: DataHealthTableState
    config_publisher_daily: DataHealthTableState


class DataCoverageSummary(BaseModel):
    total_rows: int
    country_missing_pct: float
    publisher_missing_pct: float
    billing_missing_pct: float
    availability_state: str


class IngestionRunsSummary(BaseModel):
    total_runs: int
    successful_runs: int
    failed_runs: int
    last_started_at: Optional[str] = None
    last_finished_at: Optional[str] = None


class DataHealthResponse(BaseModel):
    checked_at: str
    days: int
    buyer_id: Optional[str] = None
    state: str
    source_freshness: DataHealthSourceFreshness
    serving_freshness: DataHealthServingFreshness
    coverage: DataCoverageSummary
    ingestion_runs: IngestionRunsSummary


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check(
    config: ConfigManager = Depends(get_config),
    store=Depends(get_store),
):
    """Check API health status including credential and database state.

    For the new multi-account system, configured=True only when there are
    service accounts in the database. Legacy config.enc is ignored for
    the configured status since the UI now uses the multi-account system.
    """
    has_credentials = False
    configured = False

    # Check multi-account system - configured if any accounts exist
    try:
        service_accounts = await store.get_service_accounts(active_only=False)
        if service_accounts:
            configured = True
            has_credentials = any(
                acc.credentials_path for acc in service_accounts
            )
    except Exception:
        pass

    # Note: We intentionally do NOT fall back to legacy config.is_configured()
    # because the UI now uses the multi-account system exclusively.
    # The legacy config.enc may exist but is not used for displaying
    # "Connected Accounts" in the Setup page.

    postgres_dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    database_exists = False

    if postgres_dsn:
        try:
            row = await pg_query_one("SELECT 1 AS ok")
            database_exists = bool(row and row.get("ok") == 1)
        except Exception:
            database_exists = False

    return HealthResponse(
        status="healthy",
        version=get_version(),
        git_sha=get_git_sha(),
        configured=configured,
        has_credentials=has_credentials,
        database_exists=database_exists,
    )


@router.get("/thumbnails/{creative_id}.jpg", tags=["Thumbnails"])
async def get_thumbnail(creative_id: str):
    """Serve locally-generated video thumbnail."""
    thumb_path = Path.home() / ".catscan" / "thumbnails" / f"{creative_id}.jpg"
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb_path, media_type="image/jpeg")


@router.get("/thumbnails/status", response_model=ThumbnailStatusSummary, tags=["Thumbnails"])
async def get_thumbnail_status(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get summary of thumbnail generation status.

    Optionally filter by buyer_id to see status for a specific account.
    """
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)

    service = ThumbnailsService()
    summary = await service.get_status_summary(buyer_id)

    return ThumbnailStatusSummary(
        total_videos=summary.total_videos,
        with_thumbnails=summary.with_thumbnails,
        pending=summary.pending,
        failed=summary.failed,
        coverage_percent=summary.coverage_percent,
        ffmpeg_available=summary.ffmpeg_available,
    )


@router.get("/thumbnails/failure-metrics", response_model=ThumbnailFailureMetricsResponse, tags=["Thumbnails"])
async def get_thumbnail_failure_metrics():
    """Get thumbnail failure counts by normalized error category."""
    service = ThumbnailsService()
    metrics = await service.get_failure_metrics()
    return ThumbnailFailureMetricsResponse(**metrics)


@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get system status including installed tools and resource usage."""
    service = SystemService()
    status = await service.get_system_status()

    return SystemStatusResponse(
        python_version=status.python_version,
        node_available=status.node_available,
        node_version=status.node_version,
        ffmpeg_available=status.ffmpeg_available,
        ffmpeg_version=status.ffmpeg_version,
        database_size_mb=status.database_size_mb,
        thumbnails_count=status.thumbnails_count,
        disk_space_gb=status.disk_space_gb,
        creatives_count=status.creatives_count,
        videos_count=status.videos_count,
    )


@router.get("/system/secrets-health", response_model=SecretsHealthResponse)
async def get_system_secrets_health():
    """Get non-sensitive status of required secrets per enabled feature."""
    return SecretsHealthResponse(**get_secrets_health())


@router.get("/system/data-health", response_model=DataHealthResponse)
async def get_system_data_health(
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get source/serving freshness and dimension coverage state."""
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = DataHealthService()
    return DataHealthResponse(**await service.get_data_health(days=days, buyer_id=buyer_id))


@router.post("/thumbnails/generate", response_model=ThumbnailGenerateResponse, tags=["Thumbnails"])
async def generate_single_thumbnail(
    request: ThumbnailGenerateRequest,
    store=Depends(get_store),
):
    """Generate thumbnail for a single video creative."""
    service = ThumbnailsService()

    if not service.check_ffmpeg():
        raise HTTPException(status_code=503, detail="ffmpeg not installed on server")

    result = await service.generate_thumbnail(request.creative_id)

    if result.status == "failed" and result.error_reason == "creative_not_found":
        raise HTTPException(status_code=404, detail="Creative not found")

    return ThumbnailGenerateResponse(
        creative_id=result.creative_id,
        status=result.status,
        error_reason=result.error_reason,
        thumbnail_url=result.thumbnail_url,
    )


@router.post("/thumbnails/generate-batch", response_model=ThumbnailBatchResponse, tags=["Thumbnails"])
async def generate_batch_thumbnails(
    request: ThumbnailBatchRequest,
    store=Depends(get_store),
):
    """Generate thumbnails for multiple video creatives.

    Processes videos that don't have thumbnails yet (or failed ones if force=True).
    """
    service = ThumbnailsService()

    if not service.check_ffmpeg():
        raise HTTPException(status_code=503, detail="ffmpeg not installed on server")

    batch_results = await service.generate_batch(limit=request.limit, force=request.force)

    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for r in batch_results:
        results.append(ThumbnailGenerateResponse(
            creative_id=r.creative_id,
            status=r.status,
            error_reason=r.error_reason,
            thumbnail_url=r.thumbnail_url,
        ))
        if r.status == "success":
            success_count += 1
        elif r.status == "failed":
            failed_count += 1
        else:
            skipped_count += 1

    return ThumbnailBatchResponse(
        status='completed',
        total_processed=len(batch_results),
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        results=results,
    )


@router.post("/thumbnails/extract-html", response_model=HTMLThumbnailResponse, tags=["Thumbnails"])
async def extract_html_thumbnails(
    request: HTMLThumbnailRequest = HTMLThumbnailRequest(),
    store=Depends(get_store),
):
    """Extract thumbnail URLs from HTML creatives.

    Parses HTML creative snippets to find embedded image URLs (from <img src> tags,
    JavaScript document.write, or background-image styles) and saves them to
    thumbnail_status for display in the dashboard.
    """
    result = await store.process_html_thumbnails(
        limit=request.limit,
        force_retry=request.force_retry
    )

    return HTMLThumbnailResponse(
        status="completed",
        processed=result.get("processed", 0),
        success=result.get("success", 0),
        failed=result.get("failed", 0),
        no_image_found=result.get("no_image_found", 0),
        message=result.get("message"),
    )


# =============================================================================
# Stats and Sizes endpoints
# =============================================================================


class StatsResponse(BaseModel):
    """Response model for database statistics."""
    creative_count: int
    buyer_seat_count: int
    formats: dict[str, int]


class SizesResponse(BaseModel):
    """Response model for available creative sizes."""
    sizes: list[str]


class GeoLookupResponse(BaseModel):
    """Response model for geo ID to name mapping."""
    geos: dict[str, str]  # geo_id -> display name


@router.get("/geos/lookup", response_model=GeoLookupResponse)
async def lookup_geo_names(
    ids: str = Query(..., description="Comma-separated list of Google geo criterion IDs"),
):
    """Look up human-readable names for Google geo criterion IDs.

    Accepts IDs like "21155,21164,21171" and returns names like
    {"21155": "Los Angeles, CA", "21164": "New York, NY"}.

    Falls back to inline mapping or original ID if not found in database.
    """
    geo_ids = [g.strip() for g in ids.split(",") if g.strip()]

    if not geo_ids:
        return GeoLookupResponse(geos={})

    service = SystemService()
    geos = await service.lookup_geo_names(geo_ids)

    return GeoLookupResponse(geos=geos)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(store=Depends(get_store)):
    """Get database statistics."""
    stats = await store.get_stats()
    return StatsResponse(
        creative_count=stats.get("total_creatives", 0),
        buyer_seat_count=stats.get("total_buyer_seats", 0),
        formats=stats.get("by_format", {}),
    )


@router.get("/sizes", response_model=SizesResponse)
async def get_sizes(store=Depends(get_store)):
    """Get available creative sizes from the database."""
    rows = await store.get_available_sizes()
    # store returns list[dict] with canonical_size/count; extract strings
    sizes = [row["canonical_size"] for row in rows if row.get("canonical_size")]
    return SizesResponse(sizes=sizes)
