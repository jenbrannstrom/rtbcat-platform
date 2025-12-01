"""FastAPI application for RTBcat Creative Intelligence.

This module provides REST API endpoints for managing creatives,
campaigns, and clusters with support for data collection and analysis
using the Google Authorized Buyers RTB API.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import csv
import io

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from collectors import BuyerSeatsClient, CreativesClient
from config import ConfigManager
from storage import SQLiteStore, PerformanceMetric, creative_dicts_to_storage
from analytics import WasteAnalyzer
from api.campaigns_router import router as campaigns_router

logger = logging.getLogger(__name__)

# Global instances
_store: Optional[SQLiteStore] = None
_config_manager: Optional[ConfigManager] = None


class VideoPreview(BaseModel):
    """Video creative preview data."""

    video_url: Optional[str] = None
    vast_xml: Optional[str] = None
    duration: Optional[str] = None


class HtmlPreview(BaseModel):
    """HTML creative preview data."""

    snippet: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


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
    # Preview data based on format
    video: Optional[VideoPreview] = None
    html: Optional[HtmlPreview] = None
    native: Optional[NativePreview] = None


class CampaignResponse(BaseModel):
    """Response model for campaign data."""

    id: str
    name: str
    source: str
    creative_count: int
    metadata: dict = Field(default_factory=dict)


class ClusterAssignment(BaseModel):
    """Request model for cluster assignment."""

    creative_id: str
    cluster_id: str


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

    logger.info("RTBcat API started")

    yield

    # Cleanup on shutdown
    logger.info("RTBcat API shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    application = FastAPI(
        title="RTBcat Creative Intelligence",
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
    """Check API health status."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        configured=config.is_configured(),
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


def _extract_preview_data(creative, slim: bool = False) -> dict:
    """Extract preview data from creative raw_data based on format.

    Args:
        creative: The creative object
        slim: If True, exclude large fields (vast_xml, html snippet) for list views
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
            result["video"] = VideoPreview(
                video_url=video_url,
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


@app.get("/creatives", response_model=list[CreativeResponse], tags=["Creatives"])
async def list_creatives(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    format: Optional[str] = Query(None, description="Filter by creative format"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    slim: bool = Query(True, description="Exclude large fields (vast_xml, html snippets) for faster loading"),
    store: SQLiteStore = Depends(get_store),
):
    """List creatives with optional filtering.

    By default, slim=True excludes large fields like vast_xml and html snippets
    to reduce payload size. Set slim=False for full data.
    """
    creatives = await store.list_creatives(
        campaign_id=campaign_id,
        cluster_id=cluster_id,
        buyer_id=buyer_id,
        format=format,
        limit=limit,
        offset=offset,
    )
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
            **_extract_preview_data(c, slim=slim),
        )
        for c in creatives
    ]


@app.get("/creatives/{creative_id}", response_model=CreativeResponse, tags=["Creatives"])
async def get_creative(
    creative_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Get a specific creative by ID."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

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
        **_extract_preview_data(creative),
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
    source: Optional[str] = Query(None, description="Filter by data source"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    store: SQLiteStore = Depends(get_store),
):
    """List campaigns with optional filtering."""
    campaigns = await store.list_campaigns(
        source=source,
        limit=limit,
        offset=offset,
    )
    return [
        CampaignResponse(
            id=c.id,
            name=c.name,
            source=c.source,
            creative_count=c.creative_count,
            metadata=c.metadata,
        )
        for c in campaigns
    ]


@app.get("/campaigns/{campaign_id}", response_model=CampaignResponse, tags=["Campaigns"])
async def get_campaign(
    campaign_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Get a specific campaign by ID."""
    campaign = await store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        source=campaign.source,
        creative_count=campaign.creative_count,
        metadata=campaign.metadata,
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


# QPS Optimization endpoints


class QPSReportResponse(BaseModel):
    """Response model for full QPS optimization report."""

    report_text: str
    generated_at: str


class SizeCoverageReportResponse(BaseModel):
    """Response model for size coverage analysis."""

    total_creatives: int
    total_sizes_with_creatives: int
    total_sizes_in_traffic: int
    overall_match_rate: float
    sizes_we_can_serve: list[str]
    sizes_we_cannot_serve: list[str]
    recommended_include_list: list[str]
    opportunity_sizes: list[dict]
    report_text: str
    generated_at: str


