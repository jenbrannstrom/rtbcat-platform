"""Pretargeting apply/suspend/activate/rollback routes."""

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
    ApplyAllResponse,
    ApplyChangeRequest,
    ApplyChangeResponse,
    RollbackRequest,
    RollbackResponse,
    SnapshotCreate,
    SuspendActivateResponse,
)
from .snapshots import create_pretargeting_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


async def _get_pretargeting_client(billing_id: str, store: SQLiteStore):
    """Helper to get PretargetingClient for a billing_id."""
    # Get config and bidder_id
    config = await db_query_one(
        "SELECT bidder_id, config_id FROM pretargeting_configs WHERE billing_id = ?",
        (billing_id,)
    )
    if not config:
        raise HTTPException(status_code=404, detail=f"Config not found for billing_id: {billing_id}")

    bidder_id = config["bidder_id"]
    config_id = config["config_id"]

    # Get service account credentials
    accounts = await store.get_service_accounts(active_only=True)
    if not accounts:
        raise HTTPException(status_code=400, detail="No service account configured")

    service_account = accounts[0]
    creds_path = Path(service_account.credentials_path).expanduser()
    if not creds_path.exists():
        raise HTTPException(status_code=400, detail="Credentials file not found")

    client = PretargetingClient(
        credentials_path=str(creds_path),
        account_id=bidder_id,
    )

    return client, config_id, bidder_id


