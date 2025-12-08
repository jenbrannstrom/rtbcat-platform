"""FastAPI application for Cat-Scan Creative Intelligence.

This module provides REST API endpoints for managing creatives,
campaigns, and clusters with support for data collection and analysis
using the Google Authorized Buyers RTB API.
"""

import logging
import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

import csv
import io
import tempfile
import os

from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import FileResponse

from qps.importer import validate_csv, import_csv
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from collectors import BuyerSeatsClient, CreativesClient, EndpointsClient, PretargetingClient
from config import ConfigManager
from storage import SQLiteStore, PerformanceMetric, creative_dicts_to_storage
from analytics import WasteAnalyzer
from api.campaigns_router import router as campaigns_router
from services.campaign_aggregation import CampaignAggregationService
from services.waste_analyzer import WasteAnalyzerService

logger = logging.getLogger(__name__)

# Global instances
_store: Optional[SQLiteStore] = None
_config_manager: Optional[ConfigManager] = None


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
    thumbnail_url: Optional[str] = None  # Phase 22: Extracted from HTML snippet


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

    status: Optional[str] = None  # 'success', 'failed', or None if not processed
    error_reason: Optional[str] = None  # 'url_expired', 'no_url', 'timeout', 'network_error', 'invalid_format'
    has_thumbnail: bool = False  # True if thumbnail file exists
    thumbnail_url: Optional[str] = None  # Phase 22: URL for HTML-extracted thumbnails


class WasteFlagsResponse(BaseModel):
    """Response model for waste detection flags."""

    broken_video: bool = False  # thumbnail_status='failed' AND impressions > 0
    zero_engagement: bool = False  # impressions > 1000 AND clicks = 0


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
    # Phase 22: Country data for clustering
    country: Optional[str] = None  # Primary country by spend
    # Preview data based on format
    video: Optional[VideoPreview] = None
    html: Optional[HtmlPreview] = None
    native: Optional[NativePreview] = None
    # Phase 10.4: Thumbnail status and waste detection
    thumbnail_status: Optional[ThumbnailStatusResponse] = None
    waste_flags: Optional[WasteFlagsResponse] = None


class CampaignMetricsResponse(BaseModel):
    """Aggregated metrics for a campaign within a timeframe."""
    total_spend_micros: int = 0
    total_impressions: int = 0
    total_clicks: int = 0
    total_reached_queries: int = 0
    avg_cpm: Optional[float] = None
    avg_ctr: Optional[float] = None
    waste_score: Optional[float] = None  # (reached - imps) / reached * 100


class CampaignWarningsResponse(BaseModel):
    """Warning counts for a campaign."""
    broken_video_count: int = 0
    zero_engagement_count: int = 0
    high_spend_low_performance: int = 0
    disapproved_count: int = 0
    # Phase 22: New problem format warnings
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


class ClusterAssignment(BaseModel):
    """Request model for cluster assignment."""

    creative_id: str
    cluster_id: str


# ============================================================
# Phase 11.4: Pagination Models
# ============================================================

from typing import Generic, TypeVar
T = TypeVar('T')

class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    timeframe_days: Optional[int] = None
    total: int
    returned: int
    limit: int
    offset: int
    has_more: bool


class PaginatedCreativesResponse(BaseModel):
    """Paginated response for creatives list."""
    data: list[CreativeResponse]
    meta: PaginationMeta


class PaginatedCampaignsResponse(BaseModel):
    """Paginated response for campaigns list."""
    data: list[CampaignResponse]
    meta: PaginationMeta


class CollectRequest(BaseModel):
    """Request model for starting a collection job."""

    account_id: str
    filter_query: Optional[str] = None


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


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    version: str
    configured: bool
    has_credentials: bool = False
    database_exists: bool = False


class BuyerSeatResponse(BaseModel):
    """Response model for buyer seat data."""

    buyer_id: str
    bidder_id: str
    display_name: Optional[str] = None
    active: bool = True
    creative_count: int = 0
    last_synced: Optional[str] = None
    created_at: Optional[str] = None


class DiscoverSeatsRequest(BaseModel):
    """Request model for discovering buyer seats."""

    bidder_id: str


class DiscoverSeatsResponse(BaseModel):
    """Response model for seat discovery."""

    status: str
    bidder_id: str
    seats_discovered: int
    seats: list[BuyerSeatResponse]


class SyncSeatResponse(BaseModel):
    """Response model for seat sync operation."""

    status: str
    buyer_id: str
    creatives_synced: int
    message: str


# Waste Analysis response models


class SizeGapResponse(BaseModel):
    """Response model for a size gap in waste analysis."""

    canonical_size: str
    request_count: int
    creative_count: int
    estimated_qps: float
    estimated_waste_pct: float
    recommendation: str
    recommendation_detail: str
    potential_savings_usd: Optional[float] = None
    closest_iab_size: Optional[str] = None


class SizeCoverageResponse(BaseModel):
    """Response model for size coverage data."""

    canonical_size: str
    creative_count: int
    request_count: int
    coverage_status: str
    formats: dict = Field(default_factory=dict)


class WasteReportResponse(BaseModel):
    """Response model for waste analysis report."""

    buyer_id: Optional[str]
    total_requests: int
    total_waste_requests: int
    waste_percentage: float
    size_gaps: list[SizeGapResponse]
    size_coverage: list[SizeCoverageResponse]
    potential_savings_qps: float
    potential_savings_usd: Optional[float]
    analysis_period_days: int
    generated_at: str
    recommendations_summary: dict = Field(default_factory=dict)


class ImportTrafficResponse(BaseModel):
    """Response model for traffic import operation."""

    status: str
    records_imported: int
    message: str


# Performance Metrics models


class PerformanceMetricInput(BaseModel):
    """Input model for importing a single performance metric."""

    creative_id: str
    metric_date: str  # YYYY-MM-DD
    impressions: int = 0
    clicks: int = 0
    spend_micros: int = 0  # USD micros (1M = $1.00)
    campaign_id: Optional[str] = None
    geography: Optional[str] = None  # ISO 3166-1 alpha-2
    device_type: Optional[str] = None  # DESKTOP, MOBILE, TABLET, CTV
    placement: Optional[str] = None


class PerformanceMetricResponse(BaseModel):
    """Response model for a performance metric record."""

    id: Optional[int] = None
    creative_id: str
    campaign_id: Optional[str] = None
    metric_date: str
    impressions: int
    clicks: int
    spend_micros: int
    cpm_micros: Optional[int] = None
    cpc_micros: Optional[int] = None
    geography: Optional[str] = None
    device_type: Optional[str] = None
    placement: Optional[str] = None


class PerformanceSummaryResponse(BaseModel):
    """Response model for aggregated performance summary."""

    total_impressions: Optional[int] = None
    total_clicks: Optional[int] = None
    total_spend_micros: Optional[int] = None
    avg_cpm_micros: Optional[int] = None
    avg_cpc_micros: Optional[int] = None
    ctr_percent: Optional[float] = None
    days_with_data: Optional[int] = None
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None


class ImportPerformanceRequest(BaseModel):
    """Request model for bulk performance import."""

    metrics: list[PerformanceMetricInput]


class ImportPerformanceResponse(BaseModel):
    """Response model for performance import operation."""

    status: str
    records_imported: int
    message: str


class BatchPerformanceRequest(BaseModel):
    """Request model for batch performance lookup."""

    creative_ids: list[str]
    period: str = "7d"  # yesterday, 7d, 30d, all_time


class CreativePerformanceSummary(BaseModel):
    """Performance summary for a single creative (used in batch response)."""

    creative_id: str
    total_impressions: int = 0
    total_clicks: int = 0
    total_spend_micros: int = 0
    avg_cpm_micros: Optional[int] = None
    avg_cpc_micros: Optional[int] = None
    ctr_percent: Optional[float] = None
    days_with_data: int = 0
    has_data: bool = False


class BatchPerformanceResponse(BaseModel):
    """Response model for batch performance lookup."""

    performance: dict[str, CreativePerformanceSummary]
    period: str
    count: int


# Phase 25: Recommendation Engine Response Models
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global _store, _config_manager

    # Initialize on startup
    _config_manager = ConfigManager()
    _store = SQLiteStore()
    await _store.initialize()

    # Auto-populate buyer_seats from existing creatives if needed
    try:
        seats_created = await _store.populate_buyer_seats_from_creatives()
        if seats_created > 0:
            logger.info(f"Auto-populated {seats_created} buyer seats from existing creatives")
    except Exception as e:
        logger.warning(f"Failed to auto-populate buyer seats: {e}")

    logger.info("Cat-Scan API started")

    yield

    # Cleanup on shutdown
    logger.info("Cat-Scan API shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    application = FastAPI(
        title="Cat-Scan Creative Intelligence",
        description="API for collecting and analyzing Authorized Buyers creative data",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return application


app = create_app()

# Include routers
app.include_router(campaigns_router)


def get_store() -> SQLiteStore:
    """Dependency for getting the SQLite store."""
    if _store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return _store


def get_config() -> ConfigManager:
    """Dependency for getting the config manager."""
    if _config_manager is None:
        raise HTTPException(status_code=503, detail="Config not initialized")
    return _config_manager


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(config: ConfigManager = Depends(get_config)):
    """Check API health status including credential and database state."""
    has_credentials = False
    configured = config.is_configured()

    # Check if credentials file exists
    try:
        app_config = config.load()
        if app_config and app_config.authorized_buyers:
            creds_path = Path(app_config.authorized_buyers.service_account_path).expanduser()
            has_credentials = creds_path.exists()
    except Exception:
        pass

    # Check database exists
    db_path = Path.home() / ".catscan" / "catscan.db"

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        configured=configured,
        has_credentials=has_credentials,
        database_exists=db_path.exists(),
    )


@app.get("/thumbnails/{creative_id}.jpg", tags=["System"])
async def get_thumbnail(creative_id: str):
    """Serve locally-generated video thumbnail."""
    thumb_path = Path.home() / ".catscan" / "thumbnails" / f"{creative_id}.jpg"
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb_path, media_type="image/jpeg")


# ============================================================
# Thumbnail Generation API (Phase 18)
# ============================================================

import subprocess
import shutil


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


def _get_thumbnails_dir() -> Path:
    """Get the thumbnails directory, creating if needed."""
    thumb_dir = Path.home() / ".catscan" / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return thumb_dir


def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    # Check PATH first
    if shutil.which("ffmpeg") is not None:
        return True
    # Check common system paths (venv may not include /usr/bin in PATH)
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return True
    return False


def _get_ffmpeg_path() -> str:
    """Get the ffmpeg executable path."""
    # Check PATH first
    path = shutil.which("ffmpeg")
    if path:
        return path
    # Check common system paths
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return "ffmpeg"  # Fallback, will fail if not found


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
            "-ss", "1",  # Seek to 1 second (before -i for fast seek)
            "-t", "2",   # Only read 2 seconds of video
            "-rw_timeout", "5000000",  # 5 second network timeout (microseconds)
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


@app.get("/thumbnails/status", response_model=ThumbnailStatusSummary, tags=["Thumbnails"])
async def get_thumbnail_status(store: SQLiteStore = Depends(get_store)):
    """Get summary of thumbnail generation status."""
    import sqlite3

    db_path = Path.home() / ".catscan" / "catscan.db"
    ffmpeg_available = _check_ffmpeg()

    if not db_path.exists():
        return ThumbnailStatusSummary(
            total_videos=0,
            with_thumbnails=0,
            pending=0,
            failed=0,
            coverage_percent=0.0,
            ffmpeg_available=ffmpeg_available,
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Count total videos
    cursor.execute("SELECT COUNT(*) FROM creatives WHERE format = 'VIDEO'")
    total_videos = cursor.fetchone()[0]

    # Count by thumbnail status
    cursor.execute("""
        SELECT
            COALESCE(ts.status, 'pending') as status,
            COUNT(*) as count
        FROM creatives c
        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
        WHERE c.format = 'VIDEO'
        GROUP BY COALESCE(ts.status, 'pending')
    """)

    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
    conn.close()

    with_thumbnails = status_counts.get('success', 0)
    failed = status_counts.get('failed', 0)
    pending = total_videos - with_thumbnails - failed

    coverage = (with_thumbnails / total_videos * 100) if total_videos > 0 else 0.0

    return ThumbnailStatusSummary(
        total_videos=total_videos,
        with_thumbnails=with_thumbnails,
        pending=pending,
        failed=failed,
        coverage_percent=round(coverage, 1),
        ffmpeg_available=ffmpeg_available,
    )


# ============================================================
# System Status API (Phase 19)
# ============================================================

import sys


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


@app.get("/system/status", response_model=SystemStatusResponse, tags=["System"])
async def get_system_status():
    """Get system status including installed tools and resource usage."""

    # Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # Node.js check
    node_available = shutil.which("node") is not None
    node_version = None
    if node_available:
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
            node_version = result.stdout.strip()
        except Exception:
            pass

    # ffmpeg check
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

    # Database size
    db_path = Path.home() / ".catscan" / "catscan.db"
    database_size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0

    # Thumbnails count
    thumbnails_dir = Path.home() / ".catscan" / "thumbnails"
    thumbnails_count = len(list(thumbnails_dir.glob("*.jpg"))) if thumbnails_dir.exists() else 0

    # Disk space
    total, used, free = shutil.disk_usage(Path.home())
    disk_space_gb = free / (1024 ** 3)

    # Creative counts
    creatives_count = 0
    videos_count = 0
    if db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM creatives")
            creatives_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM creatives WHERE format = 'VIDEO'")
            videos_count = cursor.fetchone()[0]
            conn.close()
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


@app.post("/thumbnails/generate", response_model=ThumbnailGenerateResponse, tags=["Thumbnails"])
async def generate_single_thumbnail(
    request: ThumbnailGenerateRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Generate thumbnail for a single video creative."""
    import sqlite3
    import json

    if not _check_ffmpeg():
        raise HTTPException(status_code=503, detail="ffmpeg not installed on server")

    db_path = Path.home() / ".catscan" / "catscan.db"
    thumb_dir = _get_thumbnails_dir()

    # Get the creative
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, format, raw_data
        FROM creatives
        WHERE id = ?
    """, (request.creative_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Creative not found")

    if row['format'] != 'VIDEO':
        conn.close()
        return ThumbnailGenerateResponse(
            creative_id=request.creative_id,
            status='skipped',
            error_reason='not_video',
        )

    # Extract video URL from raw_data
    raw_data = json.loads(row['raw_data']) if row['raw_data'] else {}
    video_data = raw_data.get('video', {})
    video_url = video_data.get('videoUrl')

    # Try to extract from VAST if no direct URL
    if not video_url and video_data.get('vastXml'):
        video_url = _extract_video_url_from_vast(video_data['vastXml'])

    if not video_url:
        # Record status
        cursor.execute("""
            INSERT INTO thumbnail_status (creative_id, status, error_reason, attempted_at)
            VALUES (?, 'failed', 'no_url', CURRENT_TIMESTAMP)
            ON CONFLICT(creative_id) DO UPDATE SET
                status = 'failed',
                error_reason = 'no_url',
                attempted_at = CURRENT_TIMESTAMP
        """, (request.creative_id,))
        conn.commit()
        conn.close()

        return ThumbnailGenerateResponse(
            creative_id=request.creative_id,
            status='failed',
            error_reason='no_video_url',
        )

    # Generate thumbnail
    thumb_path = thumb_dir / f"{request.creative_id}.jpg"
    result = _generate_thumbnail_ffmpeg(video_url, thumb_path)

    if result['success']:
        # Update raw_data with local thumbnail path
        video_data['localThumbnailPath'] = str(thumb_path)
        raw_data['video'] = video_data
        cursor.execute(
            "UPDATE creatives SET raw_data = ? WHERE id = ?",
            (json.dumps(raw_data), request.creative_id)
        )

        # Record success status
        cursor.execute("""
            INSERT INTO thumbnail_status (creative_id, status, video_url, attempted_at)
            VALUES (?, 'success', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(creative_id) DO UPDATE SET
                status = 'success',
                error_reason = NULL,
                video_url = excluded.video_url,
                attempted_at = CURRENT_TIMESTAMP
        """, (request.creative_id, video_url))

        conn.commit()
        conn.close()

        return ThumbnailGenerateResponse(
            creative_id=request.creative_id,
            status='success',
            thumbnail_url=f"/thumbnails/{request.creative_id}.jpg",
        )
    else:
        # Record failure
        cursor.execute("""
            INSERT INTO thumbnail_status (creative_id, status, error_reason, video_url, attempted_at)
            VALUES (?, 'failed', ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(creative_id) DO UPDATE SET
                status = 'failed',
                error_reason = excluded.error_reason,
                video_url = excluded.video_url,
                attempted_at = CURRENT_TIMESTAMP
        """, (request.creative_id, result['error_reason'], video_url))
        conn.commit()
        conn.close()

        return ThumbnailGenerateResponse(
            creative_id=request.creative_id,
            status='failed',
            error_reason=result['error_reason'],
        )


@app.post("/thumbnails/generate-batch", response_model=ThumbnailBatchResponse, tags=["Thumbnails"])
async def generate_batch_thumbnails(
    request: ThumbnailBatchRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Generate thumbnails for multiple video creatives.

    Processes videos that don't have thumbnails yet (or failed ones if force=True).
    """
    import sqlite3
    import json

    if not _check_ffmpeg():
        raise HTTPException(status_code=503, detail="ffmpeg not installed on server")

    db_path = Path.home() / ".catscan" / "catscan.db"
    thumb_dir = _get_thumbnails_dir()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query for videos needing thumbnails
    if request.force:
        # Include failed ones when force=True
        query = """
            SELECT c.id, c.raw_data
            FROM creatives c
            LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
            WHERE c.format = 'VIDEO'
            AND (ts.status IS NULL OR ts.status = 'failed')
        """
    else:
        # Only get pending (no status record)
        query = """
            SELECT c.id, c.raw_data
            FROM creatives c
            LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
            WHERE c.format = 'VIDEO'
            AND ts.status IS NULL
        """

    # Add seat filter if specified
    if request.seat_id:
        query += " AND c.buyer_id = ?"
        cursor.execute(query + f" LIMIT {request.limit}", (request.seat_id,))
    else:
        cursor.execute(query + f" LIMIT {request.limit}")

    rows = cursor.fetchall()

    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for row in rows:
        creative_id = row['id']
        raw_data = json.loads(row['raw_data']) if row['raw_data'] else {}
        video_data = raw_data.get('video', {})
        video_url = video_data.get('videoUrl')

        # Try VAST extraction
        if not video_url and video_data.get('vastXml'):
            video_url = _extract_video_url_from_vast(video_data['vastXml'])

        if not video_url:
            # Record no URL
            cursor.execute("""
                INSERT INTO thumbnail_status (creative_id, status, error_reason, attempted_at)
                VALUES (?, 'failed', 'no_url', CURRENT_TIMESTAMP)
                ON CONFLICT(creative_id) DO UPDATE SET
                    status = 'failed', error_reason = 'no_url', attempted_at = CURRENT_TIMESTAMP
            """, (creative_id,))

            results.append(ThumbnailGenerateResponse(
                creative_id=creative_id,
                status='failed',
                error_reason='no_video_url',
            ))
            failed_count += 1
            continue

        # Generate thumbnail
        thumb_path = thumb_dir / f"{creative_id}.jpg"
        result = _generate_thumbnail_ffmpeg(video_url, thumb_path)

        if result['success']:
            # Update raw_data
            video_data['localThumbnailPath'] = str(thumb_path)
            raw_data['video'] = video_data
            cursor.execute(
                "UPDATE creatives SET raw_data = ? WHERE id = ?",
                (json.dumps(raw_data), creative_id)
            )

            cursor.execute("""
                INSERT INTO thumbnail_status (creative_id, status, video_url, attempted_at)
                VALUES (?, 'success', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(creative_id) DO UPDATE SET
                    status = 'success', error_reason = NULL, video_url = excluded.video_url,
                    attempted_at = CURRENT_TIMESTAMP
            """, (creative_id, video_url))

            results.append(ThumbnailGenerateResponse(
                creative_id=creative_id,
                status='success',
                thumbnail_url=f"/thumbnails/{creative_id}.jpg",
            ))
            success_count += 1
        else:
            cursor.execute("""
                INSERT INTO thumbnail_status (creative_id, status, error_reason, video_url, attempted_at)
                VALUES (?, 'failed', ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(creative_id) DO UPDATE SET
                    status = 'failed', error_reason = excluded.error_reason,
                    video_url = excluded.video_url, attempted_at = CURRENT_TIMESTAMP
            """, (creative_id, result['error_reason'], video_url))

            results.append(ThumbnailGenerateResponse(
                creative_id=creative_id,
                status='failed',
                error_reason=result['error_reason'],
            ))
            failed_count += 1

    conn.commit()
    conn.close()

    return ThumbnailBatchResponse(
        status='completed',
        total_processed=len(rows),
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        results=results,
    )


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


@app.post("/thumbnails/extract-html", response_model=HTMLThumbnailResponse, tags=["Thumbnails"])
async def extract_html_thumbnails(
    request: HTMLThumbnailRequest = HTMLThumbnailRequest(),
    store: SQLiteStore = Depends(get_store),
):
    """Extract thumbnail URLs from HTML creatives.

    Phase 22: HTML thumbnail extraction.

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


class CredentialsUploadRequest(BaseModel):
    """Request model for uploading service account credentials."""

    service_account_json: str = Field(..., description="JSON string of service account key file")
    account_id: Optional[str] = Field(None, description="Optional bidder account ID override")


class CredentialsUploadResponse(BaseModel):
    """Response model for credentials upload."""

    success: bool
    client_email: Optional[str] = None
    project_id: Optional[str] = None
    message: str


class CredentialsStatusResponse(BaseModel):
    """Response model for credentials status."""

    configured: bool
    client_email: Optional[str] = None
    project_id: Optional[str] = None
    credentials_path: Optional[str] = None
    account_id: Optional[str] = None


@app.get("/config/credentials", response_model=CredentialsStatusResponse, tags=["Configuration"])
async def get_credentials_status(config: ConfigManager = Depends(get_config)):
    """Get current credentials configuration status."""
    import json
    from pathlib import Path

    if not config.is_configured():
        return CredentialsStatusResponse(
            configured=False,
            message="No credentials configured",
        )

    try:
        app_config = config.get_config()
        if not app_config.authorized_buyers:
            return CredentialsStatusResponse(configured=False)

        creds_path = Path(app_config.authorized_buyers.service_account_path).expanduser()

        if not creds_path.exists():
            return CredentialsStatusResponse(
                configured=False,
                credentials_path=str(creds_path),
            )

        # Read the credentials file to get client_email
        with open(creds_path) as f:
            creds_data = json.load(f)

        return CredentialsStatusResponse(
            configured=True,
            client_email=creds_data.get("client_email"),
            project_id=creds_data.get("project_id"),
            credentials_path=str(creds_path),
            account_id=app_config.authorized_buyers.account_id,
        )
    except Exception as e:
        logger.error(f"Error reading credentials: {e}")
        return CredentialsStatusResponse(configured=False)


@app.post("/config/credentials", response_model=CredentialsUploadResponse, tags=["Configuration"])
async def upload_credentials(
    request: CredentialsUploadRequest,
    config: ConfigManager = Depends(get_config),
):
    """Upload Google service account credentials.

    Accepts the JSON contents of a Google Cloud service account key file,
    validates it, saves it securely, and updates the configuration.
    """
    import json
    from pathlib import Path
    from config.config_manager import AuthorizedBuyersConfig, AppConfig

    # Parse and validate JSON
    try:
        creds_data = json.loads(request.service_account_json)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {str(e)}",
        )

    # Validate required fields
    required_fields = ["type", "client_email", "private_key", "project_id"]
    missing = [f for f in required_fields if f not in creds_data]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing)}. This doesn't appear to be a valid service account key.",
        )

    if creds_data.get("type") != "service_account":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid credential type: '{creds_data.get('type')}'. Expected 'service_account'.",
        )

    # Create credentials directory
    creds_dir = Path.home() / ".catscan" / "credentials"
    creds_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(creds_dir, 0o700)

    # Save credentials file
    creds_path = creds_dir / "google-credentials.json"
    with open(creds_path, "w") as f:
        json.dump(creds_data, f, indent=2)
    os.chmod(creds_path, 0o600)

    # Determine account_id - use provided or extract from client_email
    account_id = request.account_id
    if not account_id:
        # Try to extract from client_email (format: name@project.iam.gserviceaccount.com)
        client_email = creds_data.get("client_email", "")
        # Default to empty, user will need to set it via discover seats
        account_id = ""

    # Update configuration
    try:
        try:
            app_config = config.get_config()
        except Exception:
            # No existing config, create new one
            app_config = AppConfig()

        app_config.authorized_buyers = AuthorizedBuyersConfig(
            service_account_path=str(creds_path),
            account_id=account_id,
        )
        config.save(app_config)

        logger.info(f"Credentials uploaded successfully for {creds_data.get('client_email')}")

        return CredentialsUploadResponse(
            success=True,
            client_email=creds_data.get("client_email"),
            project_id=creds_data.get("project_id"),
            message="Credentials saved successfully",
        )

    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save configuration: {str(e)}",
        )


