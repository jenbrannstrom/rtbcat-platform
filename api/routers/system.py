"""System and Thumbnails router for Cat-Scan Creative Intelligence.

This module provides system status and thumbnail management endpoints.
"""

import logging
import os
import json
from pathlib import Path

from storage.postgres_database import pg_execute, pg_query, pg_query_one
from typing import Literal, Optional

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


class ReportTableCompletenessState(BaseModel):
    rows: int
    active_days: int
    expected_days: int
    coverage_pct: float
    max_metric_date: Optional[str] = None
    availability_state: str


class ReportCompletenessSummary(BaseModel):
    expected_report_types: int
    available_report_types: int
    coverage_pct: float
    missing_report_types: list[str]
    availability_state: str
    tables: dict[str, ReportTableCompletenessState]


class QualityFreshnessSummary(BaseModel):
    rows: int
    max_metric_date: Optional[str] = None
    age_days: Optional[int] = None
    fresh_within_days: int
    availability_state: str


class BidstreamDimensionCoverageSummary(BaseModel):
    total_rows: int
    platform_missing_pct: float
    environment_missing_pct: float
    transaction_type_missing_pct: float
    availability_state: str


class SeatDayCompletenessRow(BaseModel):
    metric_date: Optional[str] = None
    buyer_account_id: str
    has_rtb_daily: bool
    has_rtb_bidstream: bool
    has_rtb_bid_filtering: bool
    has_rtb_quality: bool
    has_web_domain_daily: bool
    available_report_types: int
    expected_report_types: int
    completeness_pct: float
    availability_state: str
    refreshed_at: Optional[str] = None


class SeatDayCompletenessSummary(BaseModel):
    total_seat_days: int
    healthy_seat_days: int
    degraded_seat_days: int
    unavailable_seat_days: int
    avg_completeness_pct: float
    min_completeness_pct: float
    max_completeness_pct: float


class SeatDayCompletenessPayload(BaseModel):
    rows: list[SeatDayCompletenessRow]
    summary: SeatDayCompletenessSummary
    availability_state: str
    refreshed_at: Optional[str] = None


class OptimizerReadinessSummary(BaseModel):
    report_completeness: ReportCompletenessSummary
    rtb_quality_freshness: QualityFreshnessSummary
    bidstream_dimension_coverage: BidstreamDimensionCoverageSummary
    seat_day_completeness: SeatDayCompletenessPayload


class DataHealthResponse(BaseModel):
    checked_at: str
    days: int
    buyer_id: Optional[str] = None
    state: str
    source_freshness: DataHealthSourceFreshness
    serving_freshness: DataHealthServingFreshness
    coverage: DataCoverageSummary
    ingestion_runs: IngestionRunsSummary
    optimizer_readiness: OptimizerReadinessSummary


class UiPageLoadMetricRecordRequest(BaseModel):
    page: Literal["qps_home"]
    buyer_id: Optional[str] = None
    selected_days: Optional[int] = Field(None, ge=1, le=365)
    time_to_first_table_row_ms: Optional[float] = Field(None, ge=0, le=600000)
    time_to_table_hydrated_ms: Optional[float] = Field(None, ge=0, le=600000)
    api_latency_ms: dict[str, float] = Field(default_factory=dict)
    sampled_at: Optional[str] = None


class UiPageLoadMetricRecordResponse(BaseModel):
    status: str


class UiPageLoadMetricSample(BaseModel):
    sampled_at: str
    buyer_id: Optional[str] = None
    selected_days: Optional[int] = None
    time_to_first_table_row_ms: Optional[float] = None
    time_to_table_hydrated_ms: Optional[float] = None
    api_latency_ms: dict[str, float] = Field(default_factory=dict)


