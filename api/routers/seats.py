"""Buyer Seats Router - Buyer seat management endpoints.

Handles discovery, sync, and management of Google Authorized Buyers seats.
Supports multi-account credentials for different buyer seats.

Credential modes:
1. Multi-account: Explicit service account JSON files uploaded via UI
2. Legacy: ConfigManager service account file
3. ADC (GCP): Application Default Credentials from VM's attached service account
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config import ConfigManager
from storage import creative_dicts_to_storage
from api.dependencies import (
    get_store,
    get_config,
    get_current_user,
    get_allowed_service_account_ids,
    require_buyer_access,
)
from services.auth_service import User
from collectors import BuyerSeatsClient, CreativesClient, EndpointsClient, PretargetingClient
from services.seats_service import SeatsService, BuyerSeat

StoreType = Any


def get_seats_service() -> SeatsService:
    """Dependency to get SeatsService instance."""
    return SeatsService()

logger = logging.getLogger(__name__)


def is_gcp_mode() -> bool:
    """Check if running in GCP mode with ADC (OAuth2 Proxy enabled)."""
    return os.environ.get("OAUTH2_PROXY_ENABLED", "").lower() in ("1", "true", "yes")


async def get_credentials_for_seat_with_fallback(
    seats_service: SeatsService,
    seat: BuyerSeat,
    config: ConfigManager,
) -> Optional[str]:
    """Get credentials path for a buyer seat.

    Tries credentials in this order:
    1. Multi-account credentials (via service_account_id)
    2. First available service account
    3. Legacy ConfigManager credentials
    4. ADC (GCP mode) - returns None to trigger Application Default Credentials

    Returns:
        Path to service account JSON file, or None for ADC mode.

    Raises:
        HTTPException: If no valid credentials found and not in GCP mode.
    """
    # Try multi-account via SeatsService
    creds_path = await seats_service.get_credentials_for_seat(seat)
    if creds_path:
        return creds_path

    # Fall back to legacy ConfigManager
    if config.is_configured():
        try:
            return str(config.get_service_account_path())
        except Exception:
            pass

    # GCP mode: use Application Default Credentials (VM's attached service account)
    if is_gcp_mode():
        logger.info("Using ADC (Application Default Credentials) for GCP mode")
        return None

    raise HTTPException(
        status_code=400,
        detail="No service account credentials configured. Add a service account in Setup.",
    )


async def _trigger_background_language_analysis(
    store: StoreType,
    limit: int = 50,
) -> int:
    """Trigger background language analysis for unanalyzed creatives.

    This runs analysis on creatives that haven't been analyzed yet.
    It's designed to be non-blocking and fail gracefully.

    Args:
        store: SQLite store instance.
        limit: Maximum number of creatives to analyze per batch.

    Returns:
        Number of creatives successfully analyzed.
    """
    # Check if Gemini API is configured (database or env var)
    try:
        from api.analysis.language_analyzer import GeminiLanguageAnalyzer
    except ImportError as e:
        logger.warning(f"Language analyzer not available: {e}")
        return 0

    analyzer = GeminiLanguageAnalyzer(db_path=store.db_path)
    if not analyzer.is_configured:
        logger.debug("Gemini API key not configured, skipping language analysis")
        return 0

    # Get creatives needing analysis
    creatives = await store.creative_repository.get_creatives_needing_language_analysis(
        limit=limit
    )

    if not creatives:
        logger.debug("No creatives need language analysis")
        return 0

    logger.info(f"Starting background language analysis for {len(creatives)} creatives")
    analyzed_count = 0

    for creative in creatives:
        try:
            result = await analyzer.analyze_creative(
                creative_id=creative.id,
                raw_data=creative.raw_data,
                creative_format=creative.format,
            )

            await store.creative_repository.update_language_detection(
                creative_id=creative.id,
                detected_language=result.language,
                detected_language_code=result.language_code,
                language_confidence=result.confidence,
                language_source=result.source,
                language_analysis_error=result.error,
            )

            if result.success:
                analyzed_count += 1
                logger.debug(
                    f"Detected language for creative {creative.id}: "
                    f"{result.language} ({result.language_code})"
                )

        except Exception as e:
            logger.warning(f"Failed to analyze language for creative {creative.id}: {e}")
            # Save the error to database
            await store.creative_repository.update_language_detection(
                creative_id=creative.id,
                detected_language=None,
                detected_language_code=None,
                language_confidence=None,
                language_source="gemini",
                language_analysis_error=str(e),
            )

    logger.info(f"Background language analysis complete: {analyzed_count}/{len(creatives)} successful")
    return analyzed_count


router = APIRouter(tags=["Buyer Seats"])


# =============================================================================
# Pydantic Models
# =============================================================================

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
    """Request model for discovering buyer seats.

    Note: bidder_id is optional because buyers.list() returns ALL accessible
    buyers regardless of what ID is passed. The field is kept for backwards
    compatibility but is not actually used by the discovery logic.
    """
    bidder_id: Optional[str] = None  # Optional - buyers.list() returns all accessible buyers
    service_account_id: Optional[str] = None  # Multi-account: specify which credentials to use
    auto_sync: bool = True  # Automatically sync data after discovery


class SyncSeatResponse(BaseModel):
    """Response model for seat sync operation."""
    status: str
    buyer_id: str
    creatives_synced: int
    message: str


class SyncAllResponse(BaseModel):
    """Response model for sync all operation."""
    status: str
    creatives_synced: int
    seats_synced: int
    endpoints_synced: int
    pretargeting_synced: int
    message: str
    last_synced: Optional[str] = None


class DiscoverSeatsResponse(BaseModel):
    """Response model for seat discovery."""
    status: str
    bidder_id: Optional[str] = None  # May be None if auto-discovery was used
    seats_discovered: int
    seats: list[BuyerSeatResponse]
    # Auto-sync results (if enabled)
    sync_result: Optional[SyncAllResponse] = None


class UpdateSeatRequest(BaseModel):
    """Request model for updating a buyer seat."""
    display_name: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/seats", response_model=list[BuyerSeatResponse])
async def list_seats(
    bidder_id: Optional[str] = Query(None, description="Filter by bidder ID"),
    active_only: bool = Query(True, description="Only return active seats"),
    seats_service: SeatsService = Depends(get_seats_service),
    user: User = Depends(get_current_user),
):
    """List all known buyer seats.

    Returns buyer seats that have been discovered via the /seats/discover endpoint.
    """
    if user.role == "admin":
        seats = await seats_service.get_buyer_seats(bidder_id=bidder_id, active_only=active_only)
    else:
        service_account_ids = await get_allowed_service_account_ids(user=user)
        seats = await seats_service.get_buyer_seats_for_service_accounts(
            service_account_ids=service_account_ids,
            bidder_id=bidder_id,
            active_only=active_only,
        )
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


@router.get("/seats/{buyer_id}", response_model=BuyerSeatResponse)
async def get_seat(
    buyer_id: str,
    seats_service: SeatsService = Depends(get_seats_service),
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get a specific buyer seat by ID."""
    await require_buyer_access(buyer_id, store=store, user=user)
    seat = await seats_service.get_buyer_seat(buyer_id)
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