@router.post("/settings/pretargeting/{billing_id}/apply", response_model=ApplyChangeResponse)
async def apply_pending_change(
    billing_id: str,
    request: ApplyChangeRequest,
    store: SQLiteStore = Depends(get_store),
):
    """
    Apply a single pending change to Google Authorized Buyers.

    WARNING: This modifies your live pretargeting configuration!
    Use dry_run=True (default) to preview changes first.

    Supports:
    - add_size / remove_size
    - add_geo / remove_geo
    - add_format / remove_format
    - add_publisher / remove_publisher
    - set_publisher_mode
    """
    try:
        # Get the pending change
        change = await db_query_one(
            "SELECT * FROM pretargeting_pending_changes WHERE id = ? AND billing_id = ?",
            (request.change_id, billing_id)
        )

        if not change:
            raise HTTPException(status_code=404, detail="Pending change not found")

        if change["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Change is not pending: {change['status']}")

        if request.dry_run:
            return ApplyChangeResponse(
                status="dry_run",
                change_id=request.change_id,
                dry_run=True,
                message=f"Would apply {change['change_type']}: {change['value']} to {change['field_name']}",
            )

        # Get client
        client, config_id, bidder_id = await _get_pretargeting_client(billing_id, store)

        # Apply the change based on type
        change_type = change["change_type"]
        value = change["value"]

        if change_type == "add_size":
            parts = value.split("x")
            size = {"width": int(parts[0]), "height": int(parts[1])}
            result = await client.add_sizes_to_config(config_id, [size])
        elif change_type == "remove_size":
            parts = value.split("x")
            size = {"width": int(parts[0]), "height": int(parts[1])}
            result = await client.remove_sizes_from_config(config_id, [size])
        elif change_type == "add_geo":
            result = await client.add_geos_to_config(config_id, [value])
        elif change_type == "remove_geo":
            result = await client.remove_geos_from_config(config_id, [value])
        elif change_type == "add_excluded_geo":
            result = await client.add_geos_to_config(config_id, [value], exclude=True)
        elif change_type == "remove_excluded_geo":
            result = await client.remove_geos_from_config(config_id, [value], from_excluded=True)
        elif change_type in {"add_publisher", "remove_publisher", "set_publisher_mode"}:
            config_row = await db_query_one(
                "SELECT raw_config FROM pretargeting_configs WHERE billing_id = ?",
                (billing_id,)
            )
            raw_config = json.loads(config_row["raw_config"]) if config_row and config_row["raw_config"] else {}
            publisher_targeting = raw_config.get("publisherTargeting") or {}
            current_mode = publisher_targeting.get("targetingMode") or "EXCLUSIVE"
            current_values = list(publisher_targeting.get("values") or [])

            if change_type == "set_publisher_mode":
                updated_mode = value
                updated_values = []
            else:
                updated_mode = current_mode
                updated_values = current_values.copy()
                if change_type == "add_publisher" and value not in updated_values:
                    updated_values.append(value)
                elif change_type == "remove_publisher" and value in updated_values:
                    updated_values.remove(value)

            update_body = {
                "publisherTargeting": {
                    "targetingMode": updated_mode,
                    "values": updated_values,
                }
            }
            result = await client.patch_pretargeting_config(
                config_id=config_id,
                update_body=update_body,
                update_mask="publisherTargeting",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported change type: {change_type}")

        # Mark change as applied
        await db_execute(
            """UPDATE pretargeting_pending_changes
            SET status = 'applied', applied_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (request.change_id,)
        )

        # Record in history
        await db_execute(
            """INSERT INTO pretargeting_history
            (config_id, bidder_id, change_type, field_changed, new_value, change_source, changed_by)
            VALUES (?, ?, 'api_write', ?, ?, 'api', 'system')""",
            (config_id, bidder_id, change["field_name"], f"{change_type}:{value}")
        )

        return ApplyChangeResponse(
            status="applied",
            change_id=request.change_id,
            dry_run=False,
            message=f"Successfully applied {change_type}: {value}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply change: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/apply-all", response_model=ApplyAllResponse)
async def apply_all_pending_changes(
    billing_id: str,
    dry_run: bool = Query(True, description="Preview changes without applying"),
    store: SQLiteStore = Depends(get_store),
):
    """
    Apply all pending changes for a billing_id to Google.

    WARNING: This modifies your live pretargeting configuration!
    Use dry_run=True (default) to preview changes first.
    """
    try:
        # Get all pending changes for this billing_id
        changes = await db_query(
            """SELECT * FROM pretargeting_pending_changes
            WHERE billing_id = ? AND status = 'pending'
            ORDER BY created_at ASC""",
            (billing_id,)
        )

        if not changes:
            return ApplyAllResponse(
                status="no_changes",
                dry_run=dry_run,
                changes_applied=0,
                changes_failed=0,
                message="No pending changes to apply",
            )

        if dry_run:
            change_list = [f"{c['change_type']}: {c['value']}" for c in changes]
            return ApplyAllResponse(
                status="dry_run",
                dry_run=True,
                changes_applied=0,
                changes_failed=0,
                message=f"Would apply {len(changes)} changes: {', '.join(change_list)}",
            )

        # Create snapshot before applying
        snapshot_request = SnapshotCreate(
            billing_id=billing_id,
            snapshot_name="Auto-snapshot before changes",
            notes="Created before applying pending changes",
            snapshot_type="before_change",
        )
        await create_pretargeting_snapshot(snapshot_request)

        # Apply each change
        applied = 0
        failed = 0

        for change in changes:
            try:
                await apply_pending_change(
                    billing_id=billing_id,
                    request=ApplyChangeRequest(change_id=change["id"], dry_run=False),
                    store=store,
                )
                applied += 1
            except Exception as e:
                logger.error(f"Failed to apply change {change['id']}: {e}")
                failed += 1

        return ApplyAllResponse(
            status="completed",
            dry_run=False,
            changes_applied=applied,
            changes_failed=failed,
            message=f"Applied {applied} changes, {failed} failed",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply all changes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply all changes: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/suspend", response_model=SuspendActivateResponse)
async def suspend_pretargeting_config(
    billing_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """
    Suspend a pretargeting configuration.

    This immediately stops QPS from being consumed by this config.
    Creates an auto-snapshot before suspending for easy rollback.

    WARNING: This affects live bidding!
    """
    try:
        # Create auto-snapshot before suspending
        snapshot_request = SnapshotCreate(
            billing_id=billing_id,
            snapshot_name=f"Auto-snapshot before suspend",
            notes="Automatically created before suspend operation"
        )
        await create_pretargeting_snapshot(snapshot_request)

        # Get client
        client, config_id, bidder_id = await _get_pretargeting_client(billing_id, store)

        # Suspend the config
        result = await client.suspend_pretargeting_config(config_id)

        # Update local database
        await db_execute(
            "UPDATE pretargeting_configs SET state = 'SUSPENDED' WHERE billing_id = ?",
            (billing_id,)
        )

        # Record in history
        await db_execute(
            """INSERT INTO pretargeting_history
            (config_id, bidder_id, change_type, field_changed, old_value, new_value, change_source)
            VALUES (?, ?, 'state_change', 'state', 'ACTIVE', 'SUSPENDED', 'api')""",
            (config_id, bidder_id)
        )

        return SuspendActivateResponse(
            status="success",
            billing_id=billing_id,
            new_state="SUSPENDED",
            message="Config suspended. Auto-snapshot created for rollback.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to suspend config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to suspend config: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/activate", response_model=SuspendActivateResponse)
async def activate_pretargeting_config(
    billing_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """
    Activate a suspended pretargeting configuration.

    This resumes QPS consumption for this config.

    WARNING: This affects live bidding!
    """
    try:
        # Get client
        client, config_id, bidder_id = await _get_pretargeting_client(billing_id, store)

        # Activate the config
        result = await client.activate_pretargeting_config(config_id)

        # Update local database
        await db_execute(
            "UPDATE pretargeting_configs SET state = 'ACTIVE' WHERE billing_id = ?",
            (billing_id,)
        )

        # Record in history
        await db_execute(
            """INSERT INTO pretargeting_history
            (config_id, bidder_id, change_type, field_changed, old_value, new_value, change_source)
            VALUES (?, ?, 'state_change', 'state', 'SUSPENDED', 'ACTIVE', 'api')""",
            (config_id, bidder_id)
        )

        return SuspendActivateResponse(
            status="success",
            billing_id=billing_id,
            new_state="ACTIVE",
            message="Config activated. QPS consumption resumed.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to activate config: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/rollback", response_model=RollbackResponse)
async def rollback_to_snapshot(
    billing_id: str,
    request: RollbackRequest,
    store: SQLiteStore = Depends(get_store),
):
    """
    Rollback a pretargeting config to a previous snapshot state.

    This restores the config to its state at the time of the snapshot.
    Use dry_run=True (default) to preview what would change.

    WARNING: This modifies your live pretargeting configuration!
    """
    try:
        # Get the snapshot
        snapshot = await db_query_one(
            "SELECT * FROM pretargeting_snapshots WHERE id = ? AND billing_id = ?",
            (request.snapshot_id, billing_id)
        )

        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        # Get current config
        current = await db_query_one(
            "SELECT * FROM pretargeting_configs WHERE billing_id = ?",
            (billing_id,)
        )

        if not current:
            raise HTTPException(status_code=404, detail="Config not found")

        # Compare and determine changes needed
        changes = []

        current_sizes = set(json.loads(current["included_sizes"]) if current["included_sizes"] else [])
        snapshot_sizes = set(json.loads(snapshot["included_sizes"]) if snapshot["included_sizes"] else [])
        current_geos = set(json.loads(current["included_geos"]) if current["included_geos"] else [])
        snapshot_geos = set(json.loads(snapshot["included_geos"]) if snapshot["included_geos"] else [])
        current_formats = set(json.loads(current["included_formats"]) if current["included_formats"] else [])
        snapshot_formats = set(json.loads(snapshot["included_formats"]) if snapshot["included_formats"] else [])

        # Sizes to add (in snapshot but not in current)
        for size in snapshot_sizes - current_sizes:
            changes.append(f"add_size: {size}")

        # Sizes to remove (in current but not in snapshot)
        for size in current_sizes - snapshot_sizes:
            changes.append(f"remove_size: {size}")

        # Geos to add
        for geo in snapshot_geos - current_geos:
            changes.append(f"add_geo: {geo}")

        # Geos to remove
        for geo in current_geos - snapshot_geos:
            changes.append(f"remove_geo: {geo}")

        # Formats to add
        for fmt in snapshot_formats - current_formats:
            changes.append(f"add_format: {fmt}")

        # Formats to remove
        for fmt in current_formats - snapshot_formats:
            changes.append(f"remove_format: {fmt}")

        # State change
        if snapshot["state"] and current["state"] != snapshot["state"]:
            changes.append(f"state: {current['state']} -> {snapshot['state']}")

        if not changes:
            return RollbackResponse(
                status="no_changes",
                dry_run=request.dry_run,
                snapshot_id=request.snapshot_id,
                changes_made=[],
                message="Config matches snapshot - no changes needed",
            )

        if request.dry_run:
            return RollbackResponse(
                status="dry_run",
                dry_run=True,
                snapshot_id=request.snapshot_id,
                changes_made=changes,
                message=f"Would apply {len(changes)} changes to restore snapshot",
            )

        # Get client and apply changes
        client, config_id, bidder_id = await _get_pretargeting_client(billing_id, store)

        # Build update body from snapshot
        snapshot_dims = []
        for size_str in snapshot_sizes:
            parts = size_str.split("x")
            if len(parts) == 2:
                snapshot_dims.append({"width": int(parts[0]), "height": int(parts[1])})

        snapshot_publisher_mode = snapshot.get("publisher_targeting_mode")
        snapshot_publisher_values = json.loads(snapshot["publisher_targeting_values"]) if snapshot.get("publisher_targeting_values") else []

        update_body = {
            "includedCreativeDimensions": snapshot_dims,
            "geoTargeting": {
                "includedIds": list(snapshot_geos),
                "excludedIds": json.loads(snapshot["excluded_geos"]) if snapshot["excluded_geos"] else [],
            },
            "includedFormats": list(snapshot_formats),
        }
        update_mask = ["includedCreativeDimensions", "geoTargeting", "includedFormats"]

        if snapshot_publisher_mode is not None:
            update_body["publisherTargeting"] = {
                "targetingMode": snapshot_publisher_mode,
                "values": snapshot_publisher_values,
            }
            update_mask.append("publisherTargeting")

        # Apply the rollback
        await client.patch_pretargeting_config(
            config_id=config_id,
            update_body=update_body,
            update_mask=",".join(update_mask),
        )

        # Handle state change if needed
        if snapshot["state"] == "SUSPENDED" and current["state"] == "ACTIVE":
            await client.suspend_pretargeting_config(config_id)
        elif snapshot["state"] == "ACTIVE" and current["state"] == "SUSPENDED":
            await client.activate_pretargeting_config(config_id)

        # Record in history
        await db_execute(
            """INSERT INTO pretargeting_history
            (config_id, bidder_id, change_type, field_changed, new_value, change_source)
            VALUES (?, ?, 'rollback', 'all', ?, 'api')""",
            (config_id, bidder_id, f"snapshot_{request.snapshot_id}")
        )

        return RollbackResponse(
            status="applied",
            dry_run=False,
            snapshot_id=request.snapshot_id,
            changes_made=changes,
            message=f"Rolled back to snapshot. Applied {len(changes)} changes.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rollback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")