@app.delete("/config/credentials", tags=["Configuration"])
async def delete_credentials(config: ConfigManager = Depends(get_config)):
    """Remove stored credentials and reset configuration."""
    from pathlib import Path

    try:
        # Remove credentials file
        creds_path = Path.home() / ".catscan" / "credentials" / "google-credentials.json"
        if creds_path.exists():
            creds_path.unlink()

        # Reset configuration
        config.reset()

        return {"success": True, "message": "Credentials removed"}

    except Exception as e:
        logger.error(f"Failed to delete credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete credentials: {str(e)}",
        )


@app.get("/stats", response_model=StatsResponse, tags=["System"])
async def get_stats(store: SQLiteStore = Depends(get_store)):
    """Get database statistics."""
    stats = await store.get_stats()
    return StatsResponse(**stats)


@app.get("/sizes", response_model=SizesResponse, tags=["System"])
async def get_sizes(store: SQLiteStore = Depends(get_store)):
    """Get available creative sizes from the database."""
    sizes = await store.get_available_sizes()
    return SizesResponse(sizes=sizes)


def _extract_video_url_from_vast(vast_xml: str) -> str | None:
    """Extract video URL from VAST XML."""
    if not vast_xml:
        return None
    import re
    match = re.search(r'<MediaFile[^>]*>(?:<!\[CDATA\[)?(https?://[^\]<]+)', vast_xml)
    return match.group(1).strip() if match else None


def _extract_thumbnail_from_vast(vast_xml: str) -> str | None:
    """Extract thumbnail URL from VAST XML CompanionAds.

    Looks for StaticResource images in CompanionAds section.
    """
    if not vast_xml:
        return None
    import re

    # Look for StaticResource with image type in CompanionAds
    # Pattern: <StaticResource creativeType="image/..."><![CDATA[URL]]></StaticResource>
    patterns = [
        # StaticResource with CDATA
        r'<StaticResource[^>]*creativeType="image/[^"]*"[^>]*><!\[CDATA\[(https?://[^\]]+)\]\]></StaticResource>',
        # StaticResource without CDATA
        r'<StaticResource[^>]*creativeType="image/[^"]*"[^>]*>(https?://[^<]+)</StaticResource>',
        # Any image URL in CompanionAds section (fallback)
        r'<Companion[^>]*>.*?<StaticResource[^>]*><!\[CDATA\[(https?://[^\]]+\.(?:jpg|jpeg|png|gif))\]\]>',
    ]

    for pattern in patterns:
        match = re.search(pattern, vast_xml, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

    return None


def _extract_preview_data(creative, slim: bool = False, html_thumbnail_url: Optional[str] = None) -> dict:
    """Extract preview data from creative raw_data based on format.

    Args:
        creative: The creative object
        slim: If True, exclude large fields (vast_xml, html snippet) for list views
        html_thumbnail_url: Optional thumbnail URL for HTML creatives (from thumbnail_status)
    """
    raw_data = creative.raw_data or {}
    result = {"video": None, "html": None, "native": None}

    if creative.format == "VIDEO":
        video_data = raw_data.get("video")
        if video_data:
            vast_xml = video_data.get("vastXml")
            video_url = video_data.get("videoUrl")
            # Pre-extract video URL from VAST if not already present
            if not video_url and vast_xml:
                video_url = _extract_video_url_from_vast(vast_xml)
            # Check for local thumbnail first (generated by CLI), then VAST
            local_thumb_path = video_data.get("localThumbnailPath")
            if local_thumb_path and os.path.exists(local_thumb_path):
                # Serve via API endpoint
                thumbnail_url = f"/thumbnails/{creative.id}.jpg"
            else:
                # Fall back to extracting from VAST CompanionAds
                thumbnail_url = _extract_thumbnail_from_vast(vast_xml) if vast_xml else None
            result["video"] = VideoPreview(
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                vast_xml=None if slim else vast_xml,  # Exclude in slim mode
                duration=video_data.get("duration"),
            )

    elif creative.format == "HTML":
        html_data = raw_data.get("html")
        if html_data:
            result["html"] = HtmlPreview(
                snippet=None if slim else html_data.get("snippet"),  # Exclude in slim mode
                width=html_data.get("width"),
                height=html_data.get("height"),
                thumbnail_url=html_thumbnail_url,  # Phase 22: From thumbnail_status
            )

    elif creative.format == "NATIVE":
        native_data = raw_data.get("native")
        if native_data:
            image_data = native_data.get("image")
            logo_data = native_data.get("logo")
            result["native"] = NativePreview(
                headline=native_data.get("headline"),
                body=native_data.get("body"),
                call_to_action=native_data.get("callToAction"),
                click_link_url=native_data.get("clickLinkUrl"),
                image=ImagePreview(**image_data) if image_data else None,
                logo=ImagePreview(**logo_data) if logo_data else None,
            )

    return result


async def _get_thumbnail_status_for_creatives(
    store: SQLiteStore, creative_ids: list[str]
) -> dict[str, ThumbnailStatusResponse]:
    """Get thumbnail status for multiple creatives.

    Returns a dict mapping creative_id to ThumbnailStatusResponse.
    """
    if not creative_ids:
        return {}

    statuses = await store.get_thumbnail_statuses(creative_ids)
    thumbnails_dir = Path.home() / ".catscan" / "thumbnails"

    result = {}
    for cid in creative_ids:
        status_data = statuses.get(cid)
        has_thumbnail = (thumbnails_dir / f"{cid}.jpg").exists()

        if status_data:
            result[cid] = ThumbnailStatusResponse(
                status=status_data["status"],
                error_reason=status_data["error_reason"],
                has_thumbnail=has_thumbnail,
                thumbnail_url=status_data.get("thumbnail_url"),  # Phase 22: HTML thumbnails
            )
        else:
            result[cid] = ThumbnailStatusResponse(
                status=None,
                error_reason=None,
                has_thumbnail=has_thumbnail,
                thumbnail_url=None,
            )

    return result


async def _get_waste_flags_for_creatives(
    store: SQLiteStore,
    creative_ids: list[str],
    thumbnail_statuses: dict[str, ThumbnailStatusResponse],
    days: int = 7,
) -> dict[str, WasteFlagsResponse]:
    """Compute waste flags for multiple creatives.

    Args:
        store: Database store
        creative_ids: List of creative IDs
        thumbnail_statuses: Pre-fetched thumbnail status data
        days: Timeframe for performance data (default 7 days)

    Returns:
        Dict mapping creative_id to WasteFlagsResponse
    """
    if not creative_ids:
        return {}

    # Get performance data for all creatives in timeframe
    # We need to query the rtb_daily table for impressions/clicks
    perf_data = {}
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _get_perf():
                placeholders = ",".join("?" * len(creative_ids))
                cursor = conn.execute(
                    f"""
                    SELECT creative_id,
                           SUM(impressions) as total_impressions,
                           SUM(clicks) as total_clicks
                    FROM rtb_daily
                    WHERE creative_id IN ({placeholders})
                      AND metric_date >= date('now', '-{days} days')
                    GROUP BY creative_id
                    """,
                    creative_ids,
                )
                return {row["creative_id"]: {"impressions": row["total_impressions"], "clicks": row["total_clicks"]}
                        for row in cursor.fetchall()}

            perf_data = await loop.run_in_executor(None, _get_perf)
    except Exception as e:
        # rtb_daily table may not exist yet (no performance data imported)
        logger.debug(f"Could not fetch performance data: {e}")

    result = {}
    for cid in creative_ids:
        ts = thumbnail_statuses.get(cid)
        perf = perf_data.get(cid, {"impressions": 0, "clicks": 0})
        impressions = perf["impressions"] or 0
        clicks = perf["clicks"] or 0

        # broken_video: thumbnail failed AND has impressions (wasting money on broken video)
        broken_video = (
            ts is not None
            and ts.status == "failed"
            and impressions > 0
        )

        # zero_engagement: high impressions but no clicks (poor creative performance)
        zero_engagement = impressions > 1000 and clicks == 0

        result[cid] = WasteFlagsResponse(
            broken_video=broken_video,
            zero_engagement=zero_engagement,
        )

    return result


async def _get_primary_countries_for_creatives(
    store: SQLiteStore,
    creative_ids: list[str],
    days: int = 7,
) -> dict[str, str]:
    """Get the primary country (by spend) for each creative.

    Args:
        store: Database store
        creative_ids: List of creative IDs
        days: Timeframe for performance data (default 7 days)

    Returns:
        Dict mapping creative_id to country code
    """
    if not creative_ids:
        return {}

    result = {}
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _get_countries():
                placeholders = ",".join("?" * len(creative_ids))
                # Get the country with highest spend for each creative
                cursor = conn.execute(
                    f"""
                    WITH ranked AS (
                        SELECT creative_id, geography,
                               SUM(spend_micros) as total_spend,
                               ROW_NUMBER() OVER (
                                   PARTITION BY creative_id
                                   ORDER BY SUM(spend_micros) DESC
                               ) as rn
                        FROM performance_metrics
                        WHERE creative_id IN ({placeholders})
                          AND geography IS NOT NULL
                          AND metric_date >= date('now', '-{days} days')
                        GROUP BY creative_id, geography
                    )
                    SELECT creative_id, geography
                    FROM ranked
                    WHERE rn = 1
                    """,
                    creative_ids,
                )
                return {row["creative_id"]: row["geography"] for row in cursor.fetchall()}

            result = await loop.run_in_executor(None, _get_countries)
    except Exception as e:
        # performance_metrics table may not exist or have geography data
        logger.debug(f"Could not fetch country data: {e}")

    return result


@app.get("/creatives", response_model=list[CreativeResponse], tags=["Creatives"])
async def list_creatives(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    format: Optional[str] = Query(None, description="Filter by creative format"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    slim: bool = Query(True, description="Exclude large fields (vast_xml, html snippets) for faster loading"),
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection (default 7 days)"),
    active_only: bool = Query(False, description="Only return creatives with activity (impressions/clicks/spend) in timeframe"),
    store: SQLiteStore = Depends(get_store),
):
    """List creatives with optional filtering.

    Phase 11.1: Decision Context Foundation
    - By default, slim=True excludes large fields like vast_xml and html snippets
    - Set active_only=True to hide creatives with zero activity in the timeframe
    - Includes thumbnail_status and waste_flags for each creative
    """
    creatives = await store.list_creatives(
        campaign_id=campaign_id,
        cluster_id=cluster_id,
        buyer_id=buyer_id,
        format=format,
        limit=limit if not active_only else limit * 3,  # Fetch more if filtering
        offset=offset,
    )

    # If active_only, filter to creatives with activity in timeframe
    if active_only and creatives:
        creative_ids = [c.id for c in creatives]
        try:
            async with store._connection() as conn:
                import asyncio
                loop = asyncio.get_event_loop()

                def _get_active_ids():
                    placeholders = ",".join("?" * len(creative_ids))
                    cursor = conn.execute(
                        f"""
                        SELECT DISTINCT creative_id
                        FROM rtb_daily
                        WHERE creative_id IN ({placeholders})
                          AND metric_date >= date('now', '-{days} days')
                          AND (impressions > 0 OR clicks > 0 OR spend_micros > 0)
                        """,
                        creative_ids,
                    )
                    return set(row["creative_id"] for row in cursor.fetchall())

                active_ids = await loop.run_in_executor(None, _get_active_ids)
                creatives = [c for c in creatives if c.id in active_ids][:limit]
        except Exception as e:
            # rtb_daily table may not exist - return all creatives
            logger.debug(f"Could not filter active creatives: {e}")

    # Get thumbnail status, waste flags, and country data for all creatives
    creative_ids = [c.id for c in creatives]
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, creative_ids)
    waste_flags = await _get_waste_flags_for_creatives(store, creative_ids, thumbnail_statuses, days)
    country_data = await _get_primary_countries_for_creatives(store, creative_ids, days)

    return [
        CreativeResponse(
            id=c.id,
            name=c.name,
            format=c.format,
            account_id=c.account_id,
            buyer_id=c.buyer_id,
            approval_status=c.approval_status,
            width=c.width,
            height=c.height,
            final_url=c.final_url,
            display_url=c.display_url,
            utm_source=c.utm_source,
            utm_medium=c.utm_medium,
            utm_campaign=c.utm_campaign,
            utm_content=c.utm_content,
            utm_term=c.utm_term,
            advertiser_name=c.advertiser_name,
            campaign_id=c.campaign_id,
            cluster_id=c.cluster_id,
            seat_name=c.seat_name,
            country=country_data.get(c.id),
            thumbnail_status=thumbnail_statuses.get(c.id),
            waste_flags=waste_flags.get(c.id),
            **_extract_preview_data(
                c,
                slim=slim,
                html_thumbnail_url=thumbnail_statuses.get(c.id).thumbnail_url if thumbnail_statuses.get(c.id) else None
            ),
        )
        for c in creatives
    ]


@app.get("/creatives/v2", response_model=PaginatedCreativesResponse, tags=["Creatives"])
async def list_creatives_paginated(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    format: Optional[str] = Query(None, description="Filter by creative format"),
    limit: int = Query(50, ge=1, le=200, description="Page size (max 200)"),
    offset: int = Query(0, ge=0, description="Results offset"),
    slim: bool = Query(True, description="Exclude large fields for faster loading"),
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection"),
    active_only: bool = Query(False, description="Only return creatives with activity in timeframe"),
    store: SQLiteStore = Depends(get_store),
):
    """List creatives with pagination metadata.

    Phase 11.4: Scale Readiness
    Returns paginated results with metadata for large accounts.
    """
    # Get total count for pagination
    async with store._connection() as conn:
        import asyncio
        loop = asyncio.get_event_loop()

        def _count():
            cursor = conn.execute("SELECT COUNT(*) FROM creatives")
            return cursor.fetchone()[0]

        total = await loop.run_in_executor(None, _count)

    # Fetch creatives
    creatives = await store.list_creatives(
        campaign_id=campaign_id,
        cluster_id=cluster_id,
        buyer_id=buyer_id,
        format=format,
        limit=limit if not active_only else limit * 3,
        offset=offset,
    )

    # Filter by activity if requested
    if active_only and creatives:
        creative_ids = [c.id for c in creatives]
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _get_active_ids():
                placeholders = ",".join("?" * len(creative_ids))
                cursor = conn.execute(
                    f"""
                    SELECT DISTINCT creative_id
                    FROM rtb_daily
                    WHERE creative_id IN ({placeholders})
                      AND metric_date >= date('now', '-{days} days')
                      AND (impressions > 0 OR clicks > 0 OR spend_micros > 0)
                    """,
                    creative_ids,
                )
                return set(row["creative_id"] for row in cursor.fetchall())

            active_ids = await loop.run_in_executor(None, _get_active_ids)
            creatives = [c for c in creatives if c.id in active_ids][:limit]

    # Get thumbnail status, waste flags, and country data
    creative_ids = [c.id for c in creatives]
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, creative_ids)
    waste_flags = await _get_waste_flags_for_creatives(store, creative_ids, thumbnail_statuses, days)
    country_data = await _get_primary_countries_for_creatives(store, creative_ids, days)

    data = [
        CreativeResponse(
            id=c.id,
            name=c.name,
            format=c.format,
            account_id=c.account_id,
            buyer_id=c.buyer_id,
            approval_status=c.approval_status,
            width=c.width,
            height=c.height,
            final_url=c.final_url,
            display_url=c.display_url,
            utm_source=c.utm_source,
            utm_medium=c.utm_medium,
            utm_campaign=c.utm_campaign,
            utm_content=c.utm_content,
            utm_term=c.utm_term,
            advertiser_name=c.advertiser_name,
            campaign_id=c.campaign_id,
            cluster_id=c.cluster_id,
            seat_name=c.seat_name,
            country=country_data.get(c.id),
            thumbnail_status=thumbnail_statuses.get(c.id),
            waste_flags=waste_flags.get(c.id),
            **_extract_preview_data(
                c,
                slim=slim,
                html_thumbnail_url=thumbnail_statuses.get(c.id).thumbnail_url if thumbnail_statuses.get(c.id) else None
            ),
        )
        for c in creatives
    ]

    return PaginatedCreativesResponse(
        data=data,
        meta=PaginationMeta(
            timeframe_days=days,
            total=total,
            returned=len(data),
            limit=limit,
            offset=offset,
            has_more=offset + len(data) < total,
        ),
    )


