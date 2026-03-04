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
from datetime import datetime
from typing import Optional, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from config import ConfigManager
from storage import creative_dicts_to_storage
from api.dependencies import (
    require_admin,
    require_buyer_admin_access,
    require_seat_admin_or_sudo,
    get_store,
    get_config,
    get_current_user,
    get_allowed_buyer_ids,
    get_allowed_service_account_ids,
    require_buyer_access,
)
from services.auth_service import User
from collectors import BuyerSeatsClient, CreativesClient, EndpointsClient, PretargetingClient
from services.seats_service import SeatsService, BuyerSeat, is_gcp_mode
from services.pretargeting_service import PretargetingService
from services.config_service import ConfigService
from services.language_ai_config import get_selected_language_ai_provider

StoreType = Any


def get_seats_service() -> SeatsService:
    """Dependency to get SeatsService instance."""
    return SeatsService()

logger = logging.getLogger(__name__)


async def get_credentials_for_seat_with_fallback(
    seats_service: SeatsService,
    seat: BuyerSeat,
    config: ConfigManager,
) -> Optional[str]:
    """Get credentials path for a buyer seat with full fallback chain.

    Delegates to SeatsService.get_credentials_with_fallback() and converts
    ValueError to HTTPException for API error handling.
    """
    try:
        return await seats_service.get_credentials_with_fallback(seat, config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _trigger_background_language_analysis(
    store: StoreType,
    limit: int = 50,
) -> int:
    """Trigger background language analysis for unanalyzed creatives.

    This runs analysis on creatives that haven't been analyzed yet.
    It's designed to be non-blocking and fail gracefully.

    Args:
        store: PostgresStore instance.
        limit: Maximum number of creatives to analyze per batch.

    Returns:
        Number of creatives successfully analyzed.
    """
    # Check if selected provider API is configured (database or env var)
    try:
        from api.analysis.language_analyzer import LanguageAnalyzer
    except ImportError as e:
        logger.warning(f"Language analyzer not available: {e}")
        return 0

    provider = await get_selected_language_ai_provider(store)
    api_key = await ConfigService().get_ai_provider_api_key(store, provider)
    analyzer = LanguageAnalyzer(
        provider=provider,
        api_key=api_key,
        db_path=getattr(store, "db_path", None),
    )
    if not analyzer.is_configured:
        logger.debug(
            "%s API key not configured, skipping language analysis",
            provider.capitalize(),
        )
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
                language_source=provider,
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
    errors: list[str] = Field(default_factory=list)


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
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
) -> list[BuyerSeatResponse]:
    """List all known buyer seats.

    Returns buyer seats that have been discovered via the /seats/discover endpoint.
    """
    allowed_buyer_ids = await get_allowed_buyer_ids(store=store, user=user)
    if allowed_buyer_ids is None:
        seats = await seats_service.get_buyer_seats(
            bidder_id=bidder_id,
            active_only=active_only,
        )
    elif not allowed_buyer_ids:
        seats = []
    else:
        seats = await seats_service.get_buyer_seats_by_ids(
            buyer_ids=allowed_buyer_ids,
            bidder_id=bidder_id,
            active_only=active_only,
        )
    return [BuyerSeatResponse(**s.to_response_dict()) for s in seats]


@router.get("/seats/{buyer_id}", response_model=BuyerSeatResponse)
async def get_seat(
    buyer_id: str,
    seats_service: SeatsService = Depends(get_seats_service),
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
) -> BuyerSeatResponse:
    """Get a specific buyer seat by ID."""
    await require_buyer_access(buyer_id, store=store, user=user)
    seat = await seats_service.get_buyer_seat(buyer_id)
    if not seat:
        raise HTTPException(status_code=404, detail="Buyer seat not found")

    return BuyerSeatResponse(**seat.to_response_dict())