class UiPageLoadMetricSummaryResponse(BaseModel):
    page: Literal["qps_home"]
    buyer_id: Optional[str] = None
    since_hours: int
    sample_count: int
    p50_first_table_row_ms: Optional[float] = None
    p95_first_table_row_ms: Optional[float] = None
    p50_table_hydrated_ms: Optional[float] = None
    p95_table_hydrated_ms: Optional[float] = None
    last_sampled_at: Optional[str] = None
    latest_samples: list[UiPageLoadMetricSample] = Field(default_factory=list)


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
    availability_state: Optional[Literal["healthy", "degraded", "unavailable"]] = Query(
        None, description="Filter seat-day completeness rows by state"
    ),
    min_completeness_pct: Optional[float] = Query(
        None, ge=0.0, le=100.0, description="Filter seat-day completeness rows by minimum completeness percent"
    ),
    limit: int = Query(200, ge=1, le=1000),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get source/serving freshness and dimension coverage state."""
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    service = DataHealthService()
    return DataHealthResponse(
        **await service.get_data_health(
            days=days,
            buyer_id=buyer_id,
            availability_state=availability_state,
            min_completeness_pct=min_completeness_pct,
            limit=limit,
        )
    )


@router.post("/system/ui-metrics/page-load", response_model=UiPageLoadMetricRecordResponse)
async def record_ui_page_load_metric(
    payload: UiPageLoadMetricRecordRequest,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Record client-side UI page-load telemetry for SLO monitoring."""
    buyer_id = await resolve_buyer_id(payload.buyer_id, store=store, user=user)
    sanitized_api_latency: dict[str, float] = {}
    for key, raw_value in (payload.api_latency_ms or {}).items():
        if not key:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value < 0 or value > 600000:
            continue
        sanitized_api_latency[str(key)] = round(value, 2)

    has_primary_metric = (
        payload.time_to_first_table_row_ms is not None
        or payload.time_to_table_hydrated_ms is not None
    )
    if not has_primary_metric and not sanitized_api_latency:
        raise HTTPException(
            status_code=400,
            detail="At least one page-load metric or API latency value is required.",
        )

    await pg_execute(
        """
        INSERT INTO ui_page_load_metrics (
            page_name,
            buyer_id,
            user_id,
            selected_days,
            time_to_first_table_row_ms,
            time_to_table_hydrated_ms,
            api_latency_ms,
            sampled_at,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s::jsonb,
            COALESCE(%s::timestamptz, CURRENT_TIMESTAMP),
            CURRENT_TIMESTAMP
        )
        """,
        (
            payload.page,
            buyer_id,
            str(user.id),
            payload.selected_days,
            payload.time_to_first_table_row_ms,
            payload.time_to_table_hydrated_ms,
            json.dumps(sanitized_api_latency, separators=(",", ":")),
            payload.sampled_at,
        ),
    )
    return UiPageLoadMetricRecordResponse(status="recorded")