class NewlyUploadedCreativesResponse(BaseModel):
    """Response model for newly uploaded creatives."""

    creatives: list[dict]
    total_count: int
    period_start: str
    period_end: str


@app.get("/creatives/newly-uploaded", response_model=NewlyUploadedCreativesResponse, tags=["Creatives"])
async def get_newly_uploaded_creatives(
    days: int = Query(7, description="Number of days to look back", ge=1, le=90),
    limit: int = Query(100, description="Maximum number of creatives to return", ge=1, le=1000),
    format: Optional[str] = Query(None, description="Filter by format (HTML, VIDEO, NATIVE)"),
    store: SQLiteStore = Depends(get_store),
):
    """Get creatives that were first seen within the specified time period.

    Returns creatives that appeared for the first time in imports during the specified period.
    This is useful for identifying new creatives added to the account.
    """
    try:
        from datetime import datetime, timedelta

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days)

        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            # Build query
            query = """
                SELECT c.*,
                    (SELECT SUM(spend_micros) FROM rtb_daily WHERE creative_id = c.id) as total_spend_micros,
                    (SELECT SUM(impressions) FROM rtb_daily WHERE creative_id = c.id) as total_impressions
                FROM creatives c
                WHERE c.first_seen_at >= ?
                AND c.first_seen_at <= ?
            """
            params = [period_start.isoformat(), period_end.isoformat()]

            if format:
                query += " AND c.format = ?"
                params.append(format.upper())

            query += " ORDER BY c.first_seen_at DESC LIMIT ?"
            params.append(limit)

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(query, params).fetchall(),
            )

            # Get total count
            count_query = """
                SELECT COUNT(*) FROM creatives c
                WHERE c.first_seen_at >= ?
                AND c.first_seen_at <= ?
            """
            count_params = [period_start.isoformat(), period_end.isoformat()]
            if format:
                count_query += " AND c.format = ?"
                count_params.append(format.upper())

            total_count = await loop.run_in_executor(
                None,
                lambda: conn.execute(count_query, count_params).fetchone()[0],
            )

        creatives = []
        for row in rows:
            creative = {
                "id": row["id"],
                "name": row["name"],
                "format": row["format"],
                "approval_status": row["approval_status"],
                "width": row["width"],
                "height": row["height"],
                "canonical_size": row["canonical_size"],
                "final_url": row["final_url"],
                "first_seen_at": row["first_seen_at"],
                "first_import_batch_id": row["first_import_batch_id"],
                "total_spend_usd": (row["total_spend_micros"] or 0) / 1_000_000,
                "total_impressions": row["total_impressions"] or 0,
            }
            creatives.append(creative)

        return NewlyUploadedCreativesResponse(
            creatives=creatives,
            total_count=total_count or 0,
            period_start=period_start.strftime("%Y-%m-%d"),
            period_end=period_end.strftime("%Y-%m-%d"),
        )

    except Exception as e:
        logger.error(f"Failed to get newly uploaded creatives: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get newly uploaded creatives: {str(e)}")


