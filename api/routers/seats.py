"""Buyer Seats Router - Buyer seat management endpoints.

Handles discovery, sync, and management of Google Authorized Buyers seats.
Supports multi-account credentials for different buyer seats.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config import ConfigManager
from storage import SQLiteStore, creative_dicts_to_storage
from api.dependencies import get_store, get_config
from collectors import BuyerSeatsClient, CreativesClient

logger = logging.getLogger(__name__)


async def get_credentials_for_seat(
    store: SQLiteStore,
    seat,
    config: ConfigManager,
) -> str:
    """Get credentials path for a buyer seat.

    Tries multi-account credentials first (via service_account_id),
    falls back to legacy ConfigManager credentials.

    Returns:
        Path to service account JSON file.

    Raises:
        HTTPException: If no valid credentials found.
    """
    # Try multi-account: seat has service_account_id linked
    if seat.service_account_id:
        service_account = await store.get_service_account(seat.service_account_id)
        if service_account and service_account.credentials_path:
            # Update last_used timestamp
            await store.update_service_account_last_used(seat.service_account_id)
            return service_account.credentials_path

    # Try multi-account: get first active service account
    service_accounts = await store.get_service_accounts(active_only=True)
    if service_accounts:
        # Use first available and link it to the seat for future use
        service_account = service_accounts[0]
        await store.link_buyer_seat_to_service_account(
            seat.buyer_id, service_account.id
        )
        await store.update_service_account_last_used(service_account.id)
        return service_account.credentials_path

    # Fall back to legacy ConfigManager
    if config.is_configured():
        try:
            return str(config.get_service_account_path())
        except Exception:
            pass

    raise HTTPException(
        status_code=400,
        detail="No service account credentials configured. Add a service account in Setup.",
    )

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
    """Request model for discovering buyer seats."""
    bidder_id: str
    service_account_id: Optional[str] = None  # Multi-account: specify which credentials to use


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


@router.get("/seats/{buyer_id}", response_model=BuyerSeatResponse)
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


@router.post("/seats/discover", response_model=DiscoverSeatsResponse)
async def discover_seats(
    request: DiscoverSeatsRequest,
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Discover buyer seats under a bidder account.

    Queries the Authorized Buyers API to enumerate all buyer accounts
    associated with the specified bidder and saves them to the database.

    Supports multi-account credentials via service_account_id parameter.
    Falls back to first available service account or legacy config.
    """
    credentials_path: Optional[str] = None
    service_account_id: Optional[str] = request.service_account_id

    # Try to get credentials from multi-account system
    if service_account_id:
        # Specific account requested
        service_account = await store.get_service_account(service_account_id)
        if service_account and service_account.credentials_path:
            credentials_path = service_account.credentials_path
            await store.update_service_account_last_used(service_account_id)
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Service account {service_account_id} not found.",
            )
    else:
        # Try first available service account
        service_accounts = await store.get_service_accounts(active_only=True)
        if service_accounts:
            service_account = service_accounts[0]
            service_account_id = service_account.id
            credentials_path = service_account.credentials_path
            await store.update_service_account_last_used(service_account_id)

    # Fall back to legacy ConfigManager
    if not credentials_path:
        if config.is_configured():
            try:
                credentials_path = str(config.get_service_account_path())
            except Exception:
                pass

    if not credentials_path:
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
        seats = await client.discover_buyer_seats()
        logger.info(f"Discovered {len(seats)} buyer seats for bidder {request.bidder_id}")

        # Save to database and link to service account
        for seat in seats:
            # Set the service_account_id for newly discovered seats
            if service_account_id:
                seat.service_account_id = service_account_id
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
    store: SQLiteStore = Depends(get_store),
):
    """Sync creatives for a specific buyer seat.

    Fetches all creatives associated with the buyer seat and stores them
    in the database with the buyer_id field populated.

    Uses multi-account credentials if available, falling back to legacy config.
    """
    # Verify seat exists
    seat = await store.get_buyer_seat(buyer_id)
    if not seat:
        raise HTTPException(status_code=404, detail="Buyer seat not found")

    # Get credentials (multi-account or legacy)
    credentials_path = await get_credentials_for_seat(store, seat, config)

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Seat sync failed for {buyer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Seat sync failed: {str(e)}")


@router.patch("/seats/{buyer_id}", response_model=BuyerSeatResponse)
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


@router.post("/seats/populate")
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
