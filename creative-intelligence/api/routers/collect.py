"""Collection router for Cat-Scan API.

This module provides endpoints for collecting creative data from the
Authorized Buyers RTB API:
- Start background collection jobs
- Synchronous collection (blocking)
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.dependencies import get_store, get_config
from api.schemas.system import CollectRequest, CollectResponse
from collectors import CreativesClient
from config import ConfigManager
from storage import SQLiteStore, creative_dicts_to_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collect", tags=["Collection"])


async def collect_creatives_task(
    credentials_path: str,
    account_id: str,
    filter_query: str | None,
    store: SQLiteStore,
) -> None:
    """Background task to collect creatives from API."""
    try:
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


@router.post("", response_model=CollectResponse)
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


@router.post("/sync", response_model=CollectResponse)
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