@app.get("/creatives/{creative_id}", response_model=CreativeResponse, tags=["Creatives"])
async def get_creative(
    creative_id: str,
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection (default 7 days)"),
    store: SQLiteStore = Depends(get_store),
):
    """Get a specific creative by ID.

    Includes thumbnail_status and waste_flags.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    # Get thumbnail status and waste flags
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, [creative_id])
    waste_flags = await _get_waste_flags_for_creatives(store, [creative_id], thumbnail_statuses, days)

    return CreativeResponse(
        id=creative.id,
        name=creative.name,
        format=creative.format,
        account_id=creative.account_id,
        buyer_id=creative.buyer_id,
        approval_status=creative.approval_status,
        width=creative.width,
        height=creative.height,
        final_url=creative.final_url,
        display_url=creative.display_url,
        utm_source=creative.utm_source,
        utm_medium=creative.utm_medium,
        utm_campaign=creative.utm_campaign,
        utm_content=creative.utm_content,
        utm_term=creative.utm_term,
        advertiser_name=creative.advertiser_name,
        campaign_id=creative.campaign_id,
        cluster_id=creative.cluster_id,
        seat_name=creative.seat_name,
        thumbnail_status=thumbnail_statuses.get(creative_id),
        waste_flags=waste_flags.get(creative_id),
        **_extract_preview_data(
            creative,
            html_thumbnail_url=thumbnail_statuses.get(creative_id).thumbnail_url if thumbnail_statuses.get(creative_id) else None
        ),
    )


@app.delete("/creatives/{creative_id}", tags=["Creatives"])
async def delete_creative(
    creative_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Delete a creative by ID."""
    deleted = await store.delete_creative(creative_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Creative not found")
    return {"status": "deleted", "id": creative_id}


@app.post("/creatives/cluster", tags=["Creatives"])
async def assign_cluster(
    assignment: ClusterAssignment,
    store: SQLiteStore = Depends(get_store),
):
    """Assign a creative to a cluster."""
    await store.update_creative_cluster(
        assignment.creative_id,
        assignment.cluster_id,
    )
    return {"status": "updated", "creative_id": assignment.creative_id}


@app.delete("/creatives/{creative_id}/campaign", tags=["Creatives"])
async def remove_from_campaign(
    creative_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Remove a creative from its campaign."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    await store.update_creative_campaign(creative_id, None)
    return {"status": "removed", "creative_id": creative_id}


@app.get("/campaigns", response_model=list[CampaignResponse], tags=["Campaigns"])
async def list_campaigns(
    days: int = Query(7, ge=1, le=365, description="Timeframe for metrics aggregation (default 7 days)"),
    include_metrics: bool = Query(True, description="Include performance metrics and warnings"),
    include_empty: bool = Query(True, description="Include campaigns with no activity in timeframe"),
    store: SQLiteStore = Depends(get_store),
):
    """List all campaigns with aggregated metrics for the given timeframe.

    Phase 11.1: Decision Context Foundation
    - Returns aggregated spend, impressions, clicks, waste_score
    - Includes warning counts (broken videos, zero engagement, etc.)
    - Filters by timeframe to show relevant data
    """
    if include_metrics:
        # Use aggregation service for metrics
        service = CampaignAggregationService()
        campaigns = service.get_campaigns_with_metrics(days=days, include_empty=include_empty)
        return [
            CampaignResponse(
                id=c.id,
                name=c.name,
                creative_ids=c.creative_ids,
                creative_count=c.creative_count,
                timeframe_days=c.timeframe_days,
                metrics=CampaignMetricsResponse(
                    total_spend_micros=c.metrics.total_spend_micros,
                    total_impressions=c.metrics.total_impressions,
                    total_clicks=c.metrics.total_clicks,
                    total_reached_queries=c.metrics.total_reached_queries,
                    avg_cpm=c.metrics.avg_cpm,
                    avg_ctr=c.metrics.avg_ctr,
                    waste_score=c.metrics.waste_score,
                ) if c.metrics else None,
                warnings=CampaignWarningsResponse(
                    broken_video_count=c.warnings.broken_video_count,
                    zero_engagement_count=c.warnings.zero_engagement_count,
                    high_spend_low_performance=c.warnings.high_spend_low_performance,
                    disapproved_count=c.warnings.disapproved_count,
                ) if c.warnings else None,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in campaigns
        ]
    else:
        # Fallback to basic listing without metrics
        campaigns = await store.list_campaigns()
        return [
            CampaignResponse(
                id=c["id"],
                name=c["name"],
                creative_ids=c["creative_ids"],
                creative_count=len(c["creative_ids"]),
                created_at=str(c["created_at"]) if c.get("created_at") else None,
                updated_at=str(c["updated_at"]) if c.get("updated_at") else None,
            )
            for c in campaigns
        ]


@app.get("/campaigns/v2", response_model=PaginatedCampaignsResponse, tags=["Campaigns"])
async def list_campaigns_paginated(
    days: int = Query(7, ge=1, le=365, description="Timeframe for metrics aggregation"),
    limit: int = Query(50, ge=1, le=200, description="Page size (max 200)"),
    offset: int = Query(0, ge=0, description="Results offset"),
    include_empty: bool = Query(True, description="Include campaigns with no activity in timeframe"),
    store: SQLiteStore = Depends(get_store),
):
    """List campaigns with pagination metadata and aggregated metrics.

    Phase 11.4: Scale Readiness
    Returns paginated results with metadata for large accounts.
    """
    service = CampaignAggregationService()
    all_campaigns = service.get_campaigns_with_metrics(days=days, include_empty=include_empty)

    # Apply pagination
    total = len(all_campaigns)
    campaigns = all_campaigns[offset:offset + limit]

    data = [
        CampaignResponse(
            id=c.id,
            name=c.name,
            creative_ids=c.creative_ids,
            creative_count=c.creative_count,
            timeframe_days=c.timeframe_days,
            metrics=CampaignMetricsResponse(
                total_spend_micros=c.metrics.total_spend_micros,
                total_impressions=c.metrics.total_impressions,
                total_clicks=c.metrics.total_clicks,
                total_reached_queries=c.metrics.total_reached_queries,
                avg_cpm=c.metrics.avg_cpm,
                avg_ctr=c.metrics.avg_ctr,
                waste_score=c.metrics.waste_score,
            ) if c.metrics else None,
            warnings=CampaignWarningsResponse(
                broken_video_count=c.warnings.broken_video_count,
                zero_engagement_count=c.warnings.zero_engagement_count,
                high_spend_low_performance=c.warnings.high_spend_low_performance,
                disapproved_count=c.warnings.disapproved_count,
            ) if c.warnings else None,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in campaigns
    ]

    return PaginatedCampaignsResponse(
        data=data,
        meta=PaginationMeta(
            timeframe_days=days,
            total=total,
            returned=len(data),
            limit=limit,
            offset=offset,
            has_more=offset + len(data) < total,
        ),
    )


@app.get("/campaigns/unclustered", tags=["Campaigns"])
async def get_unclustered_creatives_early(
    days: int = Query(None, ge=1, le=365, description="Only return creatives with activity in last N days"),
    store: SQLiteStore = Depends(get_store),
):
    """Get IDs of creatives not assigned to any campaign.

    If days is specified, only returns creatives with impressions, clicks, or spend
    in the given timeframe.
    """
    creative_ids = await store.get_unclustered_creative_ids()

    # If days specified, filter to only those with activity
    if days is not None and creative_ids:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _filter_active():
                placeholders = ",".join("?" * len(creative_ids))
                cursor = conn.execute(
                    f"""
                    SELECT DISTINCT creative_id
                    FROM rtb_daily
                    WHERE creative_id IN ({placeholders})
                      AND metric_date >= date('now', '-{days} days')
                      AND (impressions > 0 OR clicks > 0 OR spend_micros > 0)
                    """,
                    creative_ids,
                )
                return [row["creative_id"] for row in cursor.fetchall()]

            active_ids = await loop.run_in_executor(None, _filter_active)
            # Preserve order from original list
            creative_ids = [cid for cid in creative_ids if cid in set(active_ids)]

    return {"creative_ids": creative_ids, "count": len(creative_ids)}


@app.get("/campaigns/{campaign_id}", response_model=CampaignResponse, tags=["Campaigns"])
async def get_campaign(
    campaign_id: str,
    days: int = Query(7, ge=1, le=365, description="Timeframe for metrics aggregation"),
    include_metrics: bool = Query(True, description="Include performance metrics"),
    store: SQLiteStore = Depends(get_store),
):
    """Get a specific campaign by ID with metrics.

    Phase 11.1: Decision Context Foundation
    """
    if include_metrics:
        service = CampaignAggregationService()
        campaign = service.get_campaign_with_metrics(campaign_id, days=days)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            creative_ids=campaign.creative_ids,
            creative_count=campaign.creative_count,
            timeframe_days=campaign.timeframe_days,
            metrics=CampaignMetricsResponse(
                total_spend_micros=campaign.metrics.total_spend_micros,
                total_impressions=campaign.metrics.total_impressions,
                total_clicks=campaign.metrics.total_clicks,
                total_reached_queries=campaign.metrics.total_reached_queries,
                avg_cpm=campaign.metrics.avg_cpm,
                avg_ctr=campaign.metrics.avg_ctr,
                waste_score=campaign.metrics.waste_score,
            ) if campaign.metrics else None,
            warnings=CampaignWarningsResponse(
                broken_video_count=campaign.warnings.broken_video_count,
                zero_engagement_count=campaign.warnings.zero_engagement_count,
                high_spend_low_performance=campaign.warnings.high_spend_low_performance,
                disapproved_count=campaign.warnings.disapproved_count,
            ) if campaign.warnings else None,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )
    else:
        campaign = await store.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return CampaignResponse(
            id=campaign["id"],
            name=campaign["name"],
            creative_ids=campaign["creative_ids"],
            creative_count=len(campaign["creative_ids"]),
            created_at=str(campaign["created_at"]) if campaign.get("created_at") else None,
            updated_at=str(campaign["updated_at"]) if campaign.get("updated_at") else None,
        )


class CollectResponse(BaseModel):
    """Response model for collection job status."""

    status: str
    account_id: str
    filter_query: Optional[str] = None
    message: str
    creatives_collected: Optional[int] = None


async def collect_creatives_task(
    credentials_path: str,
    account_id: str,
    filter_query: Optional[str],
    store: SQLiteStore,
) -> None:
    """Background task to collect creatives from Authorized Buyers API.

    Args:
        credentials_path: Path to service account JSON file.
        account_id: Bidder account ID.
        filter_query: Optional API filter string.
        store: SQLite store instance.
    """
    try:
        logger.info(f"Starting creative collection for account {account_id}")

        client = CreativesClient(
            credentials_path=credentials_path,
            account_id=account_id,
        )

        # Fetch all creatives from API
        api_creatives = await client.fetch_all_creatives(filter_query=filter_query)
        logger.info(f"Fetched {len(api_creatives)} creatives from API")

        # Convert to storage format and save
        storage_creatives = creative_dicts_to_storage(api_creatives)
        count = await store.save_creatives(storage_creatives)

        logger.info(f"Saved {count} creatives to database")

    except Exception as e:
        logger.error(f"Collection failed for account {account_id}: {e}")
        raise


@app.post("/collect", response_model=CollectResponse, tags=["Collection"])
async def start_collection(
    request: CollectRequest,
    background_tasks: BackgroundTasks,
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Start a creative collection job.

    This endpoint initiates collection from the Authorized Buyers RTB API.
    The collection runs as a background task and stores results in the database.

    Use GET /stats to check progress after starting a collection job.
    """
    if not config.is_configured():
        raise HTTPException(
            status_code=400,
            detail="API not configured. Run 'rtbcat configure' first.",
        )

    try:
        credentials_path = str(config.get_service_account_path())
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Service account credentials not configured.",
        )

    # Queue the collection as a background task
    background_tasks.add_task(
        collect_creatives_task,
        credentials_path=credentials_path,
        account_id=request.account_id,
        filter_query=request.filter_query,
        store=store,
    )

    return CollectResponse(
        status="started",
        account_id=request.account_id,
        filter_query=request.filter_query,
        message="Collection job started. Check /stats for progress.",
    )


@app.post("/collect/sync", response_model=CollectResponse, tags=["Collection"])
async def collect_sync(
    request: CollectRequest,
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Synchronously collect creatives (waits for completion).

    This endpoint blocks until collection is complete. Use /collect for
    non-blocking background collection.
    """
    if not config.is_configured():
        raise HTTPException(
            status_code=400,
            detail="API not configured. Run 'rtbcat configure' first.",
        )

    try:
        credentials_path = str(config.get_service_account_path())
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Service account credentials not configured.",
        )

    try:
        client = CreativesClient(
            credentials_path=credentials_path,
            account_id=request.account_id,
        )

        # Fetch all creatives from API
        api_creatives = await client.fetch_all_creatives(filter_query=request.filter_query)

        # Convert to storage format and save
        storage_creatives = creative_dicts_to_storage(api_creatives)
        count = await store.save_creatives(storage_creatives)

        return CollectResponse(
            status="completed",
            account_id=request.account_id,
            filter_query=request.filter_query,
            message=f"Successfully collected {count} creatives.",
            creatives_collected=count,
        )

    except Exception as e:
        logger.error(f"Collection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Collection failed: {str(e)}")


# Buyer Seats endpoints


@app.get("/seats", response_model=list[BuyerSeatResponse], tags=["Buyer Seats"])
async def list_seats(
    bidder_id: Optional[str] = Query(None, description="Filter by bidder ID"),
    active_only: bool = Query(True, description="Only return active seats"),
    store: SQLiteStore = Depends(get_store),
):
    """List all known buyer seats.

    Returns buyer seats that have been discovered via the /seats/discover endpoint.
    """
    seats = await store.get_buyer_seats(bidder_id=bidder_id, active_only=active_only)
    return [
        BuyerSeatResponse(
            buyer_id=s.buyer_id,
            bidder_id=s.bidder_id,
            display_name=s.display_name,
            active=s.active,
            creative_count=s.creative_count,
            last_synced=s.last_synced if isinstance(s.last_synced, str) else (s.last_synced.isoformat() if s.last_synced else None),
            created_at=s.created_at if isinstance(s.created_at, str) else (s.created_at.isoformat() if s.created_at else None),
        )
        for s in seats
    ]


@app.get("/seats/{buyer_id}", response_model=BuyerSeatResponse, tags=["Buyer Seats"])
async def get_seat(
    buyer_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Get a specific buyer seat by ID."""
    seat = await store.get_buyer_seat(buyer_id)
    if not seat:
        raise HTTPException(status_code=404, detail="Buyer seat not found")

    return BuyerSeatResponse(
        buyer_id=seat.buyer_id,
        bidder_id=seat.bidder_id,
        display_name=seat.display_name,
        active=seat.active,
        creative_count=seat.creative_count,
        last_synced=seat.last_synced if isinstance(seat.last_synced, str) else (seat.last_synced.isoformat() if seat.last_synced else None),
        created_at=seat.created_at if isinstance(seat.created_at, str) else (seat.created_at.isoformat() if seat.created_at else None),
    )


@app.post("/seats/discover", response_model=DiscoverSeatsResponse, tags=["Buyer Seats"])
async def discover_seats(
    request: DiscoverSeatsRequest,
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Discover buyer seats under a bidder account.

    Queries the Authorized Buyers API to enumerate all buyer accounts
    associated with the specified bidder and saves them to the database.
    """
    if not config.is_configured():
        raise HTTPException(
            status_code=400,
            detail="API not configured. Run 'rtbcat configure' first.",
        )

    try:
        credentials_path = str(config.get_service_account_path())
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Service account credentials not configured.",
        )

    try:
        client = BuyerSeatsClient(
            credentials_path=credentials_path,
            account_id=request.bidder_id,
        )

        # Discover seats from API
        seats = await client.discover_buyer_seats()
        logger.info(f"Discovered {len(seats)} buyer seats for bidder {request.bidder_id}")

        # Save to database
        for seat in seats:
            await store.save_buyer_seat(seat)

        return DiscoverSeatsResponse(
            status="completed",
            bidder_id=request.bidder_id,
            seats_discovered=len(seats),
            seats=[
                BuyerSeatResponse(
                    buyer_id=s.buyer_id,
                    bidder_id=s.bidder_id,
                    display_name=s.display_name,
                    active=s.active,
                    creative_count=s.creative_count,
                    last_synced=s.last_synced if isinstance(s.last_synced, str) else (s.last_synced.isoformat() if s.last_synced else None),
                    created_at=s.created_at if isinstance(s.created_at, str) else (s.created_at.isoformat() if s.created_at else None),
                )
                for s in seats
            ],
        )

    except Exception as e:
        logger.error(f"Seat discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Seat discovery failed: {str(e)}")


@app.post("/seats/{buyer_id}/sync", response_model=SyncSeatResponse, tags=["Buyer Seats"])
async def sync_seat_creatives(
    buyer_id: str,
    filter_query: Optional[str] = Query(None, description="Optional API filter"),
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Sync creatives for a specific buyer seat.

    Fetches all creatives associated with the buyer seat and stores them
    in the database with the buyer_id field populated.
    """
    # Verify seat exists
    seat = await store.get_buyer_seat(buyer_id)
    if not seat:
        raise HTTPException(status_code=404, detail="Buyer seat not found")

    if not config.is_configured():
        raise HTTPException(
            status_code=400,
            detail="API not configured. Run 'rtbcat configure' first.",
        )

    try:
        credentials_path = str(config.get_service_account_path())
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Service account credentials not configured.",
        )

    try:
        # Use the bidder_id as account_id for API access
        client = CreativesClient(
            credentials_path=credentials_path,
            account_id=seat.bidder_id,
        )

        # Fetch creatives with buyer_id association
        api_creatives = await client.fetch_all_creatives(
            filter_query=filter_query,
            buyer_id=buyer_id,
        )

        # Convert and save
        storage_creatives = creative_dicts_to_storage(api_creatives)
        count = await store.save_creatives(storage_creatives)

        # Update seat metadata
        await store.update_seat_creative_count(buyer_id)
        await store.update_seat_sync_time(buyer_id)

        return SyncSeatResponse(
            status="completed",
            buyer_id=buyer_id,
            creatives_synced=count,
            message=f"Successfully synced {count} creatives for buyer {buyer_id}.",
        )

    except Exception as e:
        logger.error(f"Seat sync failed for {buyer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Seat sync failed: {str(e)}")


class UpdateSeatRequest(BaseModel):
    """Request model for updating a buyer seat."""

    display_name: Optional[str] = None


@app.patch("/seats/{buyer_id}", response_model=BuyerSeatResponse, tags=["Buyer Seats"])
async def update_seat(
    buyer_id: str,
    request: UpdateSeatRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Update a buyer seat's display name."""
    if request.display_name:
        success = await store.update_buyer_seat_display_name(buyer_id, request.display_name)
        if not success:
            raise HTTPException(status_code=404, detail="Buyer seat not found")

    seat = await store.get_buyer_seat(buyer_id)
    if not seat:
        raise HTTPException(status_code=404, detail="Buyer seat not found")

    return BuyerSeatResponse(
        buyer_id=seat.buyer_id,
        bidder_id=seat.bidder_id,
        display_name=seat.display_name,
        active=seat.active,
        creative_count=seat.creative_count,
        last_synced=seat.last_synced if isinstance(seat.last_synced, str) else (seat.last_synced.isoformat() if seat.last_synced else None),
        created_at=seat.created_at if isinstance(seat.created_at, str) else (seat.created_at.isoformat() if seat.created_at else None),
    )


@app.post("/seats/populate", tags=["Buyer Seats"])
async def populate_seats_from_creatives(
    store: SQLiteStore = Depends(get_store),
):
    """Populate buyer_seats table from existing creatives.

    Creates seat records for each unique account_id found in creatives.
    This is useful for migrating data after the initial import.
    """
    try:
        count = await store.populate_buyer_seats_from_creatives()
        return {"status": "completed", "seats_created": count}
    except Exception as e:
        logger.error(f"Seat population failed: {e}")
        raise HTTPException(status_code=500, detail=f"Seat population failed: {str(e)}")


# =============================================================================
# RTB Settings Endpoints (Endpoints & Pretargeting Configs)
# =============================================================================


class RTBEndpointItem(BaseModel):
    """Individual RTB endpoint data."""

    endpoint_id: str
    url: str
    maximum_qps: Optional[int] = None
    trading_location: Optional[str] = None
    bid_protocol: Optional[str] = None


class RTBEndpointsResponse(BaseModel):
    """Response model for RTB endpoints with aggregated data."""

    bidder_id: str
    account_name: Optional[str] = None
    endpoints: list[RTBEndpointItem]
    total_qps_allocated: int
    qps_current: Optional[int] = None
    synced_at: Optional[str] = None


class PretargetingConfigResponse(BaseModel):
    """Response model for a pretargeting config."""

    config_id: str
    bidder_id: str
    billing_id: Optional[str] = None
    display_name: Optional[str] = None
    user_name: Optional[str] = None
    state: str = "ACTIVE"
    included_formats: Optional[list[str]] = None
    included_platforms: Optional[list[str]] = None
    included_sizes: Optional[list[str]] = None
    included_geos: Optional[list[str]] = None
    excluded_geos: Optional[list[str]] = None
    synced_at: Optional[str] = None


class SyncEndpointsResponse(BaseModel):
    """Response model for sync endpoints operation."""

    status: str
    endpoints_synced: int
    bidder_id: str


class SyncPretargetingResponse(BaseModel):
    """Response model for sync pretargeting configs operation."""

    status: str
    configs_synced: int
    bidder_id: str


@app.post("/settings/endpoints/sync", response_model=SyncEndpointsResponse, tags=["RTB Settings"])
async def sync_rtb_endpoints(
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Sync RTB endpoints from Google Authorized Buyers API.

    Fetches all RTB endpoints for the configured bidder account and stores them
    in the rtb_endpoints table.
    """
    try:
        app_config = config.load()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Configuration not set. Use /config to configure."
        )

    if not app_config.authorized_buyers:
        raise HTTPException(
            status_code=400,
            detail="Authorized Buyers not configured. Upload credentials via /config/credentials."
        )

    creds_path = Path(app_config.authorized_buyers.service_account_path).expanduser()
    if not creds_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Service account credentials file not found. Upload via /config/credentials."
        )

    account_id = app_config.authorized_buyers.account_id

    try:
        client = EndpointsClient(
            credentials_path=str(creds_path),
            account_id=account_id,
        )
        endpoints = await client.list_endpoints()

        # Store endpoints in database
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            for ep in endpoints:
                await loop.run_in_executor(
                    None,
                    lambda ep=ep: conn.execute(
                        """
                        INSERT OR REPLACE INTO rtb_endpoints
                        (bidder_id, endpoint_id, url, maximum_qps, trading_location, bid_protocol, synced_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            account_id,
                            ep["endpointId"],
                            ep["url"],
                            ep.get("maximumQps"),
                            ep.get("tradingLocation"),
                            ep.get("bidProtocol"),
                        ),
                    ),
                )
            await loop.run_in_executor(None, conn.commit)

        return SyncEndpointsResponse(
            status="success",
            endpoints_synced=len(endpoints),
            bidder_id=account_id,
        )

    except Exception as e:
        logger.error(f"Failed to sync RTB endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync endpoints: {str(e)}")


@app.get("/settings/endpoints", response_model=RTBEndpointsResponse, tags=["RTB Settings"])
async def get_rtb_endpoints(
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Get stored RTB endpoints with aggregated QPS data.

    Returns all RTB endpoints that have been synced from the Google API,
    along with total allocated QPS and current usage.
    """
    try:
        # Get credentials for bidder_id
        bidder_id = ""
        account_name = None
        try:
            app_config = config.load()
            if app_config and app_config.authorized_buyers:
                bidder_id = app_config.authorized_buyers.account_id
        except Exception:
            pass

        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT * FROM rtb_endpoints ORDER BY trading_location, endpoint_id"
                ).fetchall(),
            )

        endpoints = []
        total_qps = 0
        synced_at = None

        for row in rows:
            endpoints.append(
                RTBEndpointItem(
                    endpoint_id=row["endpoint_id"],
                    url=row["url"],
                    maximum_qps=row["maximum_qps"],
                    trading_location=row["trading_location"],
                    bid_protocol=row["bid_protocol"],
                )
            )
            if row["maximum_qps"]:
                total_qps += row["maximum_qps"]
            if row["synced_at"] and (synced_at is None or row["synced_at"] > synced_at):
                synced_at = row["synced_at"]
            if not bidder_id and row["bidder_id"]:
                bidder_id = row["bidder_id"]

        return RTBEndpointsResponse(
            bidder_id=bidder_id,
            account_name=account_name,
            endpoints=endpoints,
            total_qps_allocated=total_qps,
            qps_current=None,  # Would need real-time monitoring to populate
            synced_at=synced_at,
        )

    except Exception as e:
        logger.error(f"Failed to get RTB endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get endpoints: {str(e)}")


@app.post("/settings/pretargeting/sync", response_model=SyncPretargetingResponse, tags=["RTB Settings"])
async def sync_pretargeting_configs(
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Sync pretargeting configs from Google Authorized Buyers API.

    Fetches all pretargeting configurations for the configured bidder account
    and stores them in the pretargeting_configs table.
    """
    try:
        app_config = config.load()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Configuration not set. Use /config to configure."
        )

    if not app_config.authorized_buyers:
        raise HTTPException(
            status_code=400,
            detail="Authorized Buyers not configured. Upload credentials via /config/credentials."
        )

    creds_path = Path(app_config.authorized_buyers.service_account_path).expanduser()
    if not creds_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Service account credentials file not found. Upload via /config/credentials."
        )

    account_id = app_config.authorized_buyers.account_id

    try:
        client = PretargetingClient(
            credentials_path=str(creds_path),
            account_id=account_id,
        )
        configs = await client.fetch_all_pretargeting_configs()

        # Store configs in database
        async with store._connection() as conn:
            import asyncio
            import json
            loop = asyncio.get_event_loop()

            for cfg in configs:
                # Extract sizes as strings
                sizes = []
                for dim in cfg.get("includedCreativeDimensions", []):
                    if dim.get("width") and dim.get("height"):
                        sizes.append(f"{dim['width']}x{dim['height']}")

                # Extract geo IDs
                geo_targeting = cfg.get("geoTargeting", {}) or {}
                included_geos = geo_targeting.get("includedIds", [])
                excluded_geos = geo_targeting.get("excludedIds", [])

                await loop.run_in_executor(
                    None,
                    lambda cfg=cfg, sizes=sizes, included_geos=included_geos, excluded_geos=excluded_geos: conn.execute(
                        """
                        INSERT OR REPLACE INTO pretargeting_configs
                        (bidder_id, config_id, billing_id, display_name, state,
                         included_formats, included_platforms, included_sizes,
                         included_geos, excluded_geos, raw_config, synced_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            account_id,
                            cfg["configId"],
                            cfg.get("billingId"),
                            cfg.get("displayName"),
                            cfg.get("state", "ACTIVE"),
                            json.dumps(cfg.get("includedFormats", [])),
                            json.dumps(cfg.get("includedPlatforms", [])),
                            json.dumps(sizes),
                            json.dumps(included_geos),
                            json.dumps(excluded_geos),
                            json.dumps(cfg),
                        ),
                    ),
                )
            await loop.run_in_executor(None, conn.commit)

        return SyncPretargetingResponse(
            status="success",
            configs_synced=len(configs),
            bidder_id=account_id,
        )

    except Exception as e:
        logger.error(f"Failed to sync pretargeting configs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync configs: {str(e)}")


@app.get("/settings/pretargeting", response_model=list[PretargetingConfigResponse], tags=["RTB Settings"])
async def get_pretargeting_configs(
    store: SQLiteStore = Depends(get_store),
):
    """Get stored pretargeting configs.

    Returns all pretargeting configurations that have been synced from the Google API.
    Includes user-defined names if set.
    """
    try:
        async with store._connection() as conn:
            import asyncio
            import json
            loop = asyncio.get_event_loop()

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT * FROM pretargeting_configs ORDER BY billing_id"
                ).fetchall(),
            )

        results = []
        for row in rows:
            results.append(
                PretargetingConfigResponse(
                    config_id=row["config_id"],
                    bidder_id=row["bidder_id"],
                    billing_id=row["billing_id"],
                    display_name=row["display_name"],
                    user_name=row["user_name"],
                    state=row["state"] or "ACTIVE",
                    included_formats=json.loads(row["included_formats"]) if row["included_formats"] else None,
                    included_platforms=json.loads(row["included_platforms"]) if row["included_platforms"] else None,
                    included_sizes=json.loads(row["included_sizes"]) if row["included_sizes"] else None,
                    included_geos=json.loads(row["included_geos"]) if row["included_geos"] else None,
                    excluded_geos=json.loads(row["excluded_geos"]) if row["excluded_geos"] else None,
                    synced_at=row["synced_at"],
                )
            )

        return results

    except Exception as e:
        logger.error(f"Failed to get pretargeting configs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get configs: {str(e)}")


class SetPretargetingNameRequest(BaseModel):
    """Request body for setting a custom pretargeting config name."""

    user_name: str = Field(..., description="Custom name for this pretargeting config")


@app.post("/settings/pretargeting/{billing_id}/name", tags=["RTB Settings"])
async def set_pretargeting_name(
    billing_id: str,
    body: SetPretargetingNameRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Set a custom user-defined name for a pretargeting config.

    This name will be displayed in the UI alongside the billing_id,
    making it easier to identify configs.
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            # Get current value for history tracking
            current = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT user_name, config_id, bidder_id FROM pretargeting_configs WHERE billing_id = ?",
                    (billing_id,),
                ).fetchone(),
            )

            if not current:
                raise HTTPException(
                    status_code=404,
                    detail=f"Pretargeting config with billing_id {billing_id} not found"
                )

            old_name = current["user_name"]
            config_id = current["config_id"]
            bidder_id = current["bidder_id"]

            # Update the name
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "UPDATE pretargeting_configs SET user_name = ? WHERE billing_id = ?",
                    (body.user_name, billing_id),
                ),
            )

            # Record history if value changed
            if old_name != body.user_name:
                await loop.run_in_executor(
                    None,
                    lambda: conn.execute(
                        """INSERT INTO pretargeting_history
                        (config_id, bidder_id, change_type, field_changed, old_value, new_value, change_source)
                        VALUES (?, ?, 'update', 'user_name', ?, ?, 'user')""",
                        (config_id, bidder_id, old_name, body.user_name),
                    ),
                )

            await loop.run_in_executor(None, conn.commit)

        return {
            "status": "success",
            "billing_id": billing_id,
            "user_name": body.user_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set pretargeting name: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set name: {str(e)}")


# =============================================================================
# Upload Tracking Endpoints
# =============================================================================


class DailyUploadSummaryResponse(BaseModel):
    """Response model for daily upload summary."""

    upload_date: str
    total_uploads: int
    successful_uploads: int
    failed_uploads: int
    total_rows_written: int
    total_file_size_mb: float
    avg_rows_per_upload: float
    min_rows: Optional[int] = None
    max_rows: Optional[int] = None
    has_anomaly: bool = False
    anomaly_reason: Optional[str] = None


class UploadTrackingResponse(BaseModel):
    """Response model for upload tracking data."""

    daily_summaries: list[DailyUploadSummaryResponse]
    total_days: int
    total_uploads: int
    total_rows: int
    days_with_anomalies: int


@app.get("/uploads/tracking", response_model=UploadTrackingResponse, tags=["Uploads"])
async def get_upload_tracking(
    days: int = Query(30, description="Number of days to retrieve", ge=1, le=365),
    store: SQLiteStore = Depends(get_store),
):
    """Get daily upload tracking summary.

    Returns upload statistics for each day, including:
    - Date with success/failure indicator
    - File size in MB
    - Total rows written
    - Anomaly warnings for sudden drops/spikes in row counts
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """SELECT * FROM daily_upload_summary
                    ORDER BY upload_date DESC
                    LIMIT ?""",
                    (days,),
                ).fetchall(),
            )

        daily_summaries = []
        total_uploads = 0
        total_rows = 0
        days_with_anomalies = 0

        for row in rows:
            file_size_mb = (row["total_file_size_bytes"] or 0) / (1024 * 1024)
            has_anomaly = bool(row["has_anomaly"])

            daily_summaries.append(
                DailyUploadSummaryResponse(
                    upload_date=row["upload_date"],
                    total_uploads=row["total_uploads"] or 0,
                    successful_uploads=row["successful_uploads"] or 0,
                    failed_uploads=row["failed_uploads"] or 0,
                    total_rows_written=row["total_rows_written"] or 0,
                    total_file_size_mb=round(file_size_mb, 2),
                    avg_rows_per_upload=round(row["avg_rows_per_upload"] or 0, 1),
                    min_rows=row["min_rows"],
                    max_rows=row["max_rows"],
                    has_anomaly=has_anomaly,
                    anomaly_reason=row["anomaly_reason"],
                )
            )

            total_uploads += row["total_uploads"] or 0
            total_rows += row["total_rows_written"] or 0
            if has_anomaly:
                days_with_anomalies += 1

        return UploadTrackingResponse(
            daily_summaries=daily_summaries,
            total_days=len(daily_summaries),
            total_uploads=total_uploads,
            total_rows=total_rows,
            days_with_anomalies=days_with_anomalies,
        )

    except Exception as e:
        logger.error(f"Failed to get upload tracking: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get upload tracking: {str(e)}")


class ImportHistoryResponse(BaseModel):
    """Response model for import history entry."""

    batch_id: str
    filename: Optional[str] = None
    imported_at: str
    rows_read: int
    rows_imported: int
    rows_skipped: int
    rows_duplicate: int
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    total_spend_usd: float
    file_size_mb: float
    status: str
    error_message: Optional[str] = None


@app.get("/uploads/history", response_model=list[ImportHistoryResponse], tags=["Uploads"])
async def get_import_history(
    limit: int = Query(50, description="Maximum number of records to return", ge=1, le=500),
    offset: int = Query(0, description="Number of records to skip", ge=0),
    store: SQLiteStore = Depends(get_store),
):
    """Get import history records.

    Returns detailed history of all CSV imports with file sizes, row counts, and status.
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """SELECT * FROM import_history
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall(),
            )

        results = []
        for row in rows:
            file_size_bytes = row["file_size_bytes"] if "file_size_bytes" in row.keys() else 0
            file_size_mb = (file_size_bytes or 0) / (1024 * 1024)

            results.append(
                ImportHistoryResponse(
                    batch_id=row["batch_id"],
                    filename=row["filename"],
                    imported_at=row["created_at"],
                    rows_read=row["rows_read"] or 0,
                    rows_imported=row["rows_imported"] or 0,
                    rows_skipped=row["rows_skipped"] or 0,
                    rows_duplicate=row["rows_duplicate"] or 0,
                    date_range_start=row["date_range_start"],
                    date_range_end=row["date_range_end"],
                    total_spend_usd=row["total_spend_usd"] or 0,
                    file_size_mb=round(file_size_mb, 2),
                    status=row["status"] or "unknown",
                    error_message=row["error_message"],
                )
            )

        return results

    except Exception as e:
        logger.error(f"Failed to get import history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get import history: {str(e)}")


# =============================================================================
# Pretargeting History Endpoints
# =============================================================================


class PretargetingHistoryResponse(BaseModel):
    """Response model for pretargeting history entry."""

    id: int
    config_id: str
    bidder_id: str
    change_type: str
    field_changed: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: str
    changed_by: Optional[str] = None
    change_source: str


@app.get("/settings/pretargeting/history", response_model=list[PretargetingHistoryResponse], tags=["RTB Settings"])
async def get_pretargeting_history(
    config_id: Optional[str] = Query(None, description="Filter by config_id"),
    billing_id: Optional[str] = Query(None, description="Filter by billing_id"),
    days: int = Query(30, description="Number of days of history to retrieve", ge=1, le=365),
    store: SQLiteStore = Depends(get_store),
):
    """Get pretargeting settings change history.

    Returns a log of all changes made to pretargeting configurations,
    including who made the change and when.
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            # Build query based on filters
            query = """
                SELECT ph.* FROM pretargeting_history ph
                LEFT JOIN pretargeting_configs pc ON ph.config_id = pc.config_id
                WHERE ph.changed_at >= datetime('now', ?)
            """
            params = [f"-{days} days"]

            if config_id:
                query += " AND ph.config_id = ?"
                params.append(config_id)
            if billing_id:
                query += " AND pc.billing_id = ?"
                params.append(billing_id)

            query += " ORDER BY ph.changed_at DESC LIMIT 500"

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(query, params).fetchall(),
            )

        results = []
        for row in rows:
            results.append(
                PretargetingHistoryResponse(
                    id=row["id"],
                    config_id=row["config_id"],
                    bidder_id=row["bidder_id"],
                    change_type=row["change_type"],
                    field_changed=row["field_changed"],
                    old_value=row["old_value"],
                    new_value=row["new_value"],
                    changed_at=row["changed_at"],
                    changed_by=row["changed_by"],
                    change_source=row["change_source"] or "unknown",
                )
            )

        return results

    except Exception as e:
        logger.error(f"Failed to get pretargeting history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pretargeting history: {str(e)}")


# =============================================================================
# Campaign Clustering Endpoints
# =============================================================================


class CampaignCreate(BaseModel):
    """Request body for creating a campaign."""

    name: str
    creative_ids: Optional[list[str]] = None


class CampaignUpdate(BaseModel):
    """Request body for updating a campaign."""

    name: Optional[str] = None
    creative_ids: Optional[list[str]] = None  # Replace all creative IDs
    add_creative_ids: Optional[list[str]] = None  # Add to existing
    remove_creative_ids: Optional[list[str]] = None  # Remove from existing


class AutoClusterRequest(BaseModel):
    """Request body for auto-clustering."""

    by_url: bool = True
    by_country: bool = False


class ClusterSuggestion(BaseModel):
    """A suggested campaign cluster."""

    suggested_name: str
    creative_ids: list[str]
    domain: Optional[str] = None
    country: Optional[str] = None


class AutoClusterResponse(BaseModel):
    """Response model for auto-cluster suggestions."""

    suggestions: list[ClusterSuggestion]
    unclustered_count: int


@app.post("/campaigns", response_model=CampaignResponse, tags=["Campaigns"])
async def create_campaign(
    body: CampaignCreate,
    store: SQLiteStore = Depends(get_store),
):
    """Create a new campaign."""
    campaign = await store.create_campaign(
        name=body.name,
        creative_ids=body.creative_ids,
    )
    return CampaignResponse(
        id=campaign["id"],
        name=campaign["name"],
        creative_ids=campaign["creative_ids"],
    )


@app.patch("/campaigns/{campaign_id}", response_model=CampaignResponse, tags=["Campaigns"])
async def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    store: SQLiteStore = Depends(get_store),
):
    """Update a campaign's name and/or creative assignments.

    Supports three modes for creative assignment:
    - creative_ids: Replace all creative IDs with the provided list
    - add_creative_ids: Add the provided IDs to existing assignments
    - remove_creative_ids: Remove the provided IDs from existing assignments

    add/remove can be used together in one request.
    """
    # Handle add/remove creative IDs
    final_creative_ids = body.creative_ids
    if body.add_creative_ids or body.remove_creative_ids:
        # Get current campaign to get existing creative_ids
        current = await store.get_campaign(campaign_id)
        if not current:
            raise HTTPException(status_code=404, detail="Campaign not found")

        current_ids = set(current.get("creative_ids", []))

        if body.add_creative_ids:
            current_ids.update(body.add_creative_ids)
        if body.remove_creative_ids:
            current_ids.difference_update(body.remove_creative_ids)

        final_creative_ids = list(current_ids)

    campaign = await store.update_campaign(
        campaign_id=campaign_id,
        name=body.name,
        creative_ids=final_creative_ids,
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse(
        id=campaign["id"],
        name=campaign["name"],
        creative_ids=campaign["creative_ids"],
        created_at=str(campaign["created_at"]) if campaign.get("created_at") else None,
        updated_at=str(campaign["updated_at"]) if campaign.get("updated_at") else None,
    )


@app.delete("/campaigns/{campaign_id}", tags=["Campaigns"])
async def delete_campaign(
    campaign_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Delete a campaign (creatives become unclustered)."""
    deleted = await store.delete_campaign(campaign_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"status": "deleted", "campaign_id": campaign_id}


@app.post("/campaigns/auto-cluster", response_model=AutoClusterResponse, tags=["Campaigns"])
async def auto_cluster_creatives(
    body: AutoClusterRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Auto-cluster unclustered creatives by destination URL (and optionally country).

    Returns suggested clusters without saving them. User must confirm to create.
    """
    from urllib.parse import urlparse

    # Get unclustered creatives with their data
    unclustered_ids = await store.get_unclustered_creative_ids()
    if not unclustered_ids:
        return AutoClusterResponse(suggestions=[], unclustered_count=0)

    # Fetch creative details
    creatives = []
    for cid in unclustered_ids[:500]:  # Limit to 500 for performance
        creative = await store.get_creative(cid)
        if creative:
            creatives.append(creative)

    # Cluster by URL
    clusters: dict[str, list] = {}
    for c in creatives:
        url = c.final_url or c.display_url or ""
        try:
            parsed = urlparse(url if url.startswith("http") else f"https://{url}")
            # Use domain + first path segment
            path_parts = [p for p in parsed.path.split("/") if p][:2]
            key = f"{parsed.netloc}/{'/'.join(path_parts)}" if path_parts else parsed.netloc
            if not key or key == "/":
                key = "unknown"
        except Exception:
            key = "unknown"

        if key not in clusters:
            clusters[key] = []
        clusters[key].append(c)

    # Build suggestions (only clusters with 2+ creatives)
    suggestions = []
    for domain_key, cluster_creatives in clusters.items():
        if len(cluster_creatives) >= 2:
            # Generate a name from the domain
            suggested_name = domain_key.split("/")[0].replace("www.", "").split(".")[0].title()
            if suggested_name == "Unknown":
                suggested_name = f"Cluster {len(suggestions) + 1}"

            suggestions.append(
                ClusterSuggestion(
                    suggested_name=suggested_name,
                    creative_ids=[c.id for c in cluster_creatives],
                    domain=domain_key,
                )
            )

    # Sort by cluster size
    suggestions.sort(key=lambda s: len(s.creative_ids), reverse=True)

    return AutoClusterResponse(
        suggestions=suggestions[:20],  # Limit to top 20 suggestions
        unclustered_count=len(unclustered_ids),
    )


# Waste Analysis endpoints


@app.get("/analytics/waste", response_model=WasteReportResponse, tags=["Analytics"])
async def get_waste_report(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    days: int = Query(7, ge=1, le=90, description="Days of traffic to analyze"),
    store: SQLiteStore = Depends(get_store),
):
    """Get waste analysis report comparing bid requests vs creative inventory.

    Analyzes RTB traffic data to identify size gaps - ad sizes that receive
    bid requests but have no matching creatives in inventory. This helps
    identify bandwidth waste and optimization opportunities.

    Returns recommendations for each gap:
    - **Block**: High volume non-standard sizes to block in pretargeting
    - **Add Creative**: Consider adding creative for this size
    - **Use Flexible**: Near-IAB sizes that can use flexible HTML5 creatives
    - **Monitor**: Low volume sizes to watch for growth
    """
    try:
        analyzer = WasteAnalyzer(store)
        report = await analyzer.analyze_waste(buyer_id=buyer_id, days=days)

        return WasteReportResponse(
            buyer_id=report.buyer_id,
            total_requests=report.total_requests,
            total_waste_requests=report.total_waste_requests,
            waste_percentage=round(report.waste_percentage, 2),
            size_gaps=[
                SizeGapResponse(
                    canonical_size=g.canonical_size,
                    request_count=g.request_count,
                    creative_count=g.creative_count,
                    estimated_qps=round(g.estimated_qps, 2),
                    estimated_waste_pct=round(g.estimated_waste_pct, 2),
                    recommendation=g.recommendation,
                    recommendation_detail=g.recommendation_detail,
                    potential_savings_usd=g.potential_savings_usd,
                    closest_iab_size=g.closest_iab_size,
                )
                for g in report.size_gaps
            ],
            size_coverage=[
                SizeCoverageResponse(
                    canonical_size=c.canonical_size,
                    creative_count=c.creative_count,
                    request_count=c.request_count,
                    coverage_status=c.coverage_status,
                    formats=c.formats,
                )
                for c in report.size_coverage
            ],
            potential_savings_qps=round(report.potential_savings_qps, 2),
            potential_savings_usd=report.potential_savings_usd,
            analysis_period_days=report.analysis_period_days,
            generated_at=report.generated_at,
            recommendations_summary=report.recommendations_summary,
        )

    except Exception as e:
        logger.error(f"Waste analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Waste analysis failed: {str(e)}")


# ============================================================
# Phase 11.2: Evidence-Based Waste Signals
# ============================================================

class WasteSignalResponse(BaseModel):
    """Response model for a waste signal."""
    id: int
    creative_id: str
    signal_type: str
    confidence: str
    evidence: dict
    observation: str
    recommendation: str
    detected_at: str
    resolved_at: Optional[str] = None


@app.get("/analytics/waste-signals/{creative_id}", response_model=list[WasteSignalResponse], tags=["Analytics"])
async def get_waste_signals(
    creative_id: str,
    include_resolved: bool = Query(False, description="Include resolved signals"),
):
    """Get evidence-based waste signals for a creative.

    Phase 11.2: Evidence-Based Waste Detection
    Returns signals with full evidence chain explaining WHY the creative is flagged.
    """
    service = WasteAnalyzerService()
    signals = service.get_signals_for_creative(creative_id, include_resolved=include_resolved)
    return [WasteSignalResponse(**s) for s in signals]


class ProblemFormatResponse(BaseModel):
    """Response model for problem format detection."""
    creative_id: str
    problem_type: str
    evidence: dict
    severity: str
    recommendation: str


@app.get("/analytics/problem-formats", response_model=list[ProblemFormatResponse], tags=["Analytics"])
async def detect_problem_formats(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    days: int = Query(7, ge=1, le=90, description="Timeframe for analysis"),
    size_tolerance: int = Query(5, ge=0, le=20, description="Pixel tolerance for size matching"),
    store: SQLiteStore = Depends(get_store),
):
    """Detect creatives with problems that hurt QPS efficiency.

    Phase 22: Problem format detection identifies creatives that should be
    reviewed or removed.

    Problem types:
    - zero_bids: Has reached_queries but no impressions
    - non_standard: Size doesn't match any IAB standard (even with tolerance)
    - low_bid_rate: impressions / reached_queries < 1%
    - disapproved: approval_status != 'APPROVED'
    """
    from analytics.waste_analyzer import WasteAnalyzer

    analyzer = WasteAnalyzer(store)
    problems = await analyzer.detect_problem_formats(
        buyer_id=buyer_id,
        days=days,
        size_tolerance=size_tolerance,
    )

    return [
        ProblemFormatResponse(
            creative_id=p.creative_id,
            problem_type=p.problem_type,
            evidence=p.evidence,
            severity=p.severity,
            recommendation=p.recommendation,
        )
        for p in problems
    ]


@app.post("/analytics/waste-signals/analyze", tags=["Analytics"])
async def run_waste_analysis(
    days: int = Query(7, ge=1, le=90, description="Timeframe for analysis"),
    save_to_db: bool = Query(True, description="Save signals to database"),
):
    """Run waste analysis on all creatives with recent activity.

    Phase 11.2: Evidence-Based Waste Detection
    Analyzes all creatives and generates signals with evidence.
    """
    service = WasteAnalyzerService()
    signals = service.analyze_all_creatives(days=days, save_to_db=save_to_db)

    return {
        "status": "complete",
        "signals_generated": len(signals),
        "by_type": _group_signals_by_type(signals),
    }


def _group_signals_by_type(signals) -> dict[str, int]:
    """Group signals by type and count."""
    counts = {}
    for s in signals:
        counts[s.signal_type] = counts.get(s.signal_type, 0) + 1
    return counts


@app.post("/analytics/waste-signals/{signal_id}/resolve", tags=["Analytics"])
async def resolve_waste_signal(
    signal_id: int,
    notes: Optional[str] = Query(None, description="Resolution notes"),
):
    """Mark a waste signal as resolved.

    Phase 11.2: Evidence-Based Waste Detection
    """
    service = WasteAnalyzerService()
    success = service.resolve_signal(signal_id, resolved_by="user", notes=notes)

    if not success:
        raise HTTPException(status_code=404, detail="Signal not found")

    return {"status": "resolved", "signal_id": signal_id}


@app.get(
    "/analytics/size-coverage",
    response_model=dict[str, SizeCoverageResponse],
    tags=["Analytics"],
)
async def get_size_coverage(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store: SQLiteStore = Depends(get_store),
):
    """Get creative coverage by size with traffic correlation.

    Returns a dictionary mapping each canonical size to its coverage data,
    including creative count, request count, and coverage status.

    Coverage statuses:
    - **good**: Adequate creative coverage for traffic volume
    - **low**: Some creatives but may need more for volume
    - **none**: No creatives (represents waste)
    - **excess**: Have creatives but no traffic
    """
    try:
        analyzer = WasteAnalyzer(store)
        coverage = await analyzer.get_size_coverage(buyer_id=buyer_id)

        return {
            size: SizeCoverageResponse(
                canonical_size=size,
                creative_count=data["creatives"],
                request_count=data["requests"],
                coverage_status=data["coverage"],
                formats=data.get("formats", {}),
            )
            for size, data in coverage.items()
        }

    except Exception as e:
        logger.error(f"Size coverage lookup failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Size coverage lookup failed: {str(e)}"
        )


@app.post("/analytics/import-traffic", response_model=ImportTrafficResponse, tags=["Analytics"])
async def import_traffic_data(
    file: UploadFile = File(..., description="CSV file with traffic data"),
    store: SQLiteStore = Depends(get_store),
):
    """Import RTB traffic data from CSV file.

    The CSV file should have the following columns:
    - **canonical_size**: Normalized size category (e.g., "300x250 (Medium Rectangle)")
    - **raw_size**: Original requested size (e.g., "300x250")
    - **request_count**: Number of bid requests
    - **date**: Date in YYYY-MM-DD format
    - **buyer_id** (optional): Buyer seat ID

    Example CSV:
    ```
    canonical_size,raw_size,request_count,date,buyer_id
    "300x250 (Medium Rectangle)",300x250,50000,2024-01-15,456
    "Non-Standard (320x481)",320x481,12000,2024-01-15,456
    ```
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read and parse CSV
        contents = await file.read()
        text = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        # Validate required columns
        required_columns = {"canonical_size", "raw_size", "request_count", "date"}
        if reader.fieldnames is None:
            raise HTTPException(status_code=400, detail="CSV file is empty or malformed")

        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {', '.join(missing)}",
            )

        # Parse records
        records = []
        for row in reader:
            try:
                records.append(
                    {
                        "canonical_size": row["canonical_size"],
                        "raw_size": row["raw_size"],
                        "request_count": int(row["request_count"]),
                        "date": row["date"],
                        "buyer_id": row.get("buyer_id") or None,
                    }
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid row: {row}, error: {e}")
                continue

        if not records:
            raise HTTPException(status_code=400, detail="No valid records found in CSV")

        # Store traffic data
        count = await store.store_traffic_data(records)

        return ImportTrafficResponse(
            status="completed",
            records_imported=count,
            message=f"Successfully imported {count} traffic records.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Traffic import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Traffic import failed: {str(e)}")


@app.post("/analytics/generate-mock-traffic", response_model=ImportTrafficResponse, tags=["Analytics"])
async def generate_mock_traffic_endpoint(
    days: int = Query(7, ge=1, le=30, description="Days of traffic to generate"),
    buyer_id: Optional[str] = Query(None, description="Buyer ID to associate"),
    base_daily_requests: int = Query(100000, ge=1000, le=1000000, description="Base daily request volume"),
    waste_bias: float = Query(0.3, ge=0.0, le=1.0, description="Bias towards waste traffic (0-1)"),
    store: SQLiteStore = Depends(get_store),
):
    """Generate mock RTB traffic data for testing and demos.

    Creates synthetic bid request data with realistic distributions including:
    - IAB standard sizes (high volume)
    - Non-standard sizes (configurable waste)
    - Video sizes
    - Day-over-day variance

    Use `waste_bias` to control how much non-standard (waste) traffic is generated:
    - 0.0 = minimal waste, mostly standard sizes
    - 0.5 = balanced mix
    - 1.0 = heavy waste traffic
    """
    from analytics import generate_mock_traffic

    try:
        # Generate mock traffic
        traffic_records = generate_mock_traffic(
            days=days,
            buyer_id=buyer_id,
            base_daily_requests=base_daily_requests,
            waste_bias=waste_bias,
        )

        # Convert to dict format for storage
        records = [
            {
                "canonical_size": r.canonical_size,
                "raw_size": r.raw_size,
                "request_count": r.request_count,
                "date": r.date,
                "buyer_id": r.buyer_id,
            }
            for r in traffic_records
        ]

        # Store traffic data
        count = await store.store_traffic_data(records)

        return ImportTrafficResponse(
            status="completed",
            records_imported=count,
            message=f"Generated and stored {count} mock traffic records for {days} days.",
        )

    except Exception as e:
        logger.error(f"Mock traffic generation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Mock traffic generation failed: {str(e)}"
        )


# ============================================================================
# QPS Optimization Endpoints (using new qps module)
# ============================================================================

from datetime import datetime, timezone
from qps import (
    import_bigquery_csv,
    get_import_summary,
    SizeCoverageAnalyzer,
    ConfigPerformanceTracker,
    FraudSignalDetector,
    ACCOUNT_ID,
    ACCOUNT_NAME,
)


class QPSImportResponse(BaseModel):
    """Response for QPS CSV import."""

    status: str
    rows_read: int
    rows_imported: int
    rows_skipped: int
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    sizes_found: int
    billing_ids_found: list[str]
    total_reached_queries: int
    total_spend_usd: float
    errors: list[str] = []


class QPSSummaryResponse(BaseModel):
    """Response for QPS data summary."""

    total_rows: int
    unique_dates: int
    unique_billing_ids: int
    unique_sizes: int
    date_range: dict
    total_reached_queries: int
    total_impressions: int
    total_spend_usd: float


class QPSReportResponse(BaseModel):
    """Response for QPS report (plain text)."""

    report: str
    generated_at: str
    analysis_days: int


@app.get("/qps/summary", response_model=QPSSummaryResponse, tags=["QPS Optimization"])
async def get_qps_summary():
    """
    Get summary of imported QPS data.

    Returns counts of rows, dates, sizes, and totals from size_metrics_daily.
    """
    try:
        summary = get_import_summary()
        return QPSSummaryResponse(
            total_rows=summary["total_rows"],
            unique_dates=summary["unique_dates"],
            unique_billing_ids=summary["unique_billing_ids"],
            unique_sizes=summary["unique_sizes"],
            date_range=summary["date_range"],
            total_reached_queries=summary["total_reached_queries"],
            total_impressions=summary["total_impressions"],
            total_spend_usd=summary["total_spend_usd"],
        )
    except Exception as e:
        logger.error(f"Failed to get QPS summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/qps/size-coverage", response_model=QPSReportResponse, tags=["QPS Optimization"])
async def get_size_coverage_report(days: int = Query(7, ge=1, le=90)):
    """
    Get size coverage analysis report.

    Compares your creative inventory against received traffic to identify:
    - Sizes you can serve
    - Sizes you cannot serve (waste)
    - Recommended pretargeting include list

    Args:
        days: Number of days to analyze (default: 7)
    """
    try:
        analyzer = SizeCoverageAnalyzer()
        report_text = analyzer.generate_report(days)

        return QPSReportResponse(
            report=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_days=days,
        )
    except Exception as e:
        logger.error(f"Failed to generate size coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/qps/config-performance", response_model=QPSReportResponse, tags=["QPS Optimization"])
async def get_config_performance_report(days: int = Query(7, ge=1, le=90)):
    """
    Get pretargeting config performance report.

    Compares efficiency across your 10 pretargeting configs to identify
    configs needing investigation.

    Args:
        days: Number of days to analyze (default: 7)
    """
    try:
        tracker = ConfigPerformanceTracker()
        report_text = tracker.generate_report(days)

        return QPSReportResponse(
            report=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_days=days,
        )
    except Exception as e:
        logger.error(f"Failed to generate config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/qps/fraud-signals", response_model=QPSReportResponse, tags=["QPS Optimization"])
async def get_fraud_signals_report(days: int = Query(14, ge=1, le=90)):
    """
    Get fraud signals report.

    Detects suspicious patterns for human review:
    - Unusually high CTR
    - Clicks exceeding impressions

    These are PATTERNS, not proof of fraud. All signals require human review.

    Args:
        days: Number of days to analyze (default: 14)
    """
    try:
        detector = FraudSignalDetector()
        report_text = detector.generate_report(days)

        return QPSReportResponse(
            report=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_days=days,
        )
    except Exception as e:
        logger.error(f"Failed to generate fraud signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/qps/report", response_model=QPSReportResponse, tags=["QPS Optimization"])
async def get_full_qps_report(days: int = Query(7, ge=1, le=90)):
    """
    Get comprehensive QPS optimization report.

    Combines all analysis modules:
    1. Size Coverage Analysis
    2. Config Performance Tracking
    3. Fraud Signal Detection

    Args:
        days: Number of days to analyze (default: 7)
    """
    try:
        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("Cat-Scan QPS OPTIMIZATION FULL REPORT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Account: {ACCOUNT_NAME} (ID: {ACCOUNT_ID})")
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"Analysis Period: {days} days")
        lines.append("")

        # Size Coverage
        try:
            analyzer = SizeCoverageAnalyzer()
            lines.append(analyzer.generate_report(days))
            lines.append("")
        except Exception as e:
            lines.append(f"Size Coverage: Error - {e}")
            lines.append("")

        # Config Performance
        try:
            tracker = ConfigPerformanceTracker()
            lines.append(tracker.generate_report(days))
            lines.append("")
        except Exception as e:
            lines.append(f"Config Performance: Error - {e}")
            lines.append("")

        # Fraud Signals
        try:
            detector = FraudSignalDetector()
            lines.append(detector.generate_report(days * 2))
            lines.append("")
        except Exception as e:
            lines.append(f"Fraud Signals: Error - {e}")
            lines.append("")

        lines.append("=" * 80)
        lines.append("END OF FULL REPORT")
        lines.append("=" * 80)

        report_text = "\n".join(lines)

        return QPSReportResponse(
            report=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_days=days,
        )
    except Exception as e:
        logger.error(f"Failed to generate full report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/qps/include-list", tags=["QPS Optimization"])
async def get_include_list():
    """
    Get recommended pretargeting include list.

    Returns sizes that:
    1. You have creatives for
    2. Are in Google's 114-size pretargeting list

    WARNING: Adding these to pretargeting will EXCLUDE all other sizes!
    """
    try:
        analyzer = SizeCoverageAnalyzer()
        report = analyzer.analyze_coverage(days=7)

        return {
            "include_list": report.include_list,
            "count": len(report.include_list),
            "warning": "Adding these sizes will EXCLUDE all other sizes!",
            "instructions": [
                "Go to Authorized Buyers UI",
                "Navigate to Bidder Settings -> Pretargeting",
                "Edit the config you want to modify",
                "Under 'Creative dimensions', add these sizes",
                "Click Save",
                "Monitor traffic for 24-48 hours",
            ],
        }
    except Exception as e:
        logger.error(f"Failed to get include list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Performance Metrics endpoints


@app.post("/performance/import", response_model=ImportPerformanceResponse, tags=["Performance"])
async def import_performance_metrics(
    request: ImportPerformanceRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Import performance metrics in bulk.

    Accepts an array of performance metrics and stores them using UPSERT semantics.
    If a record with the same (creative_id, metric_date, geography, device_type, placement)
    already exists, it will be updated.

    Currency values are in USD micros (1,000,000 = $1.00). CPM and CPC are computed
    automatically if not provided.

    Example request body:
    ```json
    {
      "metrics": [
        {
          "creative_id": "12345",
          "metric_date": "2025-11-29",
          "impressions": 10000,
          "clicks": 150,
          "spend_micros": 5000000,
          "geography": "US",
          "device_type": "MOBILE"
        }
      ]
    }
    ```
    """
    try:
        # Convert to PerformanceMetric objects
        metrics = [
            PerformanceMetric(
                creative_id=m.creative_id,
                metric_date=m.metric_date,
                impressions=m.impressions,
                clicks=m.clicks,
                spend_micros=m.spend_micros,
                campaign_id=m.campaign_id,
                geography=m.geography,
                device_type=m.device_type,
                placement=m.placement,
            )
            for m in request.metrics
        ]

        count = await store.save_performance_metrics(metrics)

        return ImportPerformanceResponse(
            status="completed",
            records_imported=count,
            message=f"Successfully imported {count} performance metrics.",
        )

    except Exception as e:
        logger.error(f"Performance import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Performance import failed: {str(e)}")


@app.get(
    "/performance/creative/{creative_id}",
    response_model=PerformanceSummaryResponse,
    tags=["Performance"],
)
async def get_creative_performance(
    creative_id: str,
    days: int = Query(30, ge=1, le=365, description="Days to aggregate"),
    store: SQLiteStore = Depends(get_store),
):
    """Get aggregated performance summary for a creative.

    Returns total impressions, clicks, spend, and computed metrics (CPM, CPC, CTR)
    for the specified time period.

    Currency values are in USD micros (1,000,000 = $1.00).
    CTR is returned as a percentage (e.g., 1.5 = 1.5%).
    """
    try:
        summary = await store.get_creative_performance_summary(creative_id, days=days)

        return PerformanceSummaryResponse(
            total_impressions=summary.get("total_impressions"),
            total_clicks=summary.get("total_clicks"),
            total_spend_micros=summary.get("total_spend_micros"),
            avg_cpm_micros=summary.get("avg_cpm_micros"),
            avg_cpc_micros=summary.get("avg_cpc_micros"),
            ctr_percent=round(summary.get("ctr_percent"), 2) if summary.get("ctr_percent") else None,
            days_with_data=summary.get("days_with_data"),
            earliest_date=summary.get("earliest_date"),
            latest_date=summary.get("latest_date"),
        )

    except Exception as e:
        logger.error(f"Performance lookup failed for {creative_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Performance lookup failed: {str(e)}")


@app.get(
    "/performance/metrics",
    response_model=list[PerformanceMetricResponse],
    tags=["Performance"],
)
async def list_performance_metrics(
    creative_id: Optional[str] = Query(None, description="Filter by creative ID"),
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    geography: Optional[str] = Query(None, description="Filter by country code"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    store: SQLiteStore = Depends(get_store),
):
    """List performance metrics with optional filtering.

    Returns individual daily performance records matching the specified filters.
    Use the creative/{id} endpoint for aggregated summaries.
    """
    try:
        metrics = await store.get_performance_metrics(
            creative_id=creative_id,
            campaign_id=campaign_id,
            start_date=start_date,
            end_date=end_date,
            geography=geography,
            device_type=device_type,
            limit=limit,
        )

        return [
            PerformanceMetricResponse(
                id=m.id,
                creative_id=m.creative_id,
                campaign_id=m.campaign_id,
                metric_date=m.metric_date,
                impressions=m.impressions,
                clicks=m.clicks,
                spend_micros=m.spend_micros,
                cpm_micros=m.cpm_micros,
                cpc_micros=m.cpc_micros,
                geography=m.geography,
                device_type=m.device_type,
                placement=m.placement,
            )
            for m in metrics
        ]

    except Exception as e:
        logger.error(f"Performance metrics query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Performance query failed: {str(e)}")


@app.post("/performance/campaign/{campaign_id}/refresh-cache", tags=["Performance"])
async def refresh_campaign_performance_cache(
    campaign_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Refresh cached performance aggregates for a campaign.

    Computes and stores spend_7d, spend_30d, total_impressions, total_clicks,
    avg_cpm, and avg_cpc on the campaigns table for faster lookups.

    Call this after importing new performance data for a campaign.
    """
    try:
        # Verify campaign exists
        campaign = await store.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        await store.update_campaign_performance_cache(campaign_id)

        return {"status": "completed", "campaign_id": campaign_id, "message": "Cache refreshed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache refresh failed for {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Cache refresh failed: {str(e)}")


@app.delete("/performance/cleanup", tags=["Performance"])
async def cleanup_old_rtb_daily(
    days_to_keep: int = Query(90, ge=7, le=365, description="Days of data to retain"),
    store: SQLiteStore = Depends(get_store),
):
    """Delete performance data older than the retention period.

    Use this to manage database size by removing old historical data.
    Default retention is 90 days.
    """
    try:
        deleted = await store.clear_old_rtb_daily(days_to_keep=days_to_keep)

        return {
            "status": "completed",
            "records_deleted": deleted,
            "message": f"Deleted {deleted} records older than {days_to_keep} days.",
        }

    except Exception as e:
        logger.error(f"Performance cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


class CSVImportResult(BaseModel):
    """Result of CSV import operation."""

    success: bool
    batch_id: Optional[str] = None
    rows_read: Optional[int] = None
    rows_imported: Optional[int] = None
    rows_duplicate: Optional[int] = None
    rows_skipped: Optional[int] = None
    date_range: Optional[dict] = None
    unique_creatives: Optional[int] = None
    unique_sizes: Optional[int] = None
    unique_countries: Optional[int] = None
    billing_ids: Optional[list[str]] = None
    total_reached: Optional[int] = None
    total_impressions: Optional[int] = None
    total_spend_usd: Optional[float] = None
    columns_imported: Optional[list[str]] = None
    error: Optional[str] = None
    fix_instructions: Optional[str] = None
    columns_found: Optional[list[str]] = None
    columns_mapped: Optional[dict] = None
    required_missing: Optional[list[str]] = None
    errors: Optional[list[str]] = None


@app.post("/performance/import-csv", response_model=CSVImportResult, tags=["Performance"])
async def import_performance_csv(
    file: UploadFile = File(..., description="CSV file with performance data"),
):
    """Import performance data from Authorized Buyers CSV export.

    Uses the unified importer which:
    - Validates required columns (Day, Creative ID, Billing ID, Creative size, Reached queries, Impressions)
    - Stores raw data in rtb_daily table
    - Returns detailed import statistics

    If validation fails, returns fix instructions for BigQuery export configuration.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    tmp_path = None
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Validate first
        validation = validate_csv(tmp_path)

        if not validation.is_valid:
            # Return validation error with fix instructions
            return CSVImportResult(
                success=False,
                error=validation.error_message,
                fix_instructions=validation.get_fix_instructions(),
                columns_found=validation.columns_found,
                columns_mapped=validation.columns_mapped,
                required_missing=validation.required_missing,
            )

        # Import
        result = import_csv(tmp_path)

        if not result.success:
            return CSVImportResult(
                success=False,
                error=result.error_message,
                errors=result.errors,
            )

        return CSVImportResult(
            success=True,
            batch_id=result.batch_id,
            rows_read=result.rows_read,
            rows_imported=result.rows_imported,
            rows_duplicate=result.rows_duplicate,
            rows_skipped=result.rows_skipped,
            date_range={
                "start": result.date_range_start,
                "end": result.date_range_end,
            },
            unique_creatives=result.unique_creatives,
            unique_sizes=len(result.unique_sizes),
            unique_countries=len(result.unique_countries),
            billing_ids=result.unique_billing_ids,
            total_reached=result.total_reached,
            total_impressions=result.total_impressions,
            total_spend_usd=result.total_spend_usd,
            columns_imported=result.columns_imported,
        )

    except Exception as e:
        logger.error(f"Import failed: {e}")
        return CSVImportResult(
            success=False,
            error=str(e),
        )

    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post(
    "/performance/metrics/batch",
    response_model=BatchPerformanceResponse,
    tags=["Performance"],
)
async def get_batch_performance(
    request: BatchPerformanceRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Get performance summaries for multiple creatives in a single request.

    This is optimized for the dashboard view where performance data for all
    visible creatives needs to be fetched at once.

    Period options:
    - `yesterday`: Last 1 day
    - `7d`: Last 7 days
    - `30d`: Last 30 days
    - `all_time`: All available data (up to 365 days)

    Returns a dict mapping creative_id to performance summary.
    """
    try:
        # Map period to days
        period_days = {
            "yesterday": 1,
            "7d": 7,
            "30d": 30,
            "all_time": 365,
        }
        days = period_days.get(request.period, 7)

        # Fetch performance for each creative
        results: dict[str, CreativePerformanceSummary] = {}

        for creative_id in request.creative_ids:
            try:
                summary = await store.get_creative_performance_summary(
                    creative_id, days=days
                )

                has_data = summary.get("total_impressions", 0) > 0 or summary.get("total_spend_micros", 0) > 0

                results[creative_id] = CreativePerformanceSummary(
                    creative_id=creative_id,
                    total_impressions=summary.get("total_impressions") or 0,
                    total_clicks=summary.get("total_clicks") or 0,
                    total_spend_micros=summary.get("total_spend_micros") or 0,
                    avg_cpm_micros=summary.get("avg_cpm_micros"),
                    avg_cpc_micros=summary.get("avg_cpc_micros"),
                    ctr_percent=round(summary.get("ctr_percent"), 2) if summary.get("ctr_percent") else None,
                    days_with_data=summary.get("days_with_data") or 0,
                    has_data=has_data,
                )
            except Exception as e:
                logger.warning(f"Failed to get performance for {creative_id}: {e}")
                # Return empty summary on error
                results[creative_id] = CreativePerformanceSummary(
                    creative_id=creative_id,
                    has_data=False,
                )

        return BatchPerformanceResponse(
            performance=results,
            period=request.period,
            count=len(results),
        )

    except Exception as e:
        logger.error(f"Batch performance lookup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch lookup failed: {str(e)}")


class StreamingImportProgress(BaseModel):
    """Progress update for streaming import."""

    status: str
    rows_processed: int
    rows_imported: int
    rows_skipped: int
    current_batch: int
    errors: list[dict] = []


class StreamingImportResult(BaseModel):
    """Final result of streaming import."""

    status: str
    total_rows: int
    imported: int
    skipped: int
    batches: int
    errors: list[dict] = []
    date_range: Optional[dict] = None
    total_spend: Optional[float] = None


@app.post("/performance/import/stream", response_model=StreamingImportResult, tags=["Performance"])
async def import_performance_stream(
    request: Request,
    store: SQLiteStore = Depends(get_store),
):
    """
    Streaming import endpoint for large CSV files.

    Accepts NDJSON (newline-delimited JSON) stream of performance rows.
    Each line should be a JSON object with performance data.

    This endpoint:
    - Processes data in batches of 1000 rows
    - Uses optimized lookup tables for repeated values
    - Returns progress updates (if SSE client)
    - Never holds entire file in memory

    Example NDJSON format:
    ```
    {"creative_id":"79783","date":"2025-11-29","impressions":1000,"clicks":50,"spend":25.50,"geography":"US"}
    {"creative_id":"79784","date":"2025-11-29","impressions":500,"clicks":10,"spend":5.00,"geography":"BR"}
    ```

    For large files (200MB+), use this with the chunked upload frontend
    that sends data in streaming batches.
    """
    import sqlite3
    from pathlib import Path
    from storage.performance_repository import PerformanceRepository

    BATCH_SIZE = 1000
    batch: list[dict] = []
    total_processed = 0
    total_imported = 0
    total_skipped = 0
    batch_count = 0
    errors: list[dict] = []
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    total_spend = 0.0

    try:
        # Get database path and create direct connection for repository
        db_path = Path.home() / ".catscan" / "catscan.db"
        db_conn = sqlite3.connect(str(db_path))
        repo = PerformanceRepository(db_conn)

        # Read streaming body
        body = b""
        async for chunk in request.stream():
            body += chunk

        # Parse NDJSON
        lines = body.decode("utf-8").strip().split("\n")

        for line_num, line in enumerate(lines, start=1):
            if not line.strip():
                continue

            try:
                row = json.loads(line)

                # Track date range
                date = row.get("date") or row.get("metric_date")
                if date:
                    if min_date is None or date < min_date:
                        min_date = date
                    if max_date is None or date > max_date:
                        max_date = date

                # Track spend
                spend = row.get("spend", 0)
                if isinstance(spend, str):
                    spend = float(spend.replace("$", "").replace(",", ""))
                total_spend += float(spend)

                batch.append(row)
                total_processed += 1

                # Process batch when full
                if len(batch) >= BATCH_SIZE:
                    try:
                        count = repo.insert_batch(batch)
                        total_imported += count
                        batch_count += 1
                    except Exception as e:
                        logger.warning(f"Batch insert failed: {e}")
                        total_skipped += len(batch)
                        errors.append({
                            "batch": batch_count + 1,
                            "error": str(e),
                            "rows_affected": len(batch),
                        })
                    batch = []

            except json.JSONDecodeError as e:
                total_skipped += 1
                if len(errors) < 50:  # Limit error collection
                    errors.append({
                        "line": line_num,
                        "error": f"Invalid JSON: {str(e)}",
                        "data": line[:100] if len(line) > 100 else line,
                    })
            except Exception as e:
                total_skipped += 1
                if len(errors) < 50:
                    errors.append({
                        "line": line_num,
                        "error": str(e),
                    })

        # Process remaining batch
        if batch:
            try:
                count = repo.insert_batch(batch)
                total_imported += count
                batch_count += 1
            except Exception as e:
                logger.warning(f"Final batch insert failed: {e}")
                total_skipped += len(batch)
                errors.append({
                    "batch": batch_count + 1,
                    "error": str(e),
                    "rows_affected": len(batch),
                })

        db_conn.close()

        return StreamingImportResult(
            status="completed",
            total_rows=total_processed,
            imported=total_imported,
            skipped=total_skipped,
            batches=batch_count,
            errors=errors[:50],
            date_range={"start": min_date, "end": max_date} if min_date else None,
            total_spend=round(total_spend, 2) if total_spend > 0 else None,
        )

    except Exception as e:
        logger.error(f"Streaming import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming import failed: {str(e)}")


class BatchImportRequest(BaseModel):
    """Request for batch import (array of rows)."""

    rows: list[dict]


@app.post("/performance/import/batch", response_model=StreamingImportResult, tags=["Performance"])
async def import_performance_batch(
    request: BatchImportRequest,
):
    """
    Batch import endpoint for chunked uploads.

    Writes directly to the unified rtb_daily table.

    This is used by the frontend chunked uploader which sends
    batches of ~10,000 rows at a time.

    Example request:
    ```json
    {
      "rows": [
        {"creative_id":"79783","date":"2025-11-29","impressions":1000,"clicks":50,"spend":25.50,"geography":"US"},
        {"creative_id":"79784","date":"2025-11-29","impressions":500,"clicks":10,"spend":5.00,"geography":"BR"}
      ]
    }
    ```
    """
    import sqlite3
    import hashlib
    from pathlib import Path

    try:
        db_path = Path.home() / ".catscan" / "catscan.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Track stats
        min_date: Optional[str] = None
        max_date: Optional[str] = None
        total_spend = 0.0
        imported = 0
        skipped = 0

        for row in request.rows:
            try:
                # Parse date
                date = row.get("date") or row.get("metric_date")
                if not date:
                    skipped += 1
                    continue

                if min_date is None or date < min_date:
                    min_date = date
                if max_date is None or date > max_date:
                    max_date = date

                # Parse spend
                spend = row.get("spend", 0)
                if isinstance(spend, str):
                    spend = float(spend.replace("$", "").replace(",", ""))
                spend_micros = int(float(spend) * 1_000_000)
                total_spend += float(spend)

                # Parse integers
                impressions = int(row.get("impressions", 0) or 0)
                clicks = int(row.get("clicks", 0) or 0)
                reached = int(row.get("reached_queries", 0) or 0)

                # Get geography and device_type
                geography = row.get("geography") or row.get("country") or None
                device_type = row.get("device_type") or row.get("platform") or None
                placement = row.get("placement") or None
                campaign_id = row.get("campaign_id") or None

                # Insert into performance_metrics (uses unique index for dedup)
                cursor.execute("""
                    INSERT OR REPLACE INTO performance_metrics (
                        creative_id, campaign_id, metric_date,
                        impressions, clicks, spend_micros,
                        geography, device_type, placement, reached_queries
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get("creative_id"),
                    campaign_id,
                    date,
                    impressions,
                    clicks,
                    spend_micros,
                    geography,
                    device_type,
                    placement,
                    reached,
                ))

                if cursor.rowcount > 0:
                    imported += 1
                else:
                    skipped += 1  # Duplicate

            except Exception as row_err:
                logger.warning(f"Row error: {row_err}")
                skipped += 1
                continue

        conn.commit()
        conn.close()

        return StreamingImportResult(
            status="completed",
            total_rows=len(request.rows),
            imported=imported,
            skipped=skipped,
            batches=1,
            errors=[],
            date_range={"start": min_date, "end": max_date} if min_date else None,
            total_spend=round(total_spend, 2) if total_spend > 0 else None,
        )

    except Exception as e:
        logger.error(f"Batch import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch import failed: {str(e)}")


# ============================================================
# Phase 11: Evaluation Engine & Troubleshooting API Endpoints
# ============================================================

from analysis.evaluation_engine import EvaluationEngine, RecommendationType


@app.get("/api/evaluation", tags=["Evaluation"])
async def get_evaluation(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
):
    """
    Run evaluation engine and return actionable recommendations.

    Phase 11: Decision Intelligence
    Combines all data sources (CSV, API, troubleshooting) to produce
    prioritized recommendations for QPS optimization.
    """
    engine = EvaluationEngine()
    results = engine.run_full_evaluation(days)

    # Convert Recommendation dataclasses to dicts for JSON
    results["recommendations"] = [r.to_dict() for r in results["recommendations"]]

    return results


@app.get("/api/troubleshooting/filtered-bids", tags=["Troubleshooting"])
async def get_filtered_bids(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
):
    """
    Get summary of why bids were filtered.

    Phase 11: RTB Troubleshooting API
    Shows breakdown of filtered bid reasons - the key insight for understanding waste.
    """
    engine = EvaluationEngine()
    return engine.get_filtered_bids_summary(days)


@app.get("/api/troubleshooting/funnel", tags=["Troubleshooting"])
async def get_bid_funnel(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
):
    """
    Get bid funnel metrics - from bids submitted to impressions won.

    Phase 11: RTB Troubleshooting API
    Shows the conversion funnel from bid requests to wins.
    """
    engine = EvaluationEngine()
    return engine.get_bid_funnel(days)


@app.post("/api/troubleshooting/collect", tags=["Troubleshooting"])
async def trigger_troubleshooting_collection(
    days: int = Query(7, ge=1, le=30, description="Days of data to collect"),
    environment: Optional[str] = Query(None, description="Filter by APP or WEB"),
    background_tasks: BackgroundTasks = None,
):
    """
    Trigger troubleshooting data collection from Google API.

    Phase 11: RTB Troubleshooting API
    Fetches filtered bid reasons, bid metrics, and callout status.
    Requires service account with adexchange.buyer scope.
    """
    # TODO: Implement background collection
    # For now, return a placeholder
    return {
        "status": "collection_queued",
        "days": days,
        "environment": environment,
        "message": "Collection will run in background. Check /api/troubleshooting/filtered-bids after a few minutes."
    }


# =============================================================================
# Phase 25: Recommendation Engine Endpoints
# =============================================================================

@app.get("/recommendations", response_model=list[RecommendationResponse], tags=["Recommendations"])
async def get_recommendations(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    min_severity: str = Query("low", description="Minimum severity: low, medium, high, critical"),
    store: SQLiteStore = Depends(get_store),
):
    """
    Get actionable optimization recommendations.

    Phase 25: Core Analytics Engine
    Returns recommendations sorted by impact (highest wasted QPS first).
    """
    from analytics.recommendation_engine import RecommendationEngine, Severity

    try:
        severity_map = {
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }
        min_sev = severity_map.get(min_severity.lower(), Severity.LOW)

        engine = RecommendationEngine(store)
        recommendations = await engine.generate_recommendations(days=days, min_severity=min_sev)

        return [rec.to_dict() for rec in recommendations]
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommendations/summary", response_model=RecommendationSummaryResponse, tags=["Recommendations"])
async def get_recommendations_summary(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    store: SQLiteStore = Depends(get_store),
):
    """
    Get high-level waste summary with recommendation counts.

    Phase 25: Core Analytics Engine
    Returns summary metrics including total waste and recommendation breakdown.
    """
    from analytics.recommendation_engine import RecommendationEngine

    try:
        engine = RecommendationEngine(store)
        summary = await engine.get_summary(days=days)
        return summary
    except Exception as e:
        logger.error(f"Failed to get recommendations summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommendations/{recommendation_id}/resolve", tags=["Recommendations"])
async def resolve_recommendation(
    recommendation_id: str,
    notes: Optional[str] = Query(None, description="Resolution notes"),
    store: SQLiteStore = Depends(get_store),
):
    """
    Mark a recommendation as resolved.

    Phase 25: Core Analytics Engine
    Updates the recommendation status and records resolution notes.
    """
    from analytics.recommendation_engine import RecommendationEngine

    try:
        engine = RecommendationEngine(store)
        success = await engine.resolve_recommendation(recommendation_id, notes)

        if not success:
            raise HTTPException(status_code=404, detail="Recommendation not found")

        return {"status": "resolved", "id": recommendation_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommendations/by-type/{rec_type}", response_model=list[RecommendationResponse], tags=["Recommendations"])
async def get_recommendations_by_type(
    rec_type: str,
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
    store: SQLiteStore = Depends(get_store),
):
    """
    Get recommendations filtered by type.

    Phase 25: Core Analytics Engine
    Types: size_mismatch, config_inefficiency, publisher_block, app_block,
           geo_exclusion, creative_pause, creative_review, fraud_alert
    """
    from analytics.recommendation_engine import RecommendationEngine, Severity

    try:
        engine = RecommendationEngine(store)
        recommendations = await engine.generate_recommendations(days=days, min_severity=Severity.LOW)

        filtered = [rec for rec in recommendations if rec.type.value == rec_type]
        return [rec.to_dict() for rec in filtered]
    except Exception as e:
        logger.error(f"Failed to get recommendations by type: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# QPS Analytics Endpoints (Phase 27)
# =============================================================================

from analytics.size_coverage_analyzer import SizeCoverageAnalyzer
from analytics.geo_waste_analyzer import GeoWasteAnalyzer
from analytics.pretargeting_recommender import PretargetingRecommender

# Database path for QPS analytics
QPS_DB_PATH = Path.home() / ".catscan" / "catscan.db"


@app.get("/analytics/size-coverage", tags=["QPS Analytics"])
async def get_size_coverage(days: int = Query(7, ge=1, le=90)):
    """
    Analyze size coverage gaps.

    Returns sizes receiving traffic but missing creatives.
    This is the core Cat-Scan analysis for identifying QPS waste.
    """
    try:
        analyzer = SizeCoverageAnalyzer(str(QPS_DB_PATH))
        summary = analyzer.analyze(days)
        return {
            "period_days": days,
            "total_sizes_in_traffic": summary.total_sizes_in_traffic,
            "sizes_with_creatives": summary.sizes_with_creatives,
            "sizes_without_creatives": summary.sizes_without_creatives,
            "coverage_rate_pct": round(summary.coverage_rate, 1),
            "wasted_queries_daily": summary.wasted_queries_daily,
            "wasted_qps": round(summary.wasted_qps, 2),
            "gaps": [
                {
                    "size": g.size,
                    "format": g.format,
                    "queries_received": g.queries_received,
                    "daily_estimate": g.estimated_daily_queries,
                    "percent_of_traffic": round(g.percent_of_total_traffic, 1),
                    "recommendation": g.recommendation,
                }
                for g in summary.gaps[:20]  # Top 20 gaps
            ],
            "covered_sizes": [
                {
                    "size": s["size"],
                    "format": s["format"],
                    "impressions": s["impressions"],
                    "spend_usd": round(s["spend_usd"], 2),
                    "creative_count": s["creative_count"],
                    "ctr_pct": round(s["ctr"], 2),
                }
                for s in summary.covered_sizes[:20]  # Top 20 covered
            ],
        }
    except Exception as e:
        logger.error(f"Failed to analyze size coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/geo-waste", tags=["QPS Analytics"])
async def get_geo_waste(days: int = Query(7, ge=1, le=90)):
    """
    Analyze geographic QPS waste.

    Returns geos with poor performance that should be excluded from pretargeting.
    """
    try:
        analyzer = GeoWasteAnalyzer(str(QPS_DB_PATH))
        summary = analyzer.analyze(days)
        return {
            "period_days": days,
            "total_geos": summary.total_geos,
            "geos_with_traffic": summary.geos_with_traffic,
            "geos_to_exclude": summary.geos_to_exclude,
            "geos_to_monitor": summary.geos_to_monitor,
            "geos_performing_well": summary.geos_performing_well,
            "estimated_waste_pct": round(summary.estimated_waste_pct, 1),
            "total_spend_usd": round(summary.total_spend_usd, 2),
            "wasted_spend_usd": round(summary.wasted_spend_usd, 2),
            "geos": [
                {
                    "country": g.country_name,
                    "code": g.country_code,
                    "impressions": g.impressions,
                    "clicks": g.clicks,
                    "spend_usd": round(g.spend_usd, 2),
                    "ctr_pct": round(g.ctr, 2),
                    "cpm": round(g.cpm, 2),
                    "creative_count": g.creative_count,
                    "recommendation": g.recommendation,
                }
                for g in summary.geo_breakdown
            ],
        }
    except Exception as e:
        logger.error(f"Failed to analyze geo waste: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/pretargeting-recommendations", tags=["QPS Analytics"])
async def get_pretargeting_recommendations(
    days: int = Query(7, ge=1, le=90),
    max_configs: int = Query(10, ge=1, le=10),
):
    """
    Generate optimal pretargeting configurations.

    Given the 10-config limit, recommends how to configure them for
    maximum QPS efficiency.
    """
    try:
        recommender = PretargetingRecommender(str(QPS_DB_PATH))
        recommendation = recommender.generate_recommendations(days, max_configs)
        return {
            "config_limit": recommendation.config_limit,
            "summary": recommendation.summary,
            "total_waste_reduction_pct": round(recommendation.total_estimated_waste_reduction_pct, 1),
            "configs": [
                recommender.get_config_as_json(config)
                for config in recommendation.configs
            ],
        }
    except Exception as e:
        logger.error(f"Failed to generate pretargeting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/qps-summary", tags=["QPS Analytics"])
async def get_qps_summary(days: int = Query(7, ge=1, le=90)):
    """
    High-level QPS efficiency summary.

    Combines size coverage and geo waste analysis into a single dashboard view.
    """
    try:
        size_analyzer = SizeCoverageAnalyzer(str(QPS_DB_PATH))
        geo_analyzer = GeoWasteAnalyzer(str(QPS_DB_PATH))

        size_summary = size_analyzer.analyze(days)
        geo_summary = geo_analyzer.analyze(days)

        # Calculate total estimated waste
        # Size gaps are 100% waste, geo waste is partial
        size_waste_pct = 100 - size_summary.coverage_rate if size_summary.coverage_rate > 0 else 0

        return {
            "period_days": days,
            "size_coverage": {
                "coverage_rate_pct": round(size_summary.coverage_rate, 1),
                "sizes_covered": size_summary.sizes_with_creatives,
                "sizes_missing": size_summary.sizes_without_creatives,
                "wasted_qps": round(size_summary.wasted_qps, 2),
            },
            "geo_efficiency": {
                "geos_analyzed": geo_summary.total_geos,
                "geos_to_exclude": geo_summary.geos_to_exclude,
                "geos_to_monitor": geo_summary.geos_to_monitor,
                "waste_pct": round(geo_summary.estimated_waste_pct, 1),
                "wasted_spend_usd": round(geo_summary.wasted_spend_usd, 2),
            },
            "action_items": {
                "sizes_to_block": len([g for g in size_summary.gaps if g.recommendation == "BLOCK_IN_PRETARGETING"]),
                "sizes_to_consider": len([g for g in size_summary.gaps if g.recommendation == "CONSIDER_ADDING_CREATIVE"]),
                "geos_to_exclude": geo_summary.geos_to_exclude,
            },
            "estimated_savings": {
                "geo_waste_monthly_usd": round(geo_summary.wasted_spend_usd * 30 / max(days, 1), 2),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get QPS summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/geo-pretargeting-config", tags=["QPS Analytics"])
async def get_geo_pretargeting_config(days: int = Query(7, ge=1, le=90)):
    """
    Get ready-to-use geo configuration for pretargeting.

    Returns include and exclude lists for geo targeting.
    """
    try:
        analyzer = GeoWasteAnalyzer(str(QPS_DB_PATH))
        config = analyzer.get_pretargeting_geo_config(days)
        return {
            "period_days": days,
            "include_geos": config["include"],
            "exclude_geos": config["exclude"],
            "estimated_monthly_savings_usd": round(config["estimated_savings_usd"] * 30 / max(days, 1), 2),
        }
    except Exception as e:
        logger.error(f"Failed to get geo pretargeting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# RTB Funnel Analytics Endpoints (Phase 28)
# =============================================================================

from analytics.rtb_funnel_analyzer import RTBFunnelAnalyzer


@app.get("/analytics/spend-stats", tags=["RTB Analytics"])
async def get_spend_stats(days: int = Query(7, ge=1, le=90)):
    """
    Get overall spend statistics for the selected period.

    Returns total spend, impressions, and avg CPM from rtb_daily table.
    """
    try:
        conn = sqlite3.connect(str(QPS_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros
            FROM rtb_daily
            WHERE metric_date >= date('now', ?)
        """, (f'-{days} days',))

        row = cursor.fetchone()
        conn.close()

        total_impressions = row[0] if row else 0
        total_spend_micros = row[1] if row else 0
        total_spend_usd = total_spend_micros / 1_000_000

        # Calculate CPM: (spend / impressions) * 1000
        avg_cpm = None
        if total_impressions > 0 and total_spend_micros > 0:
            avg_cpm = (total_spend_usd / total_impressions) * 1000

        return {
            "period_days": days,
            "total_impressions": total_impressions,
            "total_spend_usd": round(total_spend_usd, 2),
            "avg_cpm_usd": round(avg_cpm, 2) if avg_cpm else None,
            "has_spend_data": total_spend_micros > 0,
        }
    except Exception as e:
        logger.error(f"Failed to get spend stats: {e}")
        return {
            "period_days": days,
            "total_impressions": 0,
            "total_spend_usd": 0,
            "avg_cpm_usd": None,
            "has_spend_data": False,
        }


@app.get("/analytics/rtb-funnel", tags=["RTB Analytics"])
async def get_rtb_funnel():
    """
    Get RTB funnel analysis from Google Authorized Buyers data.

    Parses the bidding metrics CSVs to provide:
    - Funnel summary: Bid Requests → Reached Queries → Impressions
    - Publisher performance with win rates
    - Geographic breakdown
    - Creative-level metrics
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        return analyzer.get_full_analysis()
    except Exception as e:
        logger.error(f"Failed to get RTB funnel data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/rtb-funnel/publishers", tags=["RTB Analytics"])
async def get_rtb_publishers(limit: int = Query(30, ge=1, le=100)):
    """
    Get publisher performance breakdown.

    Shows win rates and pretargeting filter rates by publisher.
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        return {
            "publishers": analyzer.get_publisher_performance(limit=limit),
            "count": len(analyzer._publishers) if analyzer._data_loaded else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get publisher performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/rtb-funnel/geos", tags=["RTB Analytics"])
async def get_rtb_geos(limit: int = Query(30, ge=1, le=100)):
    """
    Get geographic performance breakdown.

    Shows win rates and auction participation by country.
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        return {
            "geos": analyzer.get_geo_performance(limit=limit),
            "count": len(analyzer._geos) if analyzer._data_loaded else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get geo performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Phase 29: Multi-View Waste Analysis Endpoints
# =============================================================================


@app.get("/analytics/rtb-funnel/configs", tags=["RTB Analytics"])
async def get_config_performance(
    days: int = Query(7, ge=1, le=30),
):
    """
    Get performance breakdown by pretargeting config (billing_id).

    Reads from the rtb_daily table (populated by CSV import) and aggregates
    by billing_id to show:
    - Reached queries and impressions per config
    - Size-level performance within each config
    - Win rate vs waste percentages
    - Settings derived from the data (format, geos, platforms)
    """
    import sqlite3
    import os
    from collections import defaultdict

    db_path = os.path.expanduser("~/.catscan/catscan.db")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query aggregated data by billing_id from rtb_daily
        cursor.execute("""
            SELECT
                billing_id,
                creative_size,
                creative_format,
                country,
                platform,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions
            FROM rtb_daily
            WHERE metric_date >= date('now', ?)
            GROUP BY billing_id, creative_size, creative_format, country, platform
            ORDER BY total_reached DESC
        """, (f'-{days} days',))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            # No data in database
            return {
                "period_days": days,
                "data_source": "database",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
            }

        # Aggregate by billing_id
        configs_by_billing: dict = defaultdict(lambda: {
            "reached": 0,
            "impressions": 0,
            "sizes": defaultdict(lambda: {"reached": 0, "impressions": 0}),
            "formats": set(),
            "countries": set(),
            "platforms": set(),
        })

        for row in rows:
            billing_id = row["billing_id"]
            config = configs_by_billing[billing_id]
            config["reached"] += row["total_reached"] or 0
            config["impressions"] += row["total_impressions"] or 0

            # Track size breakdown
            size = row["creative_size"] or "unknown"
            config["sizes"][size]["reached"] += row["total_reached"] or 0
            config["sizes"][size]["impressions"] += row["total_impressions"] or 0

            # Track settings
            if row["creative_format"]:
                config["formats"].add(row["creative_format"])
            if row["country"]:
                config["countries"].add(row["country"])
            if row["platform"]:
                config["platforms"].add(row["platform"])

        # Convert to response format
        configs = []
        total_reached = 0
        total_impressions = 0

        for billing_id, config in sorted(configs_by_billing.items(), key=lambda x: x[1]["reached"], reverse=True):
            reached = config["reached"]
            impressions = config["impressions"]
            win_rate = (impressions / reached * 100) if reached > 0 else 0
            waste = 100 - win_rate

            total_reached += reached
            total_impressions += impressions

            # Convert sizes dict to list
            sizes_list = []
            for size, size_data in sorted(config["sizes"].items(), key=lambda x: x[1]["reached"], reverse=True):
                size_reached = size_data["reached"]
                size_impressions = size_data["impressions"]
                size_win = (size_impressions / size_reached * 100) if size_reached > 0 else 0
                sizes_list.append({
                    "size": size,
                    "reached": size_reached,
                    "impressions": size_impressions,
                    "win_rate_pct": round(size_win, 1),
                    "waste_pct": round(100 - size_win, 1),
                })

            # Determine format from collected formats
            formats = list(config["formats"])
            primary_format = formats[0] if formats else "BANNER"

            configs.append({
                "billing_id": billing_id,
                "name": f"Config {billing_id}",
                "reached": reached,
                "bids": 0,  # Not available in current schema
                "impressions": impressions,
                "win_rate_pct": round(win_rate, 1),
                "waste_pct": round(waste, 1),
                "settings": {
                    "format": primary_format,
                    "geos": sorted(list(config["countries"]))[:10],
                    "platforms": sorted(list(config["platforms"])),
                    "qps_limit": None,
                    "budget_usd": None,
                },
                "sizes": sizes_list[:5],
            })

        overall_win = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        return {
            "period_days": days,
            "data_source": "database",
            "configs": configs[:20],
            "total_reached": total_reached,
            "total_impressions": total_impressions,
            "overall_win_rate_pct": round(overall_win, 1),
            "overall_waste_pct": round(100 - overall_win, 1),
        }

    except Exception as e:
        logger.error(f"Failed to get config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/rtb-funnel/configs/{billing_id}/breakdown", tags=["RTB Analytics"])
async def get_config_breakdown(
    billing_id: str,
    by: str = Query("size", regex="^(size|geo|publisher|creative)$"),
    days: int = Query(7, ge=1, le=30),
):
    """
    Get detailed breakdown for a specific pretargeting config.

    Breakdown types:
    - size: By creative size (300x250, 320x50, etc.)
    - geo: By country/region
    - publisher: By app/publisher
    - creative: By individual creative ID
    """
    import sqlite3
    import os
    from collections import defaultdict

    db_path = os.path.expanduser("~/.catscan/catscan.db")

    # Map breakdown type to column
    column_map = {
        "size": "creative_size",
        "geo": "country",
        "publisher": "app_name",
        "creative": "creative_id",
    }
    group_col = column_map.get(by, "creative_size")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query aggregated data for this billing_id
        cursor.execute(f"""
            SELECT
                {group_col} as name,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions
            FROM rtb_daily
            WHERE billing_id = ?
              AND metric_date >= date('now', ?)
              AND {group_col} IS NOT NULL
              AND {group_col} != ''
            GROUP BY {group_col}
            ORDER BY total_reached DESC
            LIMIT 50
        """, (billing_id, f'-{days} days'))

        rows = cursor.fetchall()
        conn.close()

        breakdown = []
        for row in rows:
            reached = row["total_reached"] or 0
            impressions = row["total_impressions"] or 0
            win_rate = (impressions / reached * 100) if reached > 0 else 0
            waste_rate = 100 - win_rate

            breakdown.append({
                "name": row["name"] or "Unknown",
                "reached": reached,
                "win_rate": round(win_rate, 1),
                "waste_rate": round(waste_rate, 1),
            })

        return {
            "billing_id": billing_id,
            "breakdown_by": by,
            "breakdown": breakdown,
        }

    except Exception as e:
        logger.error(f"Failed to get config breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/rtb-funnel/creatives", tags=["RTB Analytics"])
async def get_creative_win_performance(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get creative performance using WIN RATE metrics.

    Shows: reached, bids, impressions won, win rate, waste
    NOT: clicks, CTR, conversions (that's media buyer's job)

    Status classification:
    - great: >50% win rate
    - ok: 20-50% win rate
    - review: <20% win rate
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        result = analyzer.get_creative_win_performance(limit=limit)
        result["period_days"] = days
        return result
    except Exception as e:
        logger.error(f"Failed to get creative win performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Gmail Import Endpoints
# ============================================================================


class GmailStatusResponse(BaseModel):
    """Response model for Gmail import status."""
    configured: bool = Field(description="Whether Gmail OAuth client is configured")
    authorized: bool = Field(description="Whether Gmail is authorized (token exists)")
    last_run: Optional[str] = Field(None, description="ISO timestamp of last import run")
    last_success: Optional[str] = Field(None, description="ISO timestamp of last successful import")
    last_error: Optional[str] = Field(None, description="Error message from last failed run")
    total_imports: int = Field(0, description="Total files imported all time")
    recent_history: list = Field(default_factory=list, description="Recent import history")


class GmailImportResponse(BaseModel):
    """Response model for Gmail import trigger."""
    success: bool
    emails_processed: int = 0
    files_imported: int = 0
    files: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


@app.get("/gmail/status", response_model=GmailStatusResponse, tags=["Gmail Import"])
async def get_gmail_status():
    """
    Get the current Gmail import configuration and status.

    Returns whether Gmail is configured/authorized and the last import results.
    """
    try:
        from scripts.gmail_import import get_status
        status = get_status()
        return GmailStatusResponse(**status)
    except ImportError:
        # Fallback if script not found
        from pathlib import Path
        catscan_dir = Path.home() / '.catscan'
        credentials_dir = catscan_dir / 'credentials'

        return GmailStatusResponse(
            configured=(credentials_dir / 'gmail-oauth-client.json').exists(),
            authorized=(credentials_dir / 'gmail-token.json').exists(),
            total_imports=0,
            recent_history=[]
        )
    except Exception as e:
        logger.error(f"Failed to get Gmail status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/gmail/import", response_model=GmailImportResponse, tags=["Gmail Import"])
async def trigger_gmail_import(background_tasks: BackgroundTasks):
    """
    Trigger a manual Gmail import.

    Checks Gmail for new report emails and imports any found CSVs.
    This is the same operation that runs via cron.
    """
    try:
        from scripts.gmail_import import run_import, get_status

        # Check if configured first
        status = get_status()
        if not status.get("configured"):
            raise HTTPException(
                status_code=400,
                detail="Gmail not configured. Upload gmail-oauth-client.json to ~/.catscan/credentials/"
            )

        if not status.get("authorized"):
            raise HTTPException(
                status_code=400,
                detail="Gmail not authorized. Run the import script manually first to complete OAuth flow."
            )

        # Run the import (synchronously for now, could be background task)
        result = run_import(verbose=False)

        return GmailImportResponse(
            success=result.get("success", False),
            emails_processed=result.get("emails_processed", 0),
            files_imported=result.get("files_imported", 0),
            files=result.get("files", []),
            errors=result.get("errors", [])
        )

    except ImportError as e:
        logger.error(f"Gmail import script not found: {e}")
        raise HTTPException(
            status_code=500,
            detail="Gmail import script not available. Check scripts/gmail_import.py"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Retention Settings API
# ============================================================================


class RetentionConfigRequest(BaseModel):
    """Request model for updating retention configuration."""
    raw_retention_days: int = Field(..., ge=7, le=365, description="Days to keep raw data")
    summary_retention_days: int = Field(..., ge=-1, le=3650, description="Days to keep summaries (-1 = forever)")
    auto_aggregate_after_days: int = Field(30, ge=1, le=90, description="Days before auto-aggregation")


class RetentionConfigResponse(BaseModel):
    """Response model for retention configuration."""
    raw_retention_days: int
    summary_retention_days: int
    auto_aggregate_after_days: int


class StorageStatsResponse(BaseModel):
    """Response model for storage statistics."""
    raw_rows: int
    raw_earliest_date: Optional[str]
    raw_latest_date: Optional[str]
    summary_rows: int
    summary_earliest_date: Optional[str]
    summary_latest_date: Optional[str]


class RetentionJobResponse(BaseModel):
    """Response model for retention job results."""
    aggregated_rows: int
    deleted_raw_rows: int
    deleted_summary_rows: int = 0


@app.get("/retention/config", response_model=RetentionConfigResponse, tags=["Retention"])
async def get_retention_config():
    """Get current retention configuration."""
    from pathlib import Path
    from storage.retention_manager import RetentionManager

    db_path = Path.home() / ".catscan" / "catscan.db"
    if not db_path.exists():
        # Return defaults if no database
        return RetentionConfigResponse(
            raw_retention_days=90,
            summary_retention_days=365,
            auto_aggregate_after_days=30,
        )

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        manager = RetentionManager(conn)
        config = manager.get_retention_config()
        conn.close()

        return RetentionConfigResponse(
            raw_retention_days=config.get('raw_retention_days', 90),
            summary_retention_days=config.get('summary_retention_days', 365),
            auto_aggregate_after_days=config.get('auto_aggregate_after_days', 30),
        )
    except Exception as e:
        logger.error(f"Failed to get retention config: {e}")
        # Return defaults on error
        return RetentionConfigResponse(
            raw_retention_days=90,
            summary_retention_days=365,
            auto_aggregate_after_days=30,
        )


@app.post("/retention/config", response_model=RetentionConfigResponse, tags=["Retention"])
async def set_retention_config(request: RetentionConfigRequest):
    """Update retention configuration."""
    from pathlib import Path
    from storage.retention_manager import RetentionManager

    db_path = Path.home() / ".catscan" / "catscan.db"
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)

        # Ensure retention_config table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retention_config (
                id INTEGER PRIMARY KEY,
                seat_id INTEGER,
                raw_retention_days INTEGER NOT NULL DEFAULT 90,
                summary_retention_days INTEGER NOT NULL DEFAULT 365,
                auto_aggregate_after_days INTEGER NOT NULL DEFAULT 30,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(seat_id)
            )
        """)
        conn.commit()

        manager = RetentionManager(conn)
        manager.set_retention_config(
            raw_retention_days=request.raw_retention_days,
            summary_retention_days=request.summary_retention_days,
            auto_aggregate_after_days=request.auto_aggregate_after_days,
        )
        conn.close()

        return RetentionConfigResponse(
            raw_retention_days=request.raw_retention_days,
            summary_retention_days=request.summary_retention_days,
            auto_aggregate_after_days=request.auto_aggregate_after_days,
        )
    except Exception as e:
        logger.error(f"Failed to set retention config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save retention config: {str(e)}")


@app.get("/retention/stats", response_model=StorageStatsResponse, tags=["Retention"])
async def get_storage_stats():
    """Get storage statistics for performance data."""
    from pathlib import Path
    from storage.retention_manager import RetentionManager

    db_path = Path.home() / ".catscan" / "catscan.db"
    if not db_path.exists():
        return StorageStatsResponse(
            raw_rows=0,
            raw_earliest_date=None,
            raw_latest_date=None,
            summary_rows=0,
            summary_earliest_date=None,
            summary_latest_date=None,
        )

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)

        # Ensure daily_creative_summary table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_creative_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seat_id INTEGER,
                creative_id TEXT NOT NULL,
                date DATE NOT NULL,
                total_queries INTEGER DEFAULT 0,
                total_impressions INTEGER DEFAULT 0,
                total_clicks INTEGER DEFAULT 0,
                total_spend REAL DEFAULT 0,
                win_rate REAL,
                ctr REAL,
                cpm REAL,
                unique_geos INTEGER DEFAULT 0,
                unique_apps INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(seat_id, creative_id, date)
            )
        """)
        conn.commit()

        manager = RetentionManager(conn)
        stats = manager.get_storage_stats()
        conn.close()

        return StorageStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        return StorageStatsResponse(
            raw_rows=0,
            raw_earliest_date=None,
            raw_latest_date=None,
            summary_rows=0,
            summary_earliest_date=None,
            summary_latest_date=None,
        )


@app.post("/retention/run", response_model=RetentionJobResponse, tags=["Retention"])
async def run_retention_job():
    """Run the retention job to aggregate and clean up old data."""
    from pathlib import Path
    from storage.retention_manager import RetentionManager

    db_path = Path.home() / ".catscan" / "catscan.db"
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)

        # Ensure required tables exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retention_config (
                id INTEGER PRIMARY KEY,
                seat_id INTEGER,
                raw_retention_days INTEGER NOT NULL DEFAULT 90,
                summary_retention_days INTEGER NOT NULL DEFAULT 365,
                auto_aggregate_after_days INTEGER NOT NULL DEFAULT 30,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(seat_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_creative_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seat_id INTEGER,
                creative_id TEXT NOT NULL,
                date DATE NOT NULL,
                total_queries INTEGER DEFAULT 0,
                total_impressions INTEGER DEFAULT 0,
                total_clicks INTEGER DEFAULT 0,
                total_spend REAL DEFAULT 0,
                win_rate REAL,
                ctr REAL,
                cpm REAL,
                unique_geos INTEGER DEFAULT 0,
                unique_apps INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(seat_id, creative_id, date)
            )
        """)
        conn.commit()

        manager = RetentionManager(conn)
        result = manager.run_retention_job()
        conn.close()

        return RetentionJobResponse(**result)
    except Exception as e:
        logger.error(f"Failed to run retention job: {e}")
        raise HTTPException(status_code=500, detail=f"Retention job failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