@router.post("/seats/discover", response_model=DiscoverSeatsResponse)
async def discover_seats(
    request: DiscoverSeatsRequest,
    config: ConfigManager = Depends(get_config),
    seats_service: SeatsService = Depends(get_seats_service),
    store: StoreType = Depends(get_store),
):
    """Discover buyer seats under a bidder account.

    Queries the Authorized Buyers API to enumerate all buyer accounts
    associated with the specified bidder and saves them to the database.

    Supports multi-account credentials via service_account_id parameter.
    Falls back to first available service account or legacy config.
    """
    credentials_path: Optional[str] = None
    service_account_id: Optional[str] = request.service_account_id
    use_adc = False

    # Try to get credentials from multi-account system
    if service_account_id:
        # Specific account requested
        service_account = await seats_service.get_service_account(service_account_id)
        if service_account and service_account.credentials_path:
            credentials_path = service_account.credentials_path
            await seats_service.update_service_account_last_used(service_account_id)
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Service account {service_account_id} not found.",
            )
    else:
        # Try first available service account
        service_accounts = await seats_service.get_service_accounts(active_only=True)
        if service_accounts:
            service_account = service_accounts[0]
            service_account_id = service_account.id
            credentials_path = service_account.credentials_path
            await seats_service.update_service_account_last_used(service_account_id)

    # Fall back to legacy ConfigManager
    if not credentials_path:
        if config.is_configured():
            try:
                credentials_path = str(config.get_service_account_path())
            except Exception:
                pass

    # GCP mode: use Application Default Credentials
    if not credentials_path and is_gcp_mode():
        logger.info("Using ADC (Application Default Credentials) for seat discovery")
        use_adc = True

    if not credentials_path and not use_adc:
        raise HTTPException(
            status_code=400,
            detail="No service account credentials configured. Add a service account in Setup.",
        )

    try:
        client = BuyerSeatsClient(
            credentials_path=credentials_path,
            account_id=request.bidder_id,
        )

        # Discover seats from API
        api_seats = await client.discover_buyer_seats()
        logger.info(f"Discovered {len(api_seats)} buyer seats for bidder {request.bidder_id}")

        # Save to database and link to service account
        saved_seats = []
        for api_seat in api_seats:
            # Create BuyerSeat from API response
            seat = BuyerSeat(
                buyer_id=api_seat.buyer_id,
                bidder_id=api_seat.bidder_id,
                display_name=api_seat.display_name,
                active=api_seat.active,
                service_account_id=service_account_id,
            )
            await seats_service.save_buyer_seat(seat)
            saved_seats.append(seat)

        # Auto-sync data if requested (default: True)
        sync_result = None
        if request.auto_sync and saved_seats:
            try:
                logger.info("Auto-syncing data after seat discovery...")
                sync_result = await sync_all_data(
                    seats_service=seats_service, store=store, config=config
                )
            except Exception as e:
                logger.warning(f"Auto-sync failed (discovery still successful): {e}")
                # Don't fail the whole discovery if auto-sync fails

        return DiscoverSeatsResponse(
            status="completed",
            bidder_id=request.bidder_id,
            seats_discovered=len(saved_seats),
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
                for s in saved_seats
            ],
            sync_result=sync_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Seat discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Seat discovery failed: {str(e)}")