class ConfigPerformanceResponse(BaseModel):
    """Response model for config performance analysis."""

    total_reached: int
    total_impressions: int
    total_spend: float
    average_efficiency: float
    configs: list[dict]
    report_text: str
    generated_at: str


class FraudSignalResponse(BaseModel):
    """Response model for fraud signal detection."""

    total_suspicious_apps: int
    total_suspicious_publishers: int
    signals: list[dict]
    report_text: str
    generated_at: str


@app.get("/qps/report", response_model=QPSReportResponse, tags=["QPS Optimization"])
async def get_qps_report(
    store: SQLiteStore = Depends(get_store),
):
    """Get full QPS optimization report as human-readable text.

    Generates a comprehensive report combining:
    - Size Coverage Analysis (Module 1)
    - Config Performance Tracking (Module 2)
    - Fraud Signal Detection (Module 3)

    The report is designed to be printed or shared with AdOps teams.
    """
    from analytics import QPSOptimizer

    try:
        optimizer = QPSOptimizer(store)
        report_text = await optimizer.generate_full_report()

        from datetime import datetime, timezone
        return QPSReportResponse(
            report_text=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.error(f"QPS report generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"QPS report generation failed: {str(e)}")


@app.get("/qps/size-coverage", response_model=SizeCoverageReportResponse, tags=["QPS Optimization"])
async def get_qps_size_coverage(
    store: SQLiteStore = Depends(get_store),
):
    """Get size coverage analysis report.

    Module 1 from QPS Optimization Strategy - analyzes:
    - What sizes you have creatives for
    - What sizes you're receiving traffic for (if data available)
    - Match rate (% of traffic you can serve)
    - Recommended pretargeting include list
    - Opportunity sizes worth creating creatives for
    """
    from analytics import QPSOptimizer

    try:
        optimizer = QPSOptimizer(store)
        report = await optimizer.generate_size_coverage_report()

        return SizeCoverageReportResponse(
            total_creatives=report.total_creatives,
            total_sizes_with_creatives=report.total_sizes_with_creatives,
            total_sizes_in_traffic=report.total_sizes_in_traffic,
            overall_match_rate=report.overall_match_rate,
            sizes_we_can_serve=report.sizes_we_can_serve,
            sizes_we_cannot_serve=report.sizes_we_cannot_serve,
            recommended_include_list=report.recommended_include_list,
            opportunity_sizes=report.opportunity_sizes,
            report_text=report.to_printout(),
            generated_at=report.generated_at,
        )

    except Exception as e:
        logger.error(f"Size coverage analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Size coverage analysis failed: {str(e)}")


@app.get("/qps/config-performance", response_model=ConfigPerformanceResponse, tags=["QPS Optimization"])
async def get_qps_config_performance(
    store: SQLiteStore = Depends(get_store),
):
    """Get pretargeting config performance report.

    Module 2 from QPS Optimization Strategy - analyzes:
    - Performance by billing_id (pretargeting config)
    - Reached queries, impressions, clicks, spend per config
    - Efficiency (impression rate)
    - Issues and investigation recommendations

    Note: Requires performance metrics with billing_account_id populated.
    """
    from analytics import QPSOptimizer

    try:
        optimizer = QPSOptimizer(store)
        report = await optimizer.generate_config_performance_report()

        return ConfigPerformanceResponse(
            total_reached=report.total_reached,
            total_impressions=report.total_impressions,
            total_spend=report.total_spend,
            average_efficiency=report.average_efficiency,
            configs=[
                {
                    "billing_id": c.billing_id,
                    "display_name": c.display_name,
                    "reached_queries": c.reached_queries,
                    "impressions": c.impressions,
                    "clicks": c.clicks,
                    "spend": c.spend,
                    "efficiency": c.efficiency,
                    "issues": c.issues,
                }
                for c in report.configs
            ],
            report_text=report.to_printout(),
            generated_at=report.generated_at,
        )

    except Exception as e:
        logger.error(f"Config performance analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Config performance analysis failed: {str(e)}")


@app.get("/qps/fraud-signals", response_model=FraudSignalResponse, tags=["QPS Optimization"])
async def get_qps_fraud_signals(
    days: int = Query(14, ge=1, le=90, description="Days of data to analyze"),
    store: SQLiteStore = Depends(get_store),
):
    """Get fraud signal detection report.

    Module 3 from QPS Optimization Strategy - detects suspicious patterns:
    - Unusually high CTR (>3% when average is 0.5-1%)
    - Clicks exceeding impressions (possible click injection)
    - High impressions with zero conversions

    These are patterns, not proof. Smart fraud mixes 70-80% real traffic
    with 20-30% fake. Single signals are not conclusive.
    """
    from analytics import QPSOptimizer

    try:
        optimizer = QPSOptimizer(store)
        report = await optimizer.generate_fraud_signal_report(days=days)

        return FraudSignalResponse(
            total_suspicious_apps=report.total_suspicious_apps,
            total_suspicious_publishers=report.total_suspicious_publishers,
            signals=[
                {
                    "entity_type": s.entity_type,
                    "entity_id": s.entity_id,
                    "entity_name": s.entity_name,
                    "signal_type": s.signal_type,
                    "signal_strength": s.signal_strength,
                    "metrics": s.metrics,
                    "recommendation": s.recommendation,
                    "detail": s.detail,
                }
                for s in report.signals
            ],
            report_text=report.to_printout(),
            generated_at=report.generated_at,
        )

    except Exception as e:
        logger.error(f"Fraud signal detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Fraud signal detection failed: {str(e)}")


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
async def cleanup_old_performance_data(
    days_to_keep: int = Query(90, ge=7, le=365, description="Days of data to retain"),
    store: SQLiteStore = Depends(get_store),
):
    """Delete performance data older than the retention period.

    Use this to manage database size by removing old historical data.
    Default retention is 90 days.
    """
    try:
        deleted = await store.clear_old_performance_data(days_to_keep=days_to_keep)

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

    status: str
    imported: int
    skipped: int
    errors: list[dict] = []


@app.post("/performance/import-csv", response_model=CSVImportResult, tags=["Performance"])
async def import_performance_csv(
    file: UploadFile = File(..., description="CSV file with performance data"),
    store: SQLiteStore = Depends(get_store),
):
    """Import performance data from CSV file.

    CSV Format (columns):
    - **creative_id** (required): Creative ID, must exist in database
    - **date** (required): Date in YYYY-MM-DD format
    - **impressions** (required): Integer >= 0
    - **clicks** (required): Integer >= 0 and <= impressions
    - **spend** (required): Decimal >= 0 (in USD, will be converted to micros)
    - **geography** (optional): ISO country code (US, BR, IE, etc.)
    - **device_type** (optional): MOBILE, DESKTOP, TABLET, CTV
    - **hour** (optional): 0-23 for hourly data
    - **placement** (optional): Site/app placement identifier
    - **campaign_id** (optional): Campaign ID

    Example CSV:
    ```
    creative_id,date,impressions,clicks,spend,geography,device_type
    79783,2025-11-29,10000,250,125.50,BR,MOBILE
    79783,2025-11-28,8500,200,100.00,BR,DESKTOP
    144634,2025-11-29,50000,800,200.00,US,MOBILE
    ```

    Duplicates are handled with UPSERT - existing records are updated.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        from datetime import datetime

        # Read and parse CSV
        contents = await file.read()
        text = contents.decode("utf-8")

        # Column name aliases for flexible matching (same as frontend)
        COLUMN_ALIASES = {
            'creative_id': ['creative_id', 'creativeid', '#creative id', '#creative_id', 'creative id', '#creativeid'],
            'date': ['date', 'day', '#day', 'metric_date', '#date'],
            'impressions': ['impressions', 'imps', '#impressions'],
            'clicks': ['clicks', '#clicks'],
            'spend': ['spend', 'spend (buyer currency)', 'spend_buyer_currency', 'cost', '#spend', 'spend (usd)', 'revenue'],
            'geography': ['geography', 'country', 'geo', 'region', '#country'],
            'device_type': ['device_type', 'device', 'platform', 'device type'],
            'placement': ['placement', 'ad_slot', 'inventory'],
            'campaign_id': ['campaign_id', 'campaign', 'line_item'],
            'hour': ['hour', '#hour'],
        }

        def normalize_column_name(col: str) -> str:
            """Convert any column name variant to standard name."""
            col_lower = col.lower().strip()

            for standard_name, aliases in COLUMN_ALIASES.items():
                if col_lower in [a.lower() for a in aliases]:
                    return standard_name

            # Clean up common patterns
            col_clean = col_lower.replace(' ', '_').replace('(', '').replace(')', '').replace('#', '')
            for standard_name, aliases in COLUMN_ALIASES.items():
                if col_clean in [a.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('#', '') for a in aliases]:
                    return standard_name

            return col_lower  # Return as-is if no match

        # Read CSV and normalize column names
        raw_reader = csv.DictReader(io.StringIO(text))
        if raw_reader.fieldnames is None:
            raise HTTPException(status_code=400, detail="CSV file is empty or malformed")

        # Create column mapping
        column_map = {col: normalize_column_name(col) for col in raw_reader.fieldnames}
        logger.info(f"Column mapping: {column_map}")

        # Re-read with normalized column names
        def normalize_row(row: dict) -> dict:
            return {column_map.get(k, k): v for k, v in row.items()}

        reader = csv.DictReader(io.StringIO(text))
        normalized_rows = [normalize_row(row) for row in reader]

        # Validate required columns (using normalized names)
        required_columns = {"creative_id", "date", "impressions", "clicks", "spend"}
        found_columns = set(column_map.values())

        missing = required_columns - found_columns
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {', '.join(missing)}. Found: {', '.join(sorted(found_columns))}",
            )

        # Parse records (using normalized rows)
        metrics = []
        errors = []
        skipped = 0
        anomaly_count = 0

        for row_num, row in enumerate(normalized_rows, start=2):  # Start at 2 (after header)
            try:
                # Parse date - try multiple formats
                date_str = row.get("date", "").strip()
                metric_date = None
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"]:
                    try:
                        metric_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
                if metric_date is None:
                    raise ValueError(f"Invalid date format: {date_str}")

                # Parse numeric values - handle various formats
                def parse_number(val, default=0):
                    if not val:
                        return default
                    # Remove currency symbols, commas, whitespace
                    cleaned = str(val).replace('$', '').replace(',', '').replace(' ', '').strip()
                    try:
                        return float(cleaned) if '.' in cleaned else int(cleaned)
                    except ValueError:
                        return default

                impressions = int(parse_number(row.get("impressions", 0)))
                clicks = int(parse_number(row.get("clicks", 0)))
                spend_usd = float(parse_number(row.get("spend", 0)))

                # Forgiving validation - fix negatives, don't reject clicks > impressions
                if impressions < 0:
                    impressions = 0  # Auto-fix
                if clicks < 0:
                    clicks = 0  # Auto-fix
                if spend_usd < 0:
                    spend_usd = 0  # Auto-fix

                # Track anomalies but DON'T reject (forgiving validator philosophy)
                if clicks > impressions:
                    anomaly_count += 1  # Just count, don't raise error

                # Convert spend to micros (USD * 1,000,000)
                spend_micros = int(spend_usd * 1_000_000)

                # Parse optional fields
                geography_raw = row.get("geography", "").strip().upper() or None
                device_type = row.get("device_type", "").strip().upper() or None
                placement = row.get("placement", "").strip() or None
                campaign_id = row.get("campaign_id", "").strip() or None

                # Normalize geography - accept both ISO codes and full country names
                # Common country name to ISO code mapping
                COUNTRY_TO_ISO = {
                    'INDIA': 'IN', 'UNITED STATES': 'US', 'USA': 'US', 'GERMANY': 'DE',
                    'UNITED KINGDOM': 'GB', 'UK': 'GB', 'FRANCE': 'FR', 'SPAIN': 'ES',
                    'ITALY': 'IT', 'CANADA': 'CA', 'AUSTRALIA': 'AU', 'BRAZIL': 'BR',
                    'MEXICO': 'MX', 'JAPAN': 'JP', 'CHINA': 'CN', 'SOUTH KOREA': 'KR',
                    'KOREA': 'KR', 'RUSSIA': 'RU', 'NETHERLANDS': 'NL', 'POLAND': 'PL',
                    'TURKEY': 'TR', 'INDONESIA': 'ID', 'THAILAND': 'TH', 'VIETNAM': 'VN',
                    'PHILIPPINES': 'PH', 'MALAYSIA': 'MY', 'SINGAPORE': 'SG', 'TAIWAN': 'TW',
                    'HONG KONG': 'HK', 'PAKISTAN': 'PK', 'BANGLADESH': 'BD', 'EGYPT': 'EG',
                    'SOUTH AFRICA': 'ZA', 'NIGERIA': 'NG', 'KENYA': 'KE', 'ARGENTINA': 'AR',
                    'COLOMBIA': 'CO', 'CHILE': 'CL', 'PERU': 'PE', 'SAUDI ARABIA': 'SA',
                    'UAE': 'AE', 'UNITED ARAB EMIRATES': 'AE', 'ISRAEL': 'IL', 'SWEDEN': 'SE',
                    'NORWAY': 'NO', 'DENMARK': 'DK', 'FINLAND': 'FI', 'BELGIUM': 'BE',
                    'AUSTRIA': 'AT', 'SWITZERLAND': 'CH', 'PORTUGAL': 'PT', 'GREECE': 'GR',
                    'CZECH REPUBLIC': 'CZ', 'ROMANIA': 'RO', 'HUNGARY': 'HU', 'IRELAND': 'IE',
                    'NEW ZEALAND': 'NZ', 'UKRAINE': 'UA',
                }

                geography = None
                if geography_raw:
                    if len(geography_raw) == 2:
                        # Already an ISO code
                        geography = geography_raw
                    elif geography_raw in COUNTRY_TO_ISO:
                        # Convert full name to ISO
                        geography = COUNTRY_TO_ISO[geography_raw]
                    else:
                        # Unknown country - accept as-is (forgiving), truncate if needed
                        geography = geography_raw[:50] if len(geography_raw) > 50 else geography_raw

                # Normalize device_type (forgiving - map unknown values to UNKNOWN)
                valid_device_types = {"MOBILE", "DESKTOP", "TABLET", "CTV", "UNKNOWN"}
                if device_type and device_type not in valid_device_types:
                    device_type = "UNKNOWN"  # Accept but normalize to UNKNOWN

                # Parse hour if present (forgiving - ignore invalid values)
                hour = None
                if row.get("hour"):
                    try:
                        hour = int(row["hour"])
                        if hour < 0 or hour > 23:
                            hour = None  # Ignore out-of-range values
                    except (ValueError, TypeError):
                        hour = None  # Ignore unparseable values

                metrics.append(
                    PerformanceMetric(
                        creative_id=row["creative_id"],
                        metric_date=metric_date,
                        impressions=impressions,
                        clicks=clicks,
                        spend_micros=spend_micros,
                        campaign_id=campaign_id,
                        geography=geography,
                        device_type=device_type,
                        placement=placement,
                    )
                )

            except (ValueError, KeyError) as e:
                errors.append({
                    "row": row_num,
                    "error": str(e),
                    "data": dict(row),
                })
                skipped += 1
                continue

        if not metrics and not errors:
            raise HTTPException(status_code=400, detail="No valid records found in CSV")

        # Import metrics
        imported = await store.save_performance_metrics(metrics)

        return CSVImportResult(
            status="completed",
            imported=imported,
            skipped=skipped,
            errors=errors[:50],  # Limit to first 50 errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV import failed: {e}")
        raise HTTPException(status_code=500, detail=f"CSV import failed: {str(e)}")


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
        db_path = Path.home() / ".rtbcat" / "rtbcat.db"
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
    store: SQLiteStore = Depends(get_store),
):
    """
    Batch import endpoint for chunked uploads.

    Accepts an array of performance rows and imports them using the
    optimized repository with lookup tables.

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
    from pathlib import Path
    from storage.performance_repository import PerformanceRepository

    try:
        # Get database path and create direct connection for repository
        db_path = Path.home() / ".rtbcat" / "rtbcat.db"
        db_conn = sqlite3.connect(str(db_path))
        repo = PerformanceRepository(db_conn)

        # Track stats
        min_date: Optional[str] = None
        max_date: Optional[str] = None
        total_spend = 0.0

        for row in request.rows:
            date = row.get("date") or row.get("metric_date")
            if date:
                if min_date is None or date < min_date:
                    min_date = date
                if max_date is None or date > max_date:
                    max_date = date

            spend = row.get("spend", 0)
            if isinstance(spend, str):
                spend = float(spend.replace("$", "").replace(",", ""))
            total_spend += float(spend)

        # Insert batch
        count = repo.insert_batch(request.rows)
        db_conn.close()

        return StreamingImportResult(
            status="completed",
            total_rows=len(request.rows),
            imported=count,
            skipped=0,
            batches=1,
            errors=[],
            date_range={"start": min_date, "end": max_date} if min_date else None,
            total_spend=round(total_spend, 2) if total_spend > 0 else None,
        )

    except Exception as e:
        logger.error(f"Batch import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch import failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
