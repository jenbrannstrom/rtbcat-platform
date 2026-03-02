"""Pretargeting configuration routes."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from collectors import PretargetingClient
from services.changes_service import ChangesService
from services.pretargeting_service import PretargetingService
from services.seats_service import SeatsService

from .models import (
    PretargetingConfigResponse,
    PretargetingHistoryResponse,
    SetPretargetingNameRequest,
    SyncPretargetingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])

MajorChangeType = Literal["targeting", "publisher", "qps", "mixed"]


def _parse_json_field(value):
    """Parse JSON field - handles both JSONB (already parsed) and TEXT (needs parsing)."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value  # Already parsed by psycopg (JSONB column)
    return json.loads(value)  # TEXT column, needs parsing


def _major_change_type_for_change(change_type: str) -> MajorChangeType:
    publisher_change_types = {"add_publisher", "remove_publisher", "set_publisher_mode"}
    if change_type == "set_maximum_qps":
        return "qps"
    if change_type in publisher_change_types:
        return "publisher"
    return "targeting"


def _resolve_active_major_change_type(
    pending_changes: list[dict],
    has_pending_publisher_changes: bool,
) -> MajorChangeType | None:
    detected: set[MajorChangeType] = {
        _major_change_type_for_change(str(change.get("change_type") or ""))
        for change in pending_changes
    }
    if has_pending_publisher_changes:
        detected.add("publisher")
    if not detected:
        return None
    if len(detected) == 1:
        return next(iter(detected))
    return "mixed"


def get_seats_service() -> SeatsService:
    """Dependency to get SeatsService instance."""
    return SeatsService()


