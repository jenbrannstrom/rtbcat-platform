"""Pretargeting pending changes routes (local-only)."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from storage.database import db_execute, db_insert_returning_id, db_query, db_query_one

from .models import ConfigDetailResponse, PendingChangeCreate, PendingChangeResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


@router.post("/settings/pretargeting/pending-change", response_model=PendingChangeResponse)
async def create_pending_change(request: PendingChangeCreate):
    """
    Create a pending change to a pretargeting configuration.

    IMPORTANT: This does NOT modify the Google Authorized Buyers account.
    Changes are staged locally and can be reviewed before manual application.

    Use this to:
    - Block sizes that are wasting QPS
    - Add/remove geographic targeting
    - Add/remove format targeting

    The change will be recorded in the pending_changes table and can be:
    - Reviewed in the UI
    - Applied manually by the user in Google Authorized Buyers
    - Cancelled if no longer needed
    """
    # Validate change_type
    valid_change_types = [
        'add_size', 'remove_size',
        'add_geo', 'remove_geo',
        'add_format', 'remove_format',
        'add_excluded_geo', 'remove_excluded_geo',
        'change_state'
    ]
    if request.change_type not in valid_change_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid change_type. Must be one of: {', '.join(valid_change_types)}"
        )

    try:
        # Verify the config exists and get config_id
        config = await db_query_one(
            "SELECT config_id FROM pretargeting_configs WHERE billing_id = ?",
            (request.billing_id,)
        )

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Pretargeting config not found for billing_id: {request.billing_id}"
            )

        config_id = config["config_id"]

        # Insert the pending change
        change_id = await db_insert_returning_id(
            """INSERT INTO pretargeting_pending_changes (
                billing_id, config_id, change_type, field_name, value,
                reason, estimated_qps_impact, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (
                request.billing_id,
                config_id,
                request.change_type,
                request.field_name,
                request.value,
                request.reason,
                request.estimated_qps_impact,
            )
        )

        # Also log to pretargeting_history
        bidder_row = await db_query_one(
            "SELECT bidder_id FROM pretargeting_configs WHERE billing_id = ?",
            (request.billing_id,)
        )
        if bidder_row:
            await db_execute(
                """INSERT INTO pretargeting_history (
                    config_id, bidder_id, change_type, field_changed,
                    old_value, new_value, change_source, changed_by
                ) VALUES (?, ?, 'pending_change', ?, NULL, ?, 'user', 'ui')""",
                (config_id, bidder_row["bidder_id"], request.field_name, f"{request.change_type}:{request.value}")
            )

        # Fetch the created change
        row = await db_query_one(
            "SELECT * FROM pretargeting_pending_changes WHERE id = ?",
            (change_id,)
        )

        return PendingChangeResponse(
            id=row["id"],
            billing_id=row["billing_id"],
            config_id=row["config_id"],
            change_type=row["change_type"],
            field_name=row["field_name"],
            value=row["value"],
            reason=row["reason"],
            estimated_qps_impact=row["estimated_qps_impact"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            status=row["status"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create pending change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create pending change: {str(e)}")


@router.get("/settings/pretargeting/pending-changes", response_model=list[PendingChangeResponse])
async def list_pending_changes(
    billing_id: Optional[str] = Query(None, description="Filter by billing account"),
    status: str = Query("pending", description="Filter by status (pending, applied, cancelled)"),
    limit: int = Query(100, ge=1, le=500),
):
    """List pending changes to pretargeting configurations."""
    try:
        query = "SELECT * FROM pretargeting_pending_changes WHERE status = ?"
        params = [status]

        if billing_id:
            query += " AND billing_id = ?"
            params.append(billing_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await db_query(query, tuple(params))

        return [
            PendingChangeResponse(
                id=row["id"],
                billing_id=row["billing_id"],
                config_id=row["config_id"],
                change_type=row["change_type"],
                field_name=row["field_name"],
                value=row["value"],
                reason=row["reason"],
                estimated_qps_impact=row["estimated_qps_impact"],
                created_at=row["created_at"],
                created_by=row["created_by"],
                status=row["status"],
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Failed to list pending changes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list pending changes: {str(e)}")


@router.delete("/settings/pretargeting/pending-change/{change_id}")
async def cancel_pending_change(change_id: int):
    """Cancel a pending change (mark as cancelled, not deleted)."""
    try:
        # Check if change exists and is pending
        change = await db_query_one(
            "SELECT * FROM pretargeting_pending_changes WHERE id = ?",
            (change_id,)
        )

        if not change:
            raise HTTPException(status_code=404, detail="Pending change not found")

        if change["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Change cannot be cancelled - current status: {change['status']}"
            )

        # Mark as cancelled
        await db_execute(
            "UPDATE pretargeting_pending_changes SET status = 'cancelled' WHERE id = ?",
            (change_id,)
        )

        return {"status": "cancelled", "id": change_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel pending change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel pending change: {str(e)}")


@router.post("/settings/pretargeting/pending-change/{change_id}/mark-applied")
async def mark_change_applied(change_id: int):
    """
    Mark a pending change as applied (user has manually applied it in Google UI).

    This is for tracking purposes only - it does NOT make any API calls.
    """
    try:
        change = await db_query_one(
            "SELECT * FROM pretargeting_pending_changes WHERE id = ?",
            (change_id,)
        )

        if not change:
            raise HTTPException(status_code=404, detail="Pending change not found")

        if change["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Change is not pending - current status: {change['status']}"
            )

        await db_execute(
            """UPDATE pretargeting_pending_changes
            SET status = 'applied', applied_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (change_id,)
        )

        return {"status": "applied", "id": change_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark change as applied: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark change as applied: {str(e)}")


@router.get("/settings/pretargeting/{billing_id}/detail", response_model=ConfigDetailResponse)
async def get_pretargeting_config_detail(billing_id: str):
    """
    Get detailed pretargeting config including current state and pending changes.

    Returns:
    - Current config values (from last Google sync)
    - List of pending changes
    - Effective values (what the config would look like after pending changes)
    """
    try:
        # Get config
        config = await db_query_one(
            "SELECT * FROM pretargeting_configs WHERE billing_id = ?",
            (billing_id,)
        )

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Config not found for billing_id: {billing_id}"
            )

        # Get pending changes
        pending_rows = await db_query(
            """SELECT * FROM pretargeting_pending_changes
            WHERE billing_id = ? AND status = 'pending'
            ORDER BY created_at ASC""",
            (billing_id,)
        )

        # Parse current values
        included_sizes = json.loads(config["included_sizes"]) if config["included_sizes"] else []
        included_geos = json.loads(config["included_geos"]) if config["included_geos"] else []
        excluded_geos = json.loads(config["excluded_geos"]) if config["excluded_geos"] else []
        included_formats = json.loads(config["included_formats"]) if config["included_formats"] else []
        included_platforms = json.loads(config["included_platforms"]) if config["included_platforms"] else []

        # Build pending changes list
        pending_changes = [
            PendingChangeResponse(
                id=row["id"],
                billing_id=row["billing_id"],
                config_id=row["config_id"],
                change_type=row["change_type"],
                field_name=row["field_name"],
                value=row["value"],
                reason=row["reason"],
                estimated_qps_impact=row["estimated_qps_impact"],
                created_at=row["created_at"],
                created_by=row["created_by"],
                status=row["status"],
            )
            for row in pending_rows
        ]

        # Compute effective values (current + pending applied)
        effective_sizes = set(included_sizes)
        effective_geos = set(included_geos)
        effective_formats = set(included_formats)

        for change in pending_changes:
            if change.change_type == 'add_size':
                effective_sizes.add(change.value)
            elif change.change_type == 'remove_size':
                effective_sizes.discard(change.value)
            elif change.change_type == 'add_geo':
                effective_geos.add(change.value)
            elif change.change_type == 'remove_geo':
                effective_geos.discard(change.value)
            elif change.change_type == 'add_format':
                effective_formats.add(change.value)
            elif change.change_type == 'remove_format':
                effective_formats.discard(change.value)

        return ConfigDetailResponse(
            config_id=config["config_id"],
            billing_id=billing_id,
            display_name=config["display_name"],
            user_name=config["user_name"],
            state=config["state"] or "ACTIVE",
            included_formats=included_formats,
            included_platforms=included_platforms,
            included_sizes=included_sizes,
            included_geos=included_geos,
            excluded_geos=excluded_geos,
            synced_at=config["synced_at"],
            pending_changes=pending_changes,
            effective_sizes=sorted(list(effective_sizes)),
            effective_geos=sorted(list(effective_geos)),
            effective_formats=sorted(list(effective_formats)),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config detail: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get config detail: {str(e)}")


# =============================================================================
