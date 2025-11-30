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

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from collectors import BuyerSeatsClient, CreativesClient
from config import ConfigManager
from storage import SQLiteStore, PerformanceMetric, creative_dicts_to_storage
from analytics import WasteAnalyzer

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
            last_synced=s.last_synced.isoformat() if s.last_synced else None,
            created_at=s.created_at.isoformat() if s.created_at else None,
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
        last_synced=seat.last_synced.isoformat() if seat.last_synced else None,
        created_at=seat.created_at.isoformat() if seat.created_at else None,
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
                    last_synced=s.last_synced.isoformat() if s.last_synced else None,
                    created_at=s.created_at.isoformat() if s.created_at else None,
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
        reader = csv.DictReader(io.StringIO(text))

        # Validate required columns
        required_columns = {"creative_id", "date", "impressions", "clicks", "spend"}
        if reader.fieldnames is None:
            raise HTTPException(status_code=400, detail="CSV file is empty or malformed")

        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {', '.join(missing)}",
            )

        # Parse records
        metrics = []
        errors = []
        skipped = 0

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
            try:
                # Parse date
                try:
                    metric_date = datetime.strptime(row["date"], "%Y-%m-%d").strftime("%Y-%m-%d")
                except ValueError:
                    raise ValueError(f"Invalid date format: {row['date']} (expected YYYY-MM-DD)")

                # Parse numeric values
                impressions = int(row.get("impressions", 0))
                clicks = int(row.get("clicks", 0))
                spend_usd = float(row.get("spend", 0))

                # Validate
                if impressions < 0:
                    raise ValueError(f"Impressions cannot be negative: {impressions}")
                if clicks < 0:
                    raise ValueError(f"Clicks cannot be negative: {clicks}")
                if clicks > impressions:
                    raise ValueError(f"Clicks ({clicks}) cannot exceed impressions ({impressions})")
                if spend_usd < 0:
                    raise ValueError(f"Spend cannot be negative: {spend_usd}")

                # Convert spend to micros (USD * 1,000,000)
                spend_micros = int(spend_usd * 1_000_000)

                # Parse optional fields
                geography = row.get("geography", "").strip().upper() or None
                device_type = row.get("device_type", "").strip().upper() or None
                placement = row.get("placement", "").strip() or None
                campaign_id = row.get("campaign_id", "").strip() or None

                # Validate geography (2-letter ISO code)
                if geography and len(geography) != 2:
                    raise ValueError(f"Invalid geography code: {geography} (expected 2-letter ISO code)")

                # Validate device_type
                valid_device_types = {"MOBILE", "DESKTOP", "TABLET", "CTV", "UNKNOWN"}
                if device_type and device_type not in valid_device_types:
                    raise ValueError(f"Invalid device_type: {device_type} (expected one of {valid_device_types})")

                # Parse hour if present
                hour = None
                if row.get("hour"):
                    hour = int(row["hour"])
                    if hour < 0 or hour > 23:
                        raise ValueError(f"Hour must be 0-23, got: {hour}")

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
