"""RTB endpoints sync and management routes."""

import logging
from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_store
from collectors import EndpointsClient
from storage.sqlite_store import SQLiteStore
from storage.postgres_store import PostgresStore

from .models import RTBEndpointItem, RTBEndpointsResponse, SyncEndpointsResponse

# Store type can be either SQLite or Postgres
StoreType = Union[SQLiteStore, PostgresStore]

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


@router.post("/settings/endpoints/sync", response_model=SyncEndpointsResponse)
async def sync_rtb_endpoints(
    service_account_id: Optional[str] = Query(None, description="Service account ID to use"),
    store: StoreType = Depends(get_store),
):
    """Sync RTB endpoints from Google Authorized Buyers API.

    Fetches all RTB endpoints for the configured bidder account and stores them
    in the rtb_endpoints table.
    """
    # Get service account from new multi-account system
    if service_account_id:
        service_account = await store.get_service_account(service_account_id)
        if not service_account:
            raise HTTPException(status_code=404, detail="Service account not found")
    else:
        accounts = await store.get_service_accounts(active_only=True)
        if not accounts:
            raise HTTPException(
                status_code=400,
                detail="No service account configured. Upload credentials via /setup."
            )
        service_account = accounts[0]
    creds_path = Path(service_account.credentials_path).expanduser()
    if not creds_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Service account credentials file not found. Re-upload via /setup."
        )

    # Get bidder account ID from buyer_seats table (linked to service account)
    account_id = await store.get_bidder_id_for_service_account(service_account.id)
    if not account_id:
        # Fallback: Get any buyer_seat (single-account scenario)
        account_id = await store.get_first_bidder_id()
    if not account_id:
        raise HTTPException(
            status_code=400,
            detail="No buyer seats discovered. Use /seats/discover first."
        )
    logger.info(f"Using bidder_id: {account_id} for RTB endpoints sync")

    try:
        client = EndpointsClient(
            credentials_path=str(creds_path),
            account_id=account_id,
        )
        endpoints = await client.list_endpoints()

        # Store endpoints in database using store method
        count = await store.sync_rtb_endpoints(account_id, endpoints)

        return SyncEndpointsResponse(
            status="success",
            endpoints_synced=count,
            bidder_id=account_id,
        )

    except Exception as e:
        logger.error(f"Failed to sync RTB endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync endpoints: {str(e)}")


@router.get("/settings/endpoints", response_model=RTBEndpointsResponse)
async def get_rtb_endpoints(
    buyer_id: Optional[str] = Query(None, description="Buyer/seat ID to get endpoints for"),
    service_account_id: Optional[str] = Query(None, description="Service account ID (deprecated, use buyer_id)"),
    store: StoreType = Depends(get_store),
):
    """Get stored RTB endpoints with aggregated QPS data.

    Returns all RTB endpoints that have been synced from the Google API,
    along with total allocated QPS and current usage.

    Note: RTB endpoints are configured at the bidder level, not the buyer/seat level.
    When a buyer_id is provided, we look up its parent bidder_id to filter endpoints.
    """
    try:
        # Get bidder_id for filtering
        bidder_id = ""
        account_name = None

        # Priority 1: Use buyer_id to look up bidder_id
        if buyer_id:
            seat_info = await store.get_buyer_seat_with_bidder(buyer_id)
            if seat_info:
                bidder_id = seat_info["bidder_id"]
                account_name = seat_info["display_name"]
                logger.debug(f"Found bidder_id {bidder_id} for buyer_id {buyer_id}")

        # Priority 2: Fall back to service_account_id (legacy support)
        if not bidder_id and service_account_id:
            service_account = await store.get_service_account(service_account_id)
            if service_account:
                account_name = service_account.display_name
                bidder_id = await store.get_bidder_id_for_service_account(service_account.id)

        # Priority 3: Fall back to first active service account
        if not bidder_id:
            accounts = await store.get_service_accounts(active_only=True)
            if accounts:
                account_name = accounts[0].display_name
                bidder_id = await store.get_bidder_id_for_service_account(accounts[0].id)
                if bidder_id:
                    logger.info(f"Using fallback bidder_id: {bidder_id} for endpoints list")

        # Get endpoints, optionally filtered by bidder_id
        rows = await store.get_rtb_endpoints(bidder_id if bidder_id else None)

        endpoints = []
        total_qps = 0
        latest_sync = None

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
            if row["synced_at"]:
                if latest_sync is None or row["synced_at"] > latest_sync:
                    latest_sync = row["synced_at"]

        # Get current QPS usage from rtb_endpoints_current table
        qps_current = await store.get_rtb_endpoints_current_qps(bidder_id if bidder_id else None)

        return RTBEndpointsResponse(
            bidder_id=bidder_id or "unknown",
            account_name=account_name,
            endpoints=endpoints,
            total_qps_allocated=total_qps,
            qps_current=qps_current,
            synced_at=latest_sync,
        )

    except Exception as e:
        logger.error(f"Failed to get RTB endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get endpoints: {str(e)}")