@router.get(
    "/system/ui-metrics/page-load/summary",
    response_model=UiPageLoadMetricSummaryResponse,
)
async def get_ui_page_load_metric_summary(
    page: Literal["qps_home"] = Query("qps_home"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    since_hours: int = Query(24, ge=1, le=168),
    latest_limit: int = Query(20, ge=1, le=100),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get percentile summary and recent samples for UI page-load telemetry."""
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)

    conditions = [
        "page_name = %s",
        "sampled_at >= CURRENT_TIMESTAMP - make_interval(hours => %s)",
    ]
    params: list[object] = [page, since_hours]
    if buyer_id:
        conditions.append("buyer_id = %s")
        params.append(buyer_id)

    where_clause = " AND ".join(conditions)
    summary_row = await pg_query_one(
        f"""
        SELECT
            COUNT(*)::bigint AS sample_count,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY time_to_first_table_row_ms)
                FILTER (WHERE time_to_first_table_row_ms IS NOT NULL) AS p50_first_table_row_ms,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY time_to_first_table_row_ms)
                FILTER (WHERE time_to_first_table_row_ms IS NOT NULL) AS p95_first_table_row_ms,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY time_to_table_hydrated_ms)
                FILTER (WHERE time_to_table_hydrated_ms IS NOT NULL) AS p50_table_hydrated_ms,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY time_to_table_hydrated_ms)
                FILTER (WHERE time_to_table_hydrated_ms IS NOT NULL) AS p95_table_hydrated_ms,
            MAX(sampled_at) AS last_sampled_at
        FROM ui_page_load_metrics
        WHERE {where_clause}
        """,
        tuple(params),
    ) or {}

    latest_rows = await pg_query(
        f"""
        SELECT
            sampled_at,
            buyer_id,
            selected_days,
            time_to_first_table_row_ms,
            time_to_table_hydrated_ms,
            api_latency_ms
        FROM ui_page_load_metrics
        WHERE {where_clause}
        ORDER BY sampled_at DESC, id DESC
        LIMIT %s
        """,
        tuple(params + [latest_limit]),
    )

    samples = [
        UiPageLoadMetricSample(
            sampled_at=str(row["sampled_at"]),
            buyer_id=row.get("buyer_id"),
            selected_days=row.get("selected_days"),
            time_to_first_table_row_ms=row.get("time_to_first_table_row_ms"),
            time_to_table_hydrated_ms=row.get("time_to_table_hydrated_ms"),
            api_latency_ms=row.get("api_latency_ms") or {},
        )
        for row in latest_rows
    ]

    return UiPageLoadMetricSummaryResponse(
        page=page,
        buyer_id=buyer_id,
        since_hours=since_hours,
        sample_count=int(summary_row.get("sample_count") or 0),
        p50_first_table_row_ms=summary_row.get("p50_first_table_row_ms"),
        p95_first_table_row_ms=summary_row.get("p95_first_table_row_ms"),
        p50_table_hydrated_ms=summary_row.get("p50_table_hydrated_ms"),
        p95_table_hydrated_ms=summary_row.get("p95_table_hydrated_ms"),
        last_sampled_at=str(summary_row["last_sampled_at"]) if summary_row.get("last_sampled_at") else None,
        latest_samples=samples,
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
    campaign_count: int = 0
    cluster_count: int = 0
    formats: dict[str, int]
    db_path: str = "postgresql"


class SizesResponse(BaseModel):
    """Response model for available creative sizes."""
    sizes: list[str]


class GeoLookupResponse(BaseModel):
    """Response model for geo ID to name mapping."""
    geos: dict[str, str]  # geo_id -> display name


class GeoSearchItemResponse(BaseModel):
    """Searchable geo target result."""

    geo_id: str
    label: str
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    city_name: Optional[str] = None
    type: Literal["country", "city"]


class GeoSearchResponse(BaseModel):
    """Response model for geo target search."""

    results: list[GeoSearchItemResponse]


@router.get("/geos/search", response_model=GeoSearchResponse)
async def search_geo_targets(
    q: str = Query(..., description="Search string for country/city name or geo ID"),
    limit: int = Query(20, ge=1, le=50, description="Max number of matches"),
    type: Literal["all", "country", "city"] = Query(
        "all", description="Filter to country-level, city-level, or both"
    ),
):
    """Search geo criterion targets for adding to pretargeting configs."""
    service = SystemService()
    matches = await service.search_geo_targets(query=q, limit=limit, target_type=type)
    return GeoSearchResponse(
        results=[
            GeoSearchItemResponse(
                geo_id=item["geo_id"],
                label=item["label"],
                country_code=item.get("country_code") or None,
                country_name=item.get("country_name") or None,
                city_name=item.get("city_name") or None,
                type=item["type"],  # type: ignore[arg-type]
            )
            for item in matches
        ]
    )


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
        campaign_count=stats.get("total_campaigns", 0),
        cluster_count=stats.get("total_clusters", 0),
        formats=stats.get("by_format", {}),
        db_path=stats.get("db_path", "postgresql"),
    )


@router.get("/sizes", response_model=SizesResponse)
async def get_sizes(store=Depends(get_store)):
    """Get available creative sizes from the database."""
    sizes = await store.get_available_sizes()
    # PostgresStore currently returns [{canonical_size, size_category, count}]
    # but this endpoint contract is list[str].
    if sizes and isinstance(sizes[0], dict):
        size_values = [
            str(row.get("canonical_size"))
            for row in sizes
            if row.get("canonical_size")
        ]
    else:
        size_values = [str(size) for size in sizes]
    return SizesResponse(sizes=size_values)
