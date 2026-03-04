"""RTB endpoints sync and management routes."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from googleapiclient.errors import HttpError

from api.dependencies import require_seat_admin_or_sudo
from collectors import EndpointsClient
from services.auth_service import User
from services.endpoints_service import EndpointsService
from services.seats_service import SeatsService, is_gcp_mode

from .models import (
    RTBEndpointItem,
    RTBEndpointsResponse,
    SyncEndpointsResponse,
    UpdateEndpointQpsRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


def get_seats_service() -> SeatsService:
    """Dependency to get SeatsService instance."""
    return SeatsService()


# ---------------------------------------------------------------------------
# Shared helper: resolve bidder context from buyer_id / service_account_id
# ---------------------------------------------------------------------------

async def _resolve_bidder_context(
    seats_service: SeatsService,
    buyer_id: Optional[str] = None,
    service_account_id: Optional[str] = None,
) -> tuple[str, Optional[str], Optional[str]]:
    """Resolve bidder_id, account_name, and credentials_path.

    Priority: buyer_id → service_account_id → first active service account.

    Returns:
        (bidder_id, account_name, credentials_path_or_none_for_adc)

    Raises:
        HTTPException on resolution failure.
    """
    account_name: Optional[str] = None
    bidder_id = ""
    service_account = None

    # Priority 1: buyer_id → look up service account via seat
    if buyer_id:
        seat_info = await seats_service.get_buyer_seat_with_bidder(buyer_id)
        if seat_info:
            bidder_id = seat_info["bidder_id"]
            account_name = seat_info["display_name"]

            # Find the service account linked to this bidder
            sa_id = seat_info.get("service_account_id")
            if sa_id:
                service_account = await seats_service.get_service_account(sa_id)

    # Priority 2: explicit service_account_id
    if not service_account and service_account_id:
        service_account = await seats_service.get_service_account(service_account_id)
        if not service_account:
            raise HTTPException(status_code=404, detail="Service account not found")
        if not account_name:
            account_name = service_account.display_name

    # Priority 3: first active service account
    if not service_account:
        accounts = await seats_service.get_service_accounts(active_only=True)
        if not accounts:
            # GCP mode (ADC) can proceed without a stored service account record.
            if not is_gcp_mode():
                raise HTTPException(
                    status_code=400,
                    detail="No service account configured. Upload credentials via /setup.",
                )
        else:
            service_account = accounts[0]
            if not account_name:
                account_name = service_account.display_name

    # Resolve bidder_id if not yet known
    if not bidder_id:
        if service_account:
            bidder_id = await seats_service.get_bidder_id_for_service_account(service_account.id) or ""
    if not bidder_id:
        bidder_id = await seats_service.get_first_bidder_id() or ""
    if not bidder_id:
        raise HTTPException(
            status_code=400,
            detail="No buyer seats discovered. Use /seats/discover first.",
        )

    # Credentials: explicit service-account JSON when available, otherwise ADC in GCP mode.
    if service_account and service_account.credentials_path:
        creds_path = Path(service_account.credentials_path).expanduser()
        if creds_path.exists():
            return bidder_id, account_name, str(creds_path)
        if not is_gcp_mode():
            raise HTTPException(
                status_code=400,
                detail="Service account credentials file not found. Re-upload via /setup.",
            )
        logger.info(
            "Service account credentials file missing; falling back to ADC for bidder_id=%s",
            bidder_id,
        )
        return bidder_id, account_name, None

    if service_account and not service_account.credentials_path and not is_gcp_mode():
        raise HTTPException(
            status_code=400,
            detail="Service account credentials path not configured.",
        )

    if is_gcp_mode():
        logger.info("Using ADC for RTB endpoints bidder_id=%s", bidder_id)
        return bidder_id, account_name, None

    raise HTTPException(
        status_code=400,
        detail="Service account credentials path not configured.",
    )


# ---------------------------------------------------------------------------
# Helper: build endpoint items + totals from raw endpoint dicts
# ---------------------------------------------------------------------------

def _build_endpoint_items(rows: list[dict]) -> tuple[list[RTBEndpointItem], int, Optional[str]]:
    """Convert raw endpoint rows to response items with totals."""
    endpoints: list[RTBEndpointItem] = []
    total_qps = 0
    latest_sync = None

    for row in rows:
        endpoints.append(
            RTBEndpointItem(
                endpoint_id=row.get("endpoint_id") or row.get("endpointId", ""),
                url=row.get("url", ""),
                maximum_qps=row.get("maximum_qps") if "maximum_qps" in row else row.get("maximumQps"),
                trading_location=row.get("trading_location") if "trading_location" in row else row.get("tradingLocation"),
                bid_protocol=row.get("bid_protocol") if "bid_protocol" in row else row.get("bidProtocol"),
            )
        )
        qps = row.get("maximum_qps") if "maximum_qps" in row else row.get("maximumQps")
        if qps:
            total_qps += int(qps)
        synced = row.get("synced_at") or row.get("collectedAt")
        if synced:
            if latest_sync is None or str(synced) > str(latest_sync):
                latest_sync = synced

    synced_at_value = str(latest_sync) if latest_sync else None
    return endpoints, total_qps, synced_at_value


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/settings/endpoints/sync", response_model=SyncEndpointsResponse)
async def sync_rtb_endpoints(
    service_account_id: Optional[str] = Query(None, description="Service account ID to use"),
    _user: User = Depends(require_seat_admin_or_sudo),
    seats_service: SeatsService = Depends(get_seats_service),
) -> SyncEndpointsResponse:
    """Sync RTB endpoints from Google Authorized Buyers API.

    Fetches all RTB endpoints for the configured bidder account and stores them
    in the rtb_endpoints table.
    """
    bidder_id, _, creds_path = await _resolve_bidder_context(
        seats_service, service_account_id=service_account_id,
    )
    logger.info(f"Using bidder_id: {bidder_id} for RTB endpoints sync")

    try:
        client = EndpointsClient(credentials_path=creds_path, account_id=bidder_id)
        endpoints = await client.list_endpoints()

        endpoint_service = EndpointsService()
        count = await endpoint_service.sync_endpoints(bidder_id, endpoints)

        # Refresh observed QPS from bidstream data for this bidder
        await endpoint_service.refresh_endpoints_current(bidder_id=bidder_id)

        return SyncEndpointsResponse(
            status="success",
            endpoints_synced=count,
            bidder_id=bidder_id,
        )

    except Exception as e:
        logger.error(f"Failed to sync RTB endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync endpoints: {str(e)}")


@router.get("/settings/endpoints", response_model=RTBEndpointsResponse)
async def get_rtb_endpoints(
    buyer_id: Optional[str] = Query(None, description="Buyer/seat ID to get endpoints for"),
    service_account_id: Optional[str] = Query(None, description="Service account ID (deprecated, use buyer_id)"),
    live: bool = Query(False, description="Fetch live data from Google API instead of local DB"),
    seats_service: SeatsService = Depends(get_seats_service),
) -> RTBEndpointsResponse:
    """Get RTB endpoints with aggregated QPS data.

    When live=false (default): returns endpoints stored in the local database.
    When live=true: fetches fresh allocated QPS from Google API, upserts into
    the local DB, and returns the updated data.

    Note: RTB endpoints are configured at the bidder level, not the buyer/seat level.
    When a buyer_id is provided, we look up its parent bidder_id to filter endpoints.
    """
    try:
        endpoint_service = EndpointsService()

        if live:
            # ---- Live path: fetch from Google API ----
            bidder_id, account_name, creds_path = await _resolve_bidder_context(
                seats_service, buyer_id=buyer_id, service_account_id=service_account_id,
            )

            client = EndpointsClient(credentials_path=creds_path, account_id=bidder_id)
            api_endpoints = await client.list_endpoints()

            # Upsert into local DB so it stays in sync
            await endpoint_service.sync_endpoints(bidder_id, api_endpoints)

            endpoints, total_qps, synced_at_value = _build_endpoint_items(api_endpoints)

            # Observed QPS still from precomputed table
            qps_current = await endpoint_service.get_current_qps(bidder_id)

            return RTBEndpointsResponse(
                bidder_id=bidder_id,
                account_name=account_name,
                endpoints=endpoints,
                total_qps_allocated=total_qps,
                qps_current=qps_current,
                synced_at=synced_at_value,
            )

        # ---- Default path: read from local DB ----
        bidder_id = ""
        account_name = None

        if buyer_id:
            seat_info = await seats_service.get_buyer_seat_with_bidder(buyer_id)
            if seat_info:
                bidder_id = seat_info["bidder_id"]
                account_name = seat_info["display_name"]

        if not bidder_id and service_account_id:
            sa = await seats_service.get_service_account(service_account_id)
            if sa:
                account_name = sa.display_name
                bidder_id = await seats_service.get_bidder_id_for_service_account(sa.id) or ""

        if not bidder_id:
            accounts = await seats_service.get_service_accounts(active_only=True)
            if accounts:
                account_name = accounts[0].display_name
                bidder_id = await seats_service.get_bidder_id_for_service_account(accounts[0].id) or ""

        effective_bidder_id = bidder_id if bidder_id else None
        rows, qps_current = await asyncio.gather(
            endpoint_service.list_endpoints(effective_bidder_id),
            endpoint_service.get_current_qps(effective_bidder_id),
        )
        endpoints, total_qps, synced_at_value = _build_endpoint_items(rows)

        return RTBEndpointsResponse(
            bidder_id=bidder_id or "unknown",
            account_name=account_name,
            endpoints=endpoints,
            total_qps_allocated=total_qps,
            qps_current=qps_current,
            synced_at=synced_at_value,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get RTB endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get endpoints: {str(e)}")


@router.patch("/settings/endpoints/{endpoint_id}/qps", response_model=RTBEndpointItem)
async def update_endpoint_qps(
    endpoint_id: str,
    request: UpdateEndpointQpsRequest,
    _user: User = Depends(require_seat_admin_or_sudo),
    seats_service: SeatsService = Depends(get_seats_service),
) -> RTBEndpointItem:
    """Update the allocated QPS for a single RTB endpoint.

    Calls the Google Authorized Buyers API to patch the endpoint, then re-syncs
    the local database. Does not refresh observed QPS.
    """
    bidder_id, _, creds_path = await _resolve_bidder_context(
        seats_service,
        buyer_id=request.buyer_id,
        service_account_id=request.service_account_id,
    )

    try:
        client = EndpointsClient(credentials_path=creds_path, account_id=bidder_id)
        updated = await client.patch_endpoint(endpoint_id, request.maximum_qps)

        # Re-sync all endpoints so local DB stays consistent
        all_endpoints = await client.list_endpoints()
        endpoint_service = EndpointsService()
        await endpoint_service.sync_endpoints(bidder_id, all_endpoints)

        return RTBEndpointItem(
            endpoint_id=updated["endpointId"],
            url=updated["url"],
            maximum_qps=updated.get("maximumQps"),
            trading_location=updated.get("tradingLocation"),
            bid_protocol=updated.get("bidProtocol"),
        )

    except HttpError as ex:
        status = ex.resp.status if hasattr(ex, "resp") else 500
        reason = str(ex.reason) if hasattr(ex, "reason") else str(ex)

        if status == 400:
            detail = f"Google API rejected the QPS update: {reason}"
        elif status == 403:
            detail = f"Not authorized to update this endpoint: {reason}"
        elif status == 404:
            detail = f"Endpoint {endpoint_id} not found."
        else:
            detail = f"Failed to update endpoint QPS: {reason}"

        raise HTTPException(status_code=status, detail=detail)

    except Exception as e:
        logger.error(f"Failed to update endpoint {endpoint_id} QPS: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update endpoint QPS: {str(e)}")
