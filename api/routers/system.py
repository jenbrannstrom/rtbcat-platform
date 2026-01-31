"""System and Thumbnails router for Cat-Scan Creative Intelligence.

This module provides system status and thumbnail management endpoints.
"""

import logging
import os
import shutil
import subprocess
import sys
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.dependencies import get_store, get_config, get_current_user, resolve_buyer_id
from storage.repositories.user_repository import User
from storage.serving_database import db_query, db_execute, table_exists
from config import ConfigManager
from services.thumbnails_service import ThumbnailsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


def get_version() -> str:
    """Get app version from VERSION file or environment variable."""
    # First check environment variable (set in Docker)
    if version := os.environ.get("APP_VERSION"):
        return version

    # Try to read from VERSION file (for local development)
    version_file = Path(__file__).parent.parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()

    # Fallback
    return "0.9.0"


def get_git_sha() -> str:
    """Get git SHA from environment variable (set during Docker build)."""
    return os.environ.get("GIT_SHA", "unknown")


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


# =============================================================================
# Helper Functions
# =============================================================================


def _get_thumbnails_dir() -> Path:
    """Get the thumbnails directory, creating if needed."""
    thumb_dir = Path.home() / ".catscan" / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return thumb_dir


def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    if shutil.which("ffmpeg") is not None:
        return True
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return True
    return False


def _get_ffmpeg_path() -> str:
    """Get the ffmpeg executable path."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return "ffmpeg"


def _classify_ffmpeg_error(returncode: int, stderr: str, url: str) -> str:
    """Classify ffmpeg error into categories."""
    stderr_lower = stderr.lower() if stderr else ""

    if "403" in stderr or "forbidden" in stderr_lower:
        return "url_expired"
    if "404" in stderr or "not found" in stderr_lower:
        return "url_not_found"
    if "timed out" in stderr_lower or "timeout" in stderr_lower:
        return "timeout"
    if "protocol" in stderr_lower or "invalid" in stderr_lower:
        return "invalid_url"
    if "network" in stderr_lower or "connection" in stderr_lower:
        return "network_error"

    return "unknown"


def _generate_thumbnail_ffmpeg(video_url: str, output_path: Path, timeout: int = 15) -> dict:
    """Generate thumbnail from video URL using ffmpeg."""
    try:
        cmd = [
            _get_ffmpeg_path(),
            "-y",
            "-ss", "1",
            "-t", "2",
            "-rw_timeout", "5000000",
            "-i", video_url,
            "-vframes", "1",
            "-vf", "scale='min(480,iw)':'-1'",
            "-q:v", "2",
            str(output_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )

        if result.returncode == 0 and output_path.exists():
            return {'success': True, 'error_reason': None}
        else:
            error_reason = _classify_ffmpeg_error(result.returncode, result.stderr, video_url)
            return {'success': False, 'error_reason': error_reason}

    except subprocess.TimeoutExpired:
        return {'success': False, 'error_reason': 'timeout'}
    except Exception:
        return {'success': False, 'error_reason': 'unknown'}


def _extract_video_url_from_vast(vast_xml: str) -> str | None:
    """Extract video URL from VAST XML."""
    if not vast_xml:
        return None
    import re
    match = re.search(r'<MediaFile[^>]*>(?:<!\[CDATA\[)?(https?://[^\]<]+)', vast_xml)
    return match.group(1).strip() if match else None


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

    # Check new multi-account system - this is the primary credential source
    try:
        service_accounts = await store.get_service_accounts(active_only=True)
        if service_accounts:
            configured = True
            has_credentials = True
    except Exception:
        pass

    # Note: We intentionally do NOT fall back to legacy config.is_configured()
    # because the UI now uses the multi-account system exclusively.
    # The legacy config.enc may exist but is not used for displaying
    # "Connected Accounts" in the Setup page.

    db_path = Path.home() / ".catscan" / "catscan.db"

    return HealthResponse(
        status="healthy",
        version=get_version(),
        git_sha=get_git_sha(),
        configured=configured,
        has_credentials=has_credentials,
        database_exists=db_path.exists(),
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


@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get system status including installed tools and resource usage."""
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    node_available = shutil.which("node") is not None
    node_version = None
    if node_available:
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
            node_version = result.stdout.strip()
        except Exception:
            pass

    ffmpeg_available = _check_ffmpeg()
    ffmpeg_version = None
    if ffmpeg_available:
        try:
            result = subprocess.run([_get_ffmpeg_path(), '-version'], capture_output=True, text=True, timeout=5)
            first_line = result.stdout.split('\n')[0]
            parts = first_line.split(' ')
            ffmpeg_version = parts[2] if len(parts) > 2 else 'Unknown'
        except Exception:
            pass

    # Database size not available for Postgres via file stat
    database_size_mb = 0.0

    thumbnails_dir = Path.home() / ".catscan" / "thumbnails"
    thumbnails_count = len(list(thumbnails_dir.glob("*.jpg"))) if thumbnails_dir.exists() else 0

    total, used, free = shutil.disk_usage(Path.home())
    disk_space_gb = free / (1024 ** 3)

    creatives_count = 0
    videos_count = 0
    try:
        rows = await db_query("SELECT COUNT(*) as cnt FROM creatives")
        creatives_count = rows[0]["cnt"] if rows else 0
        video_rows = await db_query("SELECT COUNT(*) as cnt FROM creatives WHERE format = 'VIDEO'")
        videos_count = video_rows[0]["cnt"] if video_rows else 0
    except Exception:
        pass

    return SystemStatusResponse(
        python_version=python_version,
        node_available=node_available,
        node_version=node_version,
        ffmpeg_available=ffmpeg_available,
        ffmpeg_version=ffmpeg_version,
        database_size_mb=round(database_size_mb, 2),
        thumbnails_count=thumbnails_count,
        disk_space_gb=round(disk_space_gb, 1),
        creatives_count=creatives_count,
        videos_count=videos_count,
    )


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