@router.post("/seats/discover", response_model=DiscoverSeatsResponse)
async def discover_seats(
    request: DiscoverSeatsRequest,
    config: ConfigManager = Depends(get_config),
    seats_service: SeatsService = Depends(get_seats_service),
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
) -> DiscoverSeatsResponse:
    """Discover buyer seats under a bidder account.

    Queries the Authorized Buyers API to enumerate all buyer accounts
    associated with the specified bidder and saves them to the database.

    Supports multi-account credentials via service_account_id parameter.
    Falls back to first available service account or legacy config.
    """
    await require_seat_admin_or_sudo(user=user)

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
                    seats_service=seats_service, store=store, config=config, user=user
                )
            except Exception as e:
                logger.warning(f"Auto-sync failed (discovery still successful): {e}")
                # Don't fail the whole discovery if auto-sync fails

        return DiscoverSeatsResponse(
            status="completed",
            bidder_id=request.bidder_id,
            seats_discovered=len(saved_seats),
            seats=[BuyerSeatResponse(**s.to_response_dict()) for s in saved_seats],
            sync_result=sync_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Seat discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Seat discovery failed: {str(e)}")


async def _trigger_geo_linguistic_batch(
    creative_ids: list[str], store: Any, triggered_by: str, max_batch: int = 50
) -> None:
    """Background task: run geo-linguistic analysis on recently synced creatives."""
    try:
        from services.geo_linguistic_service import GeoLinguisticService

        service = GeoLinguisticService()
        for cid in creative_ids[:max_batch]:
            try:
                await service.analyze_creative(
                    creative_id=cid, store=store, force=False, triggered_by=triggered_by
                )
            except Exception as exc:
                logger.debug("Geo-linguistic analysis skipped for %s: %s", cid, exc)
    except Exception as exc:
        logger.warning("Geo-linguistic batch trigger failed: %s", exc)


@router.post("/seats/{buyer_id}/sync", response_model=SyncSeatResponse)
async def sync_seat_creatives(
    buyer_id: str,
    filter_query: Optional[str] = Query(None, description="Optional API filter"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    config: ConfigManager = Depends(get_config),
    seats_service: SeatsService = Depends(get_seats_service),
    store: StoreType = Depends(get_store),
    user: User = Depends(get_current_user),
) -> SyncSeatResponse:
    """Sync creatives for a specific buyer seat.

    Fetches all creatives associated with the buyer seat and stores them
    in the database with the buyer_id field populated.

    Uses multi-account credentials if available, falling back to legacy config.
    """
    # Verify seat exists
    await require_buyer_admin_access(buyer_id, user=user)
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

        # Trigger geo-linguistic analysis for synced creatives in background
        synced_ids = [c.get("id") or c.get("creative_id", "") for c in storage_creatives if isinstance(c, dict)]
        if not synced_ids and storage_creatives:
            synced_ids = [getattr(c, "id", "") for c in storage_creatives if hasattr(c, "id")]
        if synced_ids:
            background_tasks.add_task(
                _trigger_geo_linguistic_batch, synced_ids, store, user.email
            )

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
) -> BuyerSeatResponse:
    """Update a buyer seat's display name."""
    await require_buyer_admin_access(buyer_id, user=user)
    if request.display_name:
        success = await seats_service.update_display_name(buyer_id, request.display_name)
        if not success:
            raise HTTPException(status_code=404, detail="Buyer seat not found")

    seat = await seats_service.get_buyer_seat(buyer_id)
    if not seat:
        raise HTTPException(status_code=404, detail="Buyer seat not found")

    return BuyerSeatResponse(**seat.to_response_dict())


@router.post("/seats/populate")
async def populate_seats_from_creatives(
    seats_service: SeatsService = Depends(get_seats_service),
    user: User = Depends(get_current_user),
) -> dict[str, str | int]:
    """Populate buyer_seats table from existing creatives.

    Creates seat records for each unique account_id found in creatives.
    This is useful for migrating data after the initial import.
    """
    await require_admin(user=user)

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
) -> SyncAllResponse:
    """Sync all data: creatives, RTB endpoints, and pretargeting configs.

    This is a unified sync operation that:
    1. Syncs creatives for all active buyer seats
    2. Syncs RTB endpoints from Google API
    3. Syncs pretargeting configurations from Google API

    Returns aggregated counts of all synced items.
    """
    await require_seat_admin_or_sudo(user=user)

    total_creatives = 0
    seats_synced = 0
    endpoints_synced = 0
    pretargeting_synced = 0
    errors = []

    # Get all active buyer seats, filtered by RBAC permissions
    allowed_buyer_ids = await get_allowed_buyer_ids(store=store, user=user)
    all_seats = await seats_service.get_buyer_seats(active_only=True)
    if allowed_buyer_ids is not None:
        allowed_set = set(allowed_buyer_ids)
        seats = [s for s in all_seats if s.buyer_id in allowed_set]
    else:
        seats = all_seats

    if not seats:
        raise HTTPException(
            status_code=400,
            detail="No buyer seats found. Discover seats first via /seats/discover.",
        )

    seats_by_bidder: dict[str, list[BuyerSeat]] = {}
    for seat in seats:
        seats_by_bidder.setdefault(seat.bidder_id, []).append(seat)

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

    # Endpoints + pretargeting are bidder-scoped. Only process active bidders
    # represented by the selected seats to avoid stale/unlinked bidder failures.
    bidder_ids_list = sorted(seats_by_bidder.keys())

    for account_id in bidder_ids_list:
        logger.info(f"Syncing endpoints and pretargeting for bidder {account_id}")
        bidder_seats = seats_by_bidder.get(account_id, [])

        bidder_credentials: Optional[str] = None
        bidder_credentials_error: Optional[str] = None
        for seat in bidder_seats:
            try:
                bidder_credentials = await get_credentials_for_seat_with_fallback(
                    seats_service,
                    seat,
                    config,
                )
                bidder_credentials_error = None
                break
            except HTTPException as e:
                bidder_credentials_error = str(e.detail)
            except Exception as e:
                bidder_credentials_error = str(e)

        if bidder_credentials is None and not is_gcp_mode():
            detail = bidder_credentials_error or "No valid credentials resolved for bidder."
            logger.error("Failed to resolve credentials for bidder %s: %s", account_id, detail)
            errors.append(f"Credentials for {account_id}: {detail}")
            continue

        # 2. Sync RTB endpoints for this bidder
        try:
            endpoints_client = EndpointsClient(
                credentials_path=bidder_credentials,  # None for ADC mode
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
            pretargeting_service = PretargetingService()
            pretargeting_client = PretargetingClient(
                credentials_path=bidder_credentials,  # None for ADC mode
                account_id=account_id,
            )
            configs = await pretargeting_client.fetch_all_pretargeting_configs()
            synced_for_bidder = 0

            for cfg in configs:
                try:
                    sizes = []
                    for dim in cfg.get("includedCreativeDimensions", []):
                        if dim.get("width") and dim.get("height"):
                            sizes.append(f"{dim['width']}x{dim['height']}")

                    geo_targeting = cfg.get("geoTargeting", {}) or {}
                    included_geos = geo_targeting.get("includedIds", [])
                    excluded_geos = geo_targeting.get("excludedIds", [])
                    included_os = cfg.get("includedMobileOperatingSystemIds", [])

                    await pretargeting_service.save_config({
                        "bidder_id": account_id,
                        "config_id": cfg["configId"],
                        "billing_id": str(cfg.get("billingId", "")).strip() or None,
                        "display_name": cfg.get("displayName"),
                        "state": cfg.get("state", "ACTIVE"),
                        "included_formats": json.dumps(cfg.get("includedFormats", [])),
                        "included_platforms": json.dumps(cfg.get("includedPlatforms", [])),
                        "included_sizes": json.dumps(sizes),
                        "included_geos": json.dumps(included_geos),
                        "excluded_geos": json.dumps(excluded_geos),
                        "included_operating_systems": json.dumps(included_os) if included_os else None,
                        "raw_config": json.dumps(cfg),
                    })

                    billing_id = str(cfg.get("billingId", "")).strip()
                    if billing_id:
                        publisher_targeting = cfg.get("publisherTargeting", {}) or {}
                        publisher_mode = publisher_targeting.get("targetingMode") or "EXCLUSIVE"
                        publisher_values = publisher_targeting.get("values", [])
                        included_publishers = publisher_values if publisher_mode == "INCLUSIVE" else []
                        excluded_publishers = publisher_values if publisher_mode == "EXCLUSIVE" else []

                        await pretargeting_service.clear_sync_publishers(billing_id)
                        for pub_id in included_publishers:
                            await pretargeting_service.add_publisher(
                                billing_id=billing_id,
                                publisher_id=str(pub_id),
                                mode="WHITELIST",
                                status="active",
                                source="api_sync",
                            )
                        for pub_id in excluded_publishers:
                            await pretargeting_service.add_publisher(
                                billing_id=billing_id,
                                publisher_id=str(pub_id),
                                mode="BLACKLIST",
                                status="active",
                                source="api_sync",
                            )
                    synced_for_bidder += 1
                except Exception as e:
                    cfg_id = cfg.get("configId", "unknown")
                    logger.error(
                        "Failed to sync pretargeting config %s for bidder %s: %s",
                        cfg_id,
                        account_id,
                        e,
                    )
                    errors.append(f"Pretargeting config {cfg_id} for {account_id}: {str(e)}")
                    continue

            pretargeting_synced += synced_for_bidder
            logger.info(f"Synced {synced_for_bidder}/{len(configs)} pretargeting configs for bidder {account_id}")
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
        errors=errors,
    )