@router.post("/settings/pretargeting/sync", response_model=SyncPretargetingResponse)
async def sync_pretargeting_configs(
    service_account_id: Optional[str] = Query(None, description="Service account ID to use"),
    seats_service: SeatsService = Depends(get_seats_service),
):
    """Sync pretargeting configs from Google Authorized Buyers API.

    Fetches all pretargeting configurations for the configured bidder account
    and stores them in the pretargeting_configs table.
    """
    # Get service account from new multi-account system
    if service_account_id:
        service_account = await seats_service.get_service_account(service_account_id)
        if not service_account:
            raise HTTPException(status_code=404, detail="Service account not found")
    else:
        accounts = await seats_service.get_service_accounts(active_only=True)
        if not accounts:
            raise HTTPException(
                status_code=400,
                detail="No service account configured. Upload credentials via /setup."
            )
        service_account = accounts[0]

    if not service_account.credentials_path:
        raise HTTPException(
            status_code=400,
            detail="Service account credentials path not configured."
        )

    creds_path = Path(service_account.credentials_path).expanduser()
    if not creds_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Service account credentials file not found. Re-upload via /setup."
        )

    # Get bidder account ID from buyer_seats table (linked to service account)
    account_id = await seats_service.get_bidder_id_for_service_account(service_account.id)
    if not account_id:
        # Fallback: Get any buyer_seat (single-account scenario)
        account_id = await seats_service.get_first_bidder_id()
    if not account_id:
        raise HTTPException(
            status_code=400,
            detail="No buyer seats discovered. Use /seats/discover first."
        )
    logger.info(f"Using bidder_id: {account_id} for pretargeting sync")

    try:
        pretargeting_service = PretargetingService()
        client = PretargetingClient(
            credentials_path=str(creds_path),
            account_id=account_id,
        )
        configs = await client.fetch_all_pretargeting_configs()

        # Store configs in database using store methods
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

        # Extract and store publisher targeting into pretargeting_publishers
        publishers_synced = 0
        for cfg in configs:
            billing_id = str(cfg.get("billingId", "")).strip()
            if not billing_id:
                continue

            publisher_targeting = cfg.get("publisherTargeting", {}) or {}
            publisher_mode = publisher_targeting.get("targetingMode") or "EXCLUSIVE"
            publisher_values = publisher_targeting.get("values", [])
            included_publishers = publisher_values if publisher_mode == "INCLUSIVE" else []
            excluded_publishers = publisher_values if publisher_mode == "EXCLUSIVE" else []

            # Clear stale api_sync entries for this billing_id before inserting new ones
            await pretargeting_service.clear_sync_publishers(billing_id)

            # Insert WHITELIST publishers (included)
            for pub_id in included_publishers:
                await pretargeting_service.add_publisher(
                    billing_id=billing_id,
                    publisher_id=str(pub_id),
                    mode="WHITELIST",
                    status="active",
                    source="api_sync",
                )
                publishers_synced += 1

            # Insert BLACKLIST publishers (excluded)
            for pub_id in excluded_publishers:
                await pretargeting_service.add_publisher(
                    billing_id=billing_id,
                    publisher_id=str(pub_id),
                    mode="BLACKLIST",
                    status="active",
                    source="api_sync",
                )
                publishers_synced += 1

        logger.info(f"Synced {publishers_synced} publisher targeting entries")

        # Prune local configs that Google no longer returns for this bidder.
        live_config_ids = [cfg["configId"] for cfg in configs]
        pruned = await pretargeting_service.delete_stale_configs(account_id, live_config_ids)
        if pruned:
            logger.info(f"Pruned {pruned} stale pretargeting config(s) for bidder {account_id}")

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
    limit: Optional[int] = Query(None, description="Optional max rows for startup/bootstrap views", ge=1, le=5000),
    summary_only: bool = Query(False, description="Return lightweight rows for startup (omits large targeting arrays)"),
    seats_service: SeatsService = Depends(get_seats_service),
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
        pretargeting_service = PretargetingService()

        # Buyer-scoped requests can resolve configs in one SQL query.
        if buyer_id:
            rows = await pretargeting_service.list_configs_for_buyer(
                buyer_id,
                limit=limit,
                summary_only=summary_only,
            )
        else:
            # Get the current account's bidder_id
            current_bidder_id = None

            # Priority 1: Fall back to service_account_id (legacy support)
            if service_account_id:
                service_account = await seats_service.get_service_account(service_account_id)
                if service_account:
                    current_bidder_id = await seats_service.get_bidder_id_for_service_account(service_account.id)

            # Priority 2: Fall back to first active service account
            if not current_bidder_id:
                accounts = await seats_service.get_service_accounts(active_only=True)
                if accounts:
                    current_bidder_id = await seats_service.get_bidder_id_for_service_account(accounts[0].id)

            # Priority 3: Fallback to any buyer_seat
            if not current_bidder_id:
                current_bidder_id = await seats_service.get_first_bidder_id()
                if current_bidder_id:
                    logger.info(f"Using fallback bidder_id: {current_bidder_id} for pretargeting list")

            # Get configs filtered by bidder_id
            rows = await pretargeting_service.list_configs(
                bidder_id=current_bidder_id,
                limit=limit,
                summary_only=summary_only,
            )

        results = []
        for row in rows:
            # Parse OS targeting and convert IDs to names if possible
            os_ids = _parse_json_field(row["included_operating_systems"])
            os_names = None
            if os_ids:
                # Map known OS IDs to human-readable names
                os_map = {"30001": "iOS", "30002": "Android"}
                os_names = [os_map.get(str(os_id), str(os_id)) for os_id in os_ids]
            maximum_qps = row.get("maximum_qps")
            if maximum_qps is None:
                raw_config = _parse_json_field(row.get("raw_config")) or {}
                maximum_qps = raw_config.get("maximumQps")
            if maximum_qps is not None:
                try:
                    maximum_qps = int(maximum_qps)
                except (TypeError, ValueError):
                    maximum_qps = None

            results.append(
                PretargetingConfigResponse(
                    config_id=row["config_id"],
                    bidder_id=row["bidder_id"],
                    billing_id=row["billing_id"],
                    display_name=row["display_name"],
                    user_name=row["user_name"],
                    state=row["state"] or "ACTIVE",
                    included_formats=_parse_json_field(row["included_formats"]),
                    included_platforms=_parse_json_field(row["included_platforms"]),
                    included_sizes=_parse_json_field(row["included_sizes"]),
                    included_geos=_parse_json_field(row["included_geos"]),
                    excluded_geos=_parse_json_field(row["excluded_geos"]),
                    maximum_qps=maximum_qps,
                    included_operating_systems=os_names,
                    synced_at=str(row["synced_at"]) if row["synced_at"] else None,
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

    This name will be displayed in the UI alongside the pretargeting
    config ID (`billing_id`),
    making it easier to identify configs.
    """
    try:
        # Get current value for history tracking
        pretargeting_service = PretargetingService()
        current = await pretargeting_service.get_config(billing_id)

        if not current:
            raise HTTPException(
                status_code=404,
                detail=f"Pretargeting config with ID (billing_id) {billing_id} not found"
            )

        old_name = current["user_name"]
        config_id = current["config_id"]
        bidder_id = current["bidder_id"]

        # Update the name
        await pretargeting_service.update_user_name(billing_id, body.user_name)

        # Record history if value changed
        if old_name != body.user_name:
            await pretargeting_service.add_history(
                config_id=str(config_id),
                bidder_id=str(bidder_id),
                change_type="update",
                field_changed="user_name",
                old_value=old_name,
                new_value=body.user_name,
                changed_by="ui",
                change_source="user",
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
    billing_id: Optional[str] = Query(
        None,
        description="Filter by pretargeting config ID (billing_id)",
    ),
    days: int = Query(30, description="Number of days of history to retrieve", ge=1, le=365),
):
    """Get pretargeting settings change history.

    Returns a log of all changes made to pretargeting configurations,
    including who made the change and when.
    """
    try:
        pretargeting_service = PretargetingService()
        rows = await pretargeting_service.list_history(
            config_id=config_id,
            billing_id=billing_id,
            days=days,
            limit=500,
        )

        results = []
        for row in rows:
            rollback_context = None
            commit_context = None
            raw_context = row.get("raw_config_snapshot")
            if row.get("change_type") == "rollback":
                if isinstance(raw_context, str):
                    try:
                        parsed = json.loads(raw_context)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        rollback_context = parsed
                elif isinstance(raw_context, dict):
                    rollback_context = raw_context
            elif row.get("change_type") == "major_commit":
                if isinstance(raw_context, str):
                    try:
                        parsed = json.loads(raw_context)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        commit_context = parsed
                elif isinstance(raw_context, dict):
                    commit_context = raw_context
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
                    rollback_context=rollback_context,
                    commit_context=commit_context,
                )
            )

        return results

    except Exception as e:
        logger.error(f"Failed to get pretargeting history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pretargeting history: {str(e)}")


# =============================================================================
# Publisher Targeting Endpoints
# =============================================================================


@router.get("/settings/pretargeting/{billing_id}/publishers")
async def get_pretargeting_publishers(
    billing_id: str,
    mode: Optional[str] = Query(None, description="Filter by mode (WHITELIST or BLACKLIST)"),
    status: Optional[str] = Query(None, description="Filter by status (active, pending_add, pending_remove)"),
):
    """Get normalized publisher list for a pretargeting config.

    Returns the list of publishers in the whitelist/blacklist with their status.
    """
    try:
        pretargeting_service = PretargetingService()
        rows = await pretargeting_service.list_publishers(
            billing_id=billing_id,
            mode=mode,
            status=status,
        )

        return {
            "billing_id": billing_id,
            "publishers": [
                {
                    "publisher_id": row["publisher_id"],
                    "mode": row["mode"],
                    "status": row["status"],
                    "source": row["source"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ],
            "count": len(rows),
        }

    except Exception as e:
        logger.error(f"Failed to get publishers for {billing_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/pretargeting/{billing_id}/publishers")
async def add_pretargeting_publisher(
    billing_id: str,
    publisher_id: str = Query(..., description="Publisher ID to add"),
    mode: str = Query(..., description="WHITELIST or BLACKLIST"),
):
    """Add a publisher to the targeting list with pending_add status.

    The publisher will be added with status 'pending_add' until the changes
    are applied via the pretargeting API.
    """
    try:
        # Validate mode
        mode = mode.strip().upper()
        if mode not in ("WHITELIST", "BLACKLIST"):
            raise HTTPException(status_code=400, detail="Mode must be WHITELIST or BLACKLIST")

        pretargeting_service = PretargetingService()
        change_service = ChangesService()

        config, existing, pending_changes, pending_publisher_changes = await asyncio.gather(
            pretargeting_service.get_config(billing_id),
            pretargeting_service.check_publisher_in_opposite_mode(
                billing_id,
                publisher_id,
                mode,
            ),
            change_service.list_pending_changes(
                billing_id=billing_id,
                status="pending",
                limit=500,
            ),
            pretargeting_service.list_pending_publisher_changes(billing_id),
        )

        if not config:
            raise HTTPException(status_code=404, detail=f"Pretargeting config {billing_id} not found")

        active_major_type = _resolve_active_major_change_type(
            pending_changes=pending_changes,
            has_pending_publisher_changes=bool(pending_publisher_changes),
        )
        if active_major_type == "mixed":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Pending changes already span multiple major change types. "
                    "Commit or clear current pending changes before staging more."
                ),
            )
        if active_major_type and active_major_type != "publisher":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Only one major change type can be staged per commit "
                    f"(current={active_major_type}, requested=publisher). "
                    "Commit or clear pending changes first."
                ),
            )

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Publisher {publisher_id} already exists in {existing['mode']} list"
            )

        await pretargeting_service.add_publisher(
            billing_id=billing_id,
            publisher_id=publisher_id,
            mode=mode,
            status="pending_add",
            source="user",
        )

        return {"status": "success", "message": f"Publisher {publisher_id} queued for addition to {mode}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add publisher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/settings/pretargeting/{billing_id}/publishers/{publisher_id}")
async def remove_pretargeting_publisher(
    billing_id: str,
    publisher_id: str,
    mode: Optional[str] = Query(None, description="WHITELIST or BLACKLIST"),
):
    """Mark a publisher for removal with pending_remove status.

    The publisher will be marked as 'pending_remove' until the changes
    are applied via the pretargeting API.
    """
    try:
        resolved_mode = None
        if mode:
            resolved_mode = mode.strip().upper()
            if resolved_mode not in ("WHITELIST", "BLACKLIST"):
                raise HTTPException(status_code=400, detail="Mode must be WHITELIST or BLACKLIST")

        pretargeting_service = PretargetingService()
        change_service = ChangesService()
        publisher_rows_task = (
            pretargeting_service.list_publishers(billing_id=billing_id)
            if not resolved_mode
            else asyncio.sleep(0, result=None)
        )
        config, rows, pending_changes, pending_publisher_changes = await asyncio.gather(
            pretargeting_service.get_config(billing_id),
            publisher_rows_task,
            change_service.list_pending_changes(
                billing_id=billing_id,
                status="pending",
                limit=500,
            ),
            pretargeting_service.list_pending_publisher_changes(billing_id),
        )
        if not config:
            raise HTTPException(status_code=404, detail=f"Pretargeting config {billing_id} not found")

        active_major_type = _resolve_active_major_change_type(
            pending_changes=pending_changes,
            has_pending_publisher_changes=bool(pending_publisher_changes),
        )
        if active_major_type == "mixed":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Pending changes already span multiple major change types. "
                    "Commit or clear current pending changes before staging more."
                ),
            )
        if active_major_type and active_major_type != "publisher":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Only one major change type can be staged per commit "
                    f"(current={active_major_type}, requested=publisher). "
                    "Commit or clear pending changes first."
                ),
            )

        if not resolved_mode:
            assert isinstance(rows, list)
            publisher_rows = [
                row for row in rows if str(row.get("publisher_id")) == str(publisher_id)
            ]
            if not publisher_rows:
                raise HTTPException(status_code=404, detail=f"Publisher {publisher_id} not found in config")
            modes = {row["mode"] for row in publisher_rows if row.get("mode")}
            if len(modes) == 1:
                resolved_mode = next(iter(modes))
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Publisher exists in multiple modes. Specify mode=WHITELIST or mode=BLACKLIST.",
                )

        await pretargeting_service.update_publisher_status(
            billing_id=billing_id,
            publisher_id=publisher_id,
            mode=resolved_mode,
            status="pending_remove",
        )
        return {
            "status": "success",
            "message": f"Publisher {publisher_id} queued for removal from {resolved_mode}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove publisher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/pretargeting/{billing_id}/publishers/pending")
async def get_pending_publisher_changes(
    billing_id: str,
):
    """Get publishers with pending changes (pending_add or pending_remove).

    Returns publishers that need to be synced to the API.
    """
    try:
        pretargeting_service = PretargetingService()
        rows = await pretargeting_service.list_pending_publisher_changes(billing_id)

        return {
            "billing_id": billing_id,
            "pending_changes": [
                {
                    "publisher_id": row["publisher_id"],
                    "mode": row["mode"],
                    "status": row["status"],
                    "source": row["source"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ],
            "count": len(rows),
        }

    except Exception as e:
        logger.error(f"Failed to get pending changes for {billing_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