# Fallback geo ID mappings for common Google Ads criterion IDs
# Used when migration 010 hasn't been run or geographies table is empty
FALLBACK_GEO_NAMES = {
    # US Metro/DMA regions (21xxx series) - most common
    '21155': 'Los Angeles, CA', '21164': 'New York, NY', '21174': 'Chicago, IL',
    '21145': 'Atlanta, GA', '21147': 'Austin, TX', '21149': 'Baltimore, MD',
    '21159': 'Boston, MA', '21170': 'Charlotte, NC', '21176': 'Cincinnati, OH',
    '21178': 'Cleveland-Akron, OH', '21183': 'Columbus, OH', '21186': 'Dallas-Fort Worth, TX',
    '21189': 'Denver, CO', '21191': 'Detroit, MI', '21225': 'Houston, TX',
    '21228': 'Indianapolis, IN', '21231': 'Jacksonville, FL', '21236': 'Kansas City, MO',
    '21244': 'Las Vegas, NV', '21258': 'Miami-Fort Lauderdale, FL', '21260': 'Minneapolis-St. Paul, MN',
    '21267': 'Nashville, TN', '21268': 'New Orleans, LA', '21272': 'Oklahoma City, OK',
    '21274': 'Orlando-Daytona Beach, FL', '21281': 'Philadelphia, PA', '21282': 'Phoenix, AZ',
    '21283': 'Pittsburgh, PA', '21284': 'Portland, OR', '21289': 'Raleigh-Durham, NC',
    '21297': 'Sacramento-Stockton, CA', '21299': 'Saint Louis, MO', '21301': 'Salt Lake City, UT',
    '21303': 'San Antonio, TX', '21304': 'San Diego, CA', '21305': 'San Francisco-Oakland, CA',
    '21308': 'Seattle-Tacoma, WA', '21319': 'Tampa-St. Petersburg, FL', '21332': 'Washington, DC',
    '21152': 'Beaumont-Port Arthur, TX', '21171': 'Charlottesville, VA',
    # Country-level IDs
    '2840': 'United States', '2826': 'United Kingdom', '2124': 'Canada', '2036': 'Australia',
    '2276': 'Germany', '2250': 'France', '2392': 'Japan', '2076': 'Brazil', '2356': 'India',
    '2484': 'Mexico', '2724': 'Spain', '2380': 'Italy', '2528': 'Netherlands', '2586': 'Pakistan',
    '2360': 'Indonesia', '2608': 'Philippines', '2704': 'Vietnam', '2764': 'Thailand',
    '2458': 'Malaysia', '2702': 'Singapore', '2784': 'UAE', '2682': 'Saudi Arabia',
}


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

    # Build query with placeholders
    placeholders = ",".join(["?" for _ in geo_ids])

    # Try database lookup first
    rows = []
    try:
        rows = await db_query(f"""
            SELECT google_geo_id, country_code, country_name, city_name
            FROM geographies
            WHERE google_geo_id IN ({placeholders})
        """, tuple(geo_ids))
    except Exception:
        # Table may not exist if migration not run
        pass

    # Build result mapping from database
    result = {}
    found_ids = set()

    for row in rows:
        geo_id = str(row['google_geo_id'])
        found_ids.add(geo_id)

        if row['city_name']:
            # City-level: show "City, ST" or just city name
            result[geo_id] = row['city_name']
        elif row['country_name']:
            # Country-level: show ISO-3 code when available
            from utils.country_codes import get_country_alpha3
            result[geo_id] = get_country_alpha3(row['country_code']) if row['country_code'] else row['country_name']
        elif row['country_code']:
            # Fallback to ISO-3 code from country code
            from utils.country_codes import get_country_alpha3
            result[geo_id] = get_country_alpha3(row['country_code'])

    # For any not found in DB, try fallback mapping
    for geo_id in geo_ids:
        if geo_id not in found_ids:
            if geo_id in FALLBACK_GEO_NAMES:
                from utils.country_codes import get_country_alpha3_from_name
                result[geo_id] = get_country_alpha3_from_name(FALLBACK_GEO_NAMES[geo_id])
            else:
                # Return original ID as last resort
                result[geo_id] = geo_id

    return GeoLookupResponse(geos=result)


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
    sizes = await store.get_available_sizes()
    return SizesResponse(sizes=sizes)