@router.post("/seats/{buyer_id}/sync", response_model=SyncSeatResponse)
async def sync_seat_creatives(
    buyer_id: str,
    filter_query: Optional[str] = Query(None, description="Optional API filter"),
    config: ConfigManager = Depends(get_config),
    seats_service: SeatsService = Depends(get_seats_service),
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Sync creatives for a specific buyer seat.

    Fetches all creatives associated with the buyer seat and stores them
    in the database with the buyer_id field populated.

    Uses multi-account credentials if available, falling back to legacy config.
    """
    # Verify seat exists
    await require_buyer_access(buyer_id, store=store, user=user)
    seat = await seats_service.get_buyer_seat(buyer_id)
    if not seat:
        raise HTTPException(status_code=404, detail="Buyer seat not found")

    # Get credentials (multi-account or legacy)
    credentials_path = await get_credentials_for_seat_with_fallback(seats_service, seat, config)

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
        await seats_service.update_seat_after_sync(buyer_id)

        return SyncSeatResponse(
            status="completed",
            buyer_id=buyer_id,
            creatives_synced=count,
            message=f"Successfully synced {count} creatives for buyer {buyer_id}.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Seat sync failed for {buyer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Seat sync failed: {str(e)}")


@router.patch("/seats/{buyer_id}", response_model=BuyerSeatResponse)
async def update_seat(
    buyer_id: str,
    request: UpdateSeatRequest,
    seats_service: SeatsService = Depends(get_seats_service),
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Update a buyer seat's display name."""
    await require_buyer_access(buyer_id, store=store, user=user)
    if request.display_name:
        success = await seats_service.update_display_name(buyer_id, request.display_name)
        if not success:
            raise HTTPException(status_code=404, detail="Buyer seat not found")

    seat = await seats_service.get_buyer_seat(buyer_id)
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


@router.post("/seats/populate")
async def populate_seats_from_creatives(
    seats_service: SeatsService = Depends(get_seats_service),
):
    """Populate buyer_seats table from existing creatives.

    Creates seat records for each unique account_id found in creatives.
    This is useful for migrating data after the initial import.
    """
    try:
        count = await seats_service.populate_from_creatives()
        return {"status": "completed", "seats_created": count}
    except Exception as e:
        logger.error(f"Seat population failed: {e}")
        raise HTTPException(status_code=500, detail=f"Seat population failed: {str(e)}")


@router.post("/seats/sync-all", response_model=SyncAllResponse)
async def sync_all_data(
    seats_service: SeatsService = Depends(get_seats_service),
    store: StoreType = Depends(get_store),
    config: ConfigManager = Depends(get_config),
    user: User = Depends(get_current_user),
):
    """Sync all data: creatives, RTB endpoints, and pretargeting configs.

    This is a unified sync operation that:
    1. Syncs creatives for all active buyer seats
    2. Syncs RTB endpoints from Google API
    3. Syncs pretargeting configurations from Google API

    Returns aggregated counts of all synced items.
    """
    total_creatives = 0
    seats_synced = 0
    endpoints_synced = 0
    pretargeting_synced = 0
    errors = []

    # Get all active buyer seats
    if user.role == "admin":
        seats = await seats_service.get_buyer_seats(active_only=True)
    else:
        service_account_ids = await get_allowed_service_account_ids(user=user)
        seats = await seats_service.get_buyer_seats_for_service_accounts(
            service_account_ids=service_account_ids,
            active_only=True,
        )

    if not seats:
        raise HTTPException(
            status_code=400,
            detail="No buyer seats found. Discover seats first via /seats/discover.",
        )

    # Get service account for API access (or use ADC in GCP mode)
    creds_path: Optional[str] = None
    use_adc = False

    service_accounts = await seats_service.get_service_accounts(active_only=True)
    if service_accounts:
        service_account = service_accounts[0]
        if service_account.credentials_path:
            expanded_path = Path(service_account.credentials_path).expanduser()
            if expanded_path.exists():
                creds_path = str(expanded_path)

    if not creds_path and is_gcp_mode():
        logger.info("Using ADC (Application Default Credentials) for sync-all")
        use_adc = True

    if not creds_path and not use_adc:
        raise HTTPException(
            status_code=400,
            detail="No service account configured. Add a service account in Setup.",
        )

    # 1. Sync creatives for each buyer seat
    for seat in seats:
        try:
            credentials_path = await get_credentials_for_seat_with_fallback(seats_service, seat, config)
            client = CreativesClient(
                credentials_path=credentials_path,
                account_id=seat.bidder_id,
            )
            api_creatives = await client.fetch_all_creatives(buyer_id=seat.buyer_id)
            storage_creatives = creative_dicts_to_storage(api_creatives)
            count = await store.save_creatives(storage_creatives)
            total_creatives += count
            seats_synced += 1

            # Update seat metadata
            await seats_service.update_seat_after_sync(seat.buyer_id)
        except Exception as e:
            logger.error(f"Failed to sync creatives for seat {seat.buyer_id}: {e}")
            errors.append(f"Creatives for {seat.buyer_id}: {str(e)}")

    # Get all unique bidder_ids for endpoints and pretargeting sync
    # Each bidder may have different endpoints and pretargeting configs
    if user.role == "admin":
        bidder_ids_list = await seats_service.get_distinct_bidder_ids()
    else:
        bidder_ids_list = list({seat.bidder_id for seat in seats})

    for account_id in bidder_ids_list:
        logger.info(f"Syncing endpoints and pretargeting for bidder {account_id}")

        # 2. Sync RTB endpoints for this bidder
        try:
            endpoints_client = EndpointsClient(
                credentials_path=creds_path,  # None for ADC mode
                account_id=account_id,
            )
            endpoints = await endpoints_client.list_endpoints()
            count = await store.sync_rtb_endpoints(account_id, endpoints)
            endpoints_synced += count
            logger.info(f"Synced {count} endpoints for bidder {account_id}")
        except Exception as e:
            logger.error(f"Failed to sync RTB endpoints for bidder {account_id}: {e}")
            errors.append(f"RTB endpoints for {account_id}: {str(e)}")

        # 3. Sync pretargeting configs for this bidder
        try:
            pretargeting_client = PretargetingClient(
                credentials_path=creds_path,  # None for ADC mode
                account_id=account_id,
            )
            configs = await pretargeting_client.fetch_all_pretargeting_configs()

            for cfg in configs:
                sizes = []
                for dim in cfg.get("includedCreativeDimensions", []):
                    if dim.get("width") and dim.get("height"):
                        sizes.append(f"{dim['width']}x{dim['height']}")

                geo_targeting = cfg.get("geoTargeting", {}) or {}
                included_geos = geo_targeting.get("includedIds", [])
                excluded_geos = geo_targeting.get("excludedIds", [])

                await store.save_pretargeting_config({
                    "bidder_id": account_id,
                    "config_id": cfg["configId"],
                    "billing_id": cfg.get("billingId"),
                    "display_name": cfg.get("displayName"),
                    "state": cfg.get("state", "ACTIVE"),
                    "included_formats": json.dumps(cfg.get("includedFormats", [])),
                    "included_platforms": json.dumps(cfg.get("includedPlatforms", [])),
                    "included_sizes": json.dumps(sizes),
                    "included_geos": json.dumps(included_geos),
                    "excluded_geos": json.dumps(excluded_geos),
                    "raw_config": json.dumps(cfg),
                })
            pretargeting_synced += len(configs)
            logger.info(f"Synced {len(configs)} pretargeting configs for bidder {account_id}")
        except Exception as e:
            logger.error(f"Failed to sync pretargeting configs for bidder {account_id}: {e}")
            errors.append(f"Pretargeting for {account_id}: {str(e)}")

    # 4. Trigger background language analysis for new creatives (non-blocking)
    try:
        await _trigger_background_language_analysis(store)
    except Exception as e:
        logger.warning(f"Background language analysis failed (non-critical): {e}")
        # Don't add to errors - this is optional and non-blocking

    # Build response message
    sync_time = datetime.utcnow().isoformat() + "Z"
    if errors:
        message = f"Sync completed with errors: {'; '.join(errors)}"
        status = "partial"
    else:
        message = f"Successfully synced {total_creatives} creatives from {seats_synced} seats, {endpoints_synced} endpoints, and {pretargeting_synced} pretargeting configs."
        status = "completed"

    return SyncAllResponse(
        status=status,
        creatives_synced=total_creatives,
        seats_synced=seats_synced,
        endpoints_synced=endpoints_synced,
        pretargeting_synced=pretargeting_synced,
        message=message,
        last_synced=sync_time,
    )
