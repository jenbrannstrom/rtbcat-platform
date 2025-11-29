"""FastAPI application for RTBcat Creative Intelligence.

This module provides REST API endpoints for managing creatives,
campaigns, and clusters with support for data collection and analysis
using the Google Authorized Buyers RTB API.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from collectors import CreativesClient
from config import ConfigManager
from storage import SQLiteStore, creative_dicts_to_storage

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


def _extract_preview_data(creative) -> dict:
    """Extract preview data from creative raw_data based on format."""
    raw_data = creative.raw_data or {}
    result = {"video": None, "html": None, "native": None}

    if creative.format == "VIDEO":
        video_data = raw_data.get("video")
        if video_data:
            result["video"] = VideoPreview(
                video_url=video_data.get("videoUrl"),
                vast_xml=video_data.get("vastXml"),
                duration=video_data.get("duration"),
            )

    elif creative.format == "HTML":
        html_data = raw_data.get("html")
        if html_data:
            result["html"] = HtmlPreview(
                snippet=html_data.get("snippet"),
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
    format: Optional[str] = Query(None, description="Filter by creative format"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    store: SQLiteStore = Depends(get_store),
):
    """List creatives with optional filtering."""
    creatives = await store.list_creatives(
        campaign_id=campaign_id,
        cluster_id=cluster_id,
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
            **_extract_preview_data(c),
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
