"""Pretargeting configuration routes."""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_store
from collectors import PretargetingClient
from storage.database import db_execute, db_query, db_query_one
from storage.sqlite_store import SQLiteStore

from .models import (
    PretargetingConfigResponse,
    PretargetingHistoryResponse,
    SetPretargetingNameRequest,
    SyncPretargetingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


@router.post("/settings/pretargeting/sync", response_model=SyncPretargetingResponse)
async def sync_pretargeting_configs(
    service_account_id: Optional[str] = Query(None, description="Service account ID to use"),
    store: SQLiteStore = Depends(get_store),
):
    """Sync pretargeting configs from Google Authorized Buyers API.

    Fetches all pretargeting configurations for the configured bidder account
    and stores them in the pretargeting_configs table.
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
        (service_account.id,)
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
    logger.info(f"Using bidder_id: {account_id} for pretargeting sync")

    try:
        client = PretargetingClient(
            credentials_path=str(creds_path),
            account_id=account_id,
        )
        configs = await client.fetch_all_pretargeting_configs()

        # Store configs in database using new db module
        for cfg in configs:
            # Extract sizes as strings
            sizes = []
            for dim in cfg.get("includedCreativeDimensions", []):
                if dim.get("width") and dim.get("height"):
                    sizes.append(f"{dim['width']}x{dim['height']}")

            # Extract geo IDs
            geo_targeting = cfg.get("geoTargeting", {}) or {}
            included_geos = geo_targeting.get("includedIds", [])
            excluded_geos = geo_targeting.get("excludedIds", [])

            # Extract OS targeting IDs (iOS = 30001, Android = 30002)
            included_os = cfg.get("includedMobileOperatingSystemIds", [])

            await db_execute(
                """
                INSERT INTO pretargeting_configs
                (bidder_id, config_id, billing_id, display_name, state,
                 included_formats, included_platforms, included_sizes,
                 included_geos, excluded_geos, included_operating_systems, raw_config, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bidder_id, config_id) DO UPDATE SET
                    billing_id = excluded.billing_id,
                    display_name = excluded.display_name,
                    state = excluded.state,
                    included_formats = excluded.included_formats,
                    included_platforms = excluded.included_platforms,
                    included_sizes = excluded.included_sizes,
                    included_geos = excluded.included_geos,
                    excluded_geos = excluded.excluded_geos,
                    included_operating_systems = excluded.included_operating_systems,
                    raw_config = excluded.raw_config,
                    synced_at = CURRENT_TIMESTAMP
                """,
                (
                    account_id,
                    cfg["configId"],
                    # Normalize billing_id to match CSV import (strip whitespace)
                    str(cfg.get("billingId", "")).strip() or None,
                    cfg.get("displayName"),
                    cfg.get("state", "ACTIVE"),
                    json.dumps(cfg.get("includedFormats", [])),
                    json.dumps(cfg.get("includedPlatforms", [])),
                    json.dumps(sizes),
                    json.dumps(included_geos),
                    json.dumps(excluded_geos),
                    json.dumps(included_os) if included_os else None,
                    json.dumps(cfg),
                ),
            )

        return SyncPretargetingResponse(
            status="success",
            configs_synced=len(configs),
            bidder_id=account_id,
        )

    except Exception as e:
        logger.error(f"Failed to sync pretargeting configs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync configs: {str(e)}")


@router.get("/settings/pretargeting", response_model=list[PretargetingConfigResponse])
async def get_pretargeting_configs(
    buyer_id: Optional[str] = Query(None, description="Buyer/seat ID to get configs for"),
    service_account_id: Optional[str] = Query(None, description="Service account ID (deprecated, use buyer_id)"),
    store: SQLiteStore = Depends(get_store),
):
    """Get stored pretargeting configs for the current account.

    Returns pretargeting configurations that have been synced from the Google API
    for the currently configured account (bidder_id). This prevents cross-account
    data mixing when multiple accounts have been synced.

    Note: Pretargeting configs are per-bidder. When buyer_id is provided, we look up
    its parent bidder_id to filter configs.

    Includes user-defined names if set.
    """
    try:
        # Get the current account's bidder_id
        current_bidder_id = None

        # Priority 1: Use buyer_id to look up bidder_id
        if buyer_id:
            bidder_row = await db_query_one(
                "SELECT bidder_id FROM buyer_seats WHERE buyer_id = ?",
                (buyer_id,)
            )
            if bidder_row:
                current_bidder_id = bidder_row["bidder_id"]
                logger.debug(f"Found bidder_id {current_bidder_id} for buyer_id {buyer_id}")

        # Priority 2: Fall back to service_account_id (legacy support)
        if not current_bidder_id and service_account_id:
            service_account = await store.get_service_account(service_account_id)
            if service_account:
                bidder_row = await db_query_one(
                    "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
                    (service_account.id,)
                )
                if bidder_row:
                    current_bidder_id = bidder_row["bidder_id"]

        # Priority 3: Fall back to first active service account
        if not current_bidder_id:
            accounts = await store.get_service_accounts(active_only=True)
            if accounts:
                service_account = accounts[0]
                bidder_row = await db_query_one(
                    "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
                    (service_account.id,)
                )
                if bidder_row:
                    current_bidder_id = bidder_row["bidder_id"]

        # Priority 4: Fallback to any buyer_seat
        if not current_bidder_id:
            bidder_row = await db_query_one(
                "SELECT bidder_id FROM buyer_seats LIMIT 1"
            )
            if bidder_row:
                current_bidder_id = bidder_row["bidder_id"]
                logger.info(f"Using fallback bidder_id: {current_bidder_id} for pretargeting list")

        if current_bidder_id:
            # Filter by current account's bidder_id
            rows = await db_query(
                "SELECT * FROM pretargeting_configs WHERE bidder_id = ? ORDER BY billing_id",
                (current_bidder_id,)
            )
        else:
            # Fallback: return all configs if no account configured
            rows = await db_query(
                "SELECT * FROM pretargeting_configs ORDER BY billing_id"
            )

        results = []
        for row in rows:
            # Parse OS targeting and convert IDs to names if possible
            os_ids = json.loads(row["included_operating_systems"]) if row["included_operating_systems"] else None
            os_names = None
            if os_ids:
                # Map known OS IDs to human-readable names
                os_map = {"30001": "iOS", "30002": "Android"}
                os_names = [os_map.get(str(os_id), str(os_id)) for os_id in os_ids]

            results.append(
                PretargetingConfigResponse(
                    config_id=row["config_id"],
                    bidder_id=row["bidder_id"],
                    billing_id=row["billing_id"],
                    display_name=row["display_name"],
                    user_name=row["user_name"],
                    state=row["state"] or "ACTIVE",
                    included_formats=json.loads(row["included_formats"]) if row["included_formats"] else None,
                    included_platforms=json.loads(row["included_platforms"]) if row["included_platforms"] else None,
                    included_sizes=json.loads(row["included_sizes"]) if row["included_sizes"] else None,
                    included_geos=json.loads(row["included_geos"]) if row["included_geos"] else None,
                    excluded_geos=json.loads(row["excluded_geos"]) if row["excluded_geos"] else None,
                    included_operating_systems=os_names,
                    synced_at=row["synced_at"],
                )
            )

        return results

    except Exception as e:
        logger.error(f"Failed to get pretargeting configs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get configs: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/name")
async def set_pretargeting_name(
    billing_id: str,
    body: SetPretargetingNameRequest,
):
    """Set a custom user-defined name for a pretargeting config.

    This name will be displayed in the UI alongside the billing_id,
    making it easier to identify configs.
    """
    try:
        # Get current value for history tracking
        current = await db_query_one(
            "SELECT user_name, config_id, bidder_id FROM pretargeting_configs WHERE billing_id = ?",
            (billing_id,),
        )

        if not current:
            raise HTTPException(
                status_code=404,
                detail=f"Pretargeting config with billing_id {billing_id} not found"
            )

        old_name = current["user_name"]
        config_id = current["config_id"]
        bidder_id = current["bidder_id"]

        # Update the name
        await db_execute(
            "UPDATE pretargeting_configs SET user_name = ? WHERE billing_id = ?",
            (body.user_name, billing_id),
        )

        # Record history if value changed
        if old_name != body.user_name:
            await db_execute(
                """INSERT INTO pretargeting_history
                (config_id, bidder_id, change_type, field_changed, old_value, new_value, change_source)
                VALUES (?, ?, 'update', 'user_name', ?, ?, 'user')""",
                (config_id, bidder_id, old_name, body.user_name),
            )

        return {
            "status": "success",
            "billing_id": billing_id,
            "user_name": body.user_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set pretargeting name: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set name: {str(e)}")


@router.get("/settings/pretargeting/history", response_model=list[PretargetingHistoryResponse])
async def get_pretargeting_history(
    config_id: Optional[str] = Query(None, description="Filter by config_id"),
    billing_id: Optional[str] = Query(None, description="Filter by billing_id"),
    days: int = Query(30, description="Number of days of history to retrieve", ge=1, le=365),
):
    """Get pretargeting settings change history.

    Returns a log of all changes made to pretargeting configurations,
    including who made the change and when.
    """
    try:
        # Build query based on filters
        query = """
            SELECT ph.* FROM pretargeting_history ph
            LEFT JOIN pretargeting_configs pc ON ph.config_id = pc.config_id
            WHERE ph.changed_at >= datetime('now', ?)
        """
        params = [f"-{days} days"]

        if config_id:
            query += " AND ph.config_id = ?"
            params.append(config_id)
        if billing_id:
            query += " AND pc.billing_id = ?"
            params.append(billing_id)

        query += " ORDER BY ph.changed_at DESC LIMIT 500"

        rows = await db_query(query, tuple(params))

        results = []
        for row in rows:
            results.append(
                PretargetingHistoryResponse(
                    id=row["id"],
                    config_id=row["config_id"],
                    bidder_id=row["bidder_id"],
                    change_type=row["change_type"],
                    field_changed=row["field_changed"],
                    old_value=row["old_value"],
                    new_value=row["new_value"],
                    changed_at=row["changed_at"],
                    changed_by=row["changed_by"],
                    change_source=row["change_source"] or "unknown",
                )
            )

        return results

    except Exception as e:
        logger.error(f"Failed to get pretargeting history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pretargeting history: {str(e)}")


# =============================================================================
