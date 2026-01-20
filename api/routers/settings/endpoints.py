"""RTB endpoints sync and management routes."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_store
from collectors import EndpointsClient
from storage.database import db_execute, db_query, db_query_one
from storage.sqlite_store import SQLiteStore

from .models import RTBEndpointItem, RTBEndpointsResponse, SyncEndpointsResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


@router.post("/settings/endpoints/sync", response_model=SyncEndpointsResponse)
async def sync_rtb_endpoints(
    service_account_id: Optional[str] = Query(None, description="Service account ID to use"),
    store: SQLiteStore = Depends(get_store),
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
    bidder_row = await db_query_one(
        "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
        (service_account.id,),
    )
    if not bidder_row:
        # Fallback: Get any buyer_seat (single-account scenario)
        bidder_row = await db_query_one(
            "SELECT bidder_id FROM buyer_seats LIMIT 1"
        )
    if not bidder_row:
        raise HTTPException(
            status_code=400,
            detail="No buyer seats discovered. Use /seats/discover first."
        )
    account_id = bidder_row["bidder_id"]
    logger.info(f"Using bidder_id: {account_id} for RTB endpoints sync")

    try:
        client = EndpointsClient(
            credentials_path=str(creds_path),
            account_id=account_id,
        )
        endpoints = await client.list_endpoints()

        # Store endpoints in database using new db module
        for ep in endpoints:
            await db_execute(
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
            )

        return SyncEndpointsResponse(
            status="success",
            endpoints_synced=len(endpoints),
            bidder_id=account_id,
        )

    except Exception as e:
        logger.error(f"Failed to sync RTB endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync endpoints: {str(e)}")


@router.get("/settings/endpoints", response_model=RTBEndpointsResponse)
async def get_rtb_endpoints(
    buyer_id: Optional[str] = Query(None, description="Buyer/seat ID to get endpoints for"),
    service_account_id: Optional[str] = Query(None, description="Service account ID (deprecated, use buyer_id)"),
    store: SQLiteStore = Depends(get_store),
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
            bidder_row = await db_query_one(
                "SELECT bidder_id, display_name FROM buyer_seats WHERE buyer_id = ?",
                (buyer_id,),
            )
            if bidder_row:
                bidder_id = bidder_row["bidder_id"]
                account_name = bidder_row["display_name"]
                logger.debug(f"Found bidder_id {bidder_id} for buyer_id {buyer_id}")

        # Priority 2: Fall back to service_account_id (legacy support)
        if not bidder_id and service_account_id:
            service_account = await store.get_service_account(service_account_id)
            if service_account:
                account_name = service_account.display_name
                bidder_row = await db_query_one(
                    "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
                    (service_account.id,),
                )
                if bidder_row:
                    bidder_id = bidder_row["bidder_id"]

        # Priority 3: Fall back to first active service account
        if not bidder_id:
            accounts = await store.get_service_accounts(active_only=True)
            if accounts:
                account_name = accounts[0].display_name
                bidder_row = await db_query_one(
                    "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
                    (accounts[0].id,),
                )
                if bidder_row:
                    bidder_id = bidder_row["bidder_id"]
                    logger.info(f"Using fallback bidder_id: {bidder_id} for endpoints list")

        # Get endpoints, optionally filtered by bidder_id
        if bidder_id:
            rows = await db_query(
                "SELECT * FROM rtb_endpoints WHERE bidder_id = ? ORDER BY trading_location, endpoint_id",
                (bidder_id,),
            )
        else:
            rows = await db_query(
                "SELECT * FROM rtb_endpoints ORDER BY trading_location, endpoint_id"
            )

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
        qps_current = None
        if bidder_id:
            row = await db_query_one(
                "SELECT SUM(current_qps) as current_qps FROM rtb_endpoints_current WHERE bidder_id = ?",
                (bidder_id,),
            )
        else:
            row = await db_query_one("SELECT SUM(current_qps) as current_qps FROM rtb_endpoints_current")

        if row:
            qps_current = row["current_qps"]

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
