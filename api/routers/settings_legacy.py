"""RTB Settings Router - Endpoints and Pretargeting configuration.

Handles RTB endpoint sync and pretargeting configuration management
from the Google Authorized Buyers API.

NOTE: This is a legacy monolithic file (1,846 lines) being refactored.
Models have been extracted to api/routers/settings/models.py.
Routes will be split into:
- settings/endpoints.py: RTB endpoints sync and management
- settings/pretargeting.py: Pretargeting config management
- settings/snapshots.py: Config snapshots and comparisons
- settings/changes.py: Pending changes queue
- settings/actions.py: Apply, suspend, activate, rollback

See api/routers/settings/__init__.py for the migration plan.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from config import ConfigManager
from storage.database import db_query, db_query_one, db_execute, db_insert_returning_id, db_transaction_async
from api.dependencies import get_config, get_store
from storage.sqlite_store import SQLiteStore
from collectors import PretargetingClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


# =============================================================================
# Pydantic Models
# =============================================================================

class RTBEndpointItem(BaseModel):
    """Individual RTB endpoint data."""
    endpoint_id: str
    url: str
    maximum_qps: Optional[int] = None
    trading_location: Optional[str] = None
    bid_protocol: Optional[str] = None


class RTBEndpointsResponse(BaseModel):
    """Response model for RTB endpoints with aggregated data."""
    bidder_id: str
    account_name: Optional[str] = None
    endpoints: list[RTBEndpointItem]
    total_qps_allocated: int
    qps_current: Optional[int] = None
    synced_at: Optional[str] = None


class PretargetingConfigResponse(BaseModel):
    """Response model for a pretargeting config."""
    config_id: str
    bidder_id: str
    billing_id: Optional[str] = None
    display_name: Optional[str] = None
    user_name: Optional[str] = None
    state: str = "ACTIVE"
    included_formats: Optional[list[str]] = None
    included_platforms: Optional[list[str]] = None
    included_sizes: Optional[list[str]] = None
    included_geos: Optional[list[str]] = None
    excluded_geos: Optional[list[str]] = None
    included_operating_systems: Optional[list[str]] = None  # iOS, Android IDs
    synced_at: Optional[str] = None


class SyncEndpointsResponse(BaseModel):
    """Response model for sync endpoints operation."""
    status: str
    endpoints_synced: int
    bidder_id: str


class SyncPretargetingResponse(BaseModel):
    """Response model for sync pretargeting configs operation."""
    status: str
    configs_synced: int
    bidder_id: str


class SetPretargetingNameRequest(BaseModel):
    """Request body for setting a custom pretargeting config name."""
    user_name: str = Field(..., description="Custom name for this pretargeting config")


class PretargetingHistoryResponse(BaseModel):
    """Response model for pretargeting history entry."""
    id: int
    config_id: str
    bidder_id: str
    change_type: str
    field_changed: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: str
    changed_by: Optional[str] = None
    change_source: str


# Pretargeting Snapshot Endpoints
# =============================================================================

class SnapshotCreate(BaseModel):
    """Request to create a snapshot of a pretargeting config."""
    billing_id: str
    snapshot_name: Optional[str] = None
    notes: Optional[str] = None


class SnapshotResponse(BaseModel):
    """Response model for a pretargeting snapshot."""
    id: int
    billing_id: str
    snapshot_name: Optional[str] = None
    snapshot_type: str
    state: Optional[str] = None
    included_formats: Optional[str] = None
    included_platforms: Optional[str] = None
    included_sizes: Optional[str] = None
    included_geos: Optional[str] = None
    excluded_geos: Optional[str] = None
    total_impressions: int
    total_clicks: int
    total_spend_usd: float
    days_tracked: int
    avg_daily_impressions: Optional[float] = None
    avg_daily_spend_usd: Optional[float] = None
    ctr_pct: Optional[float] = None
    cpm_usd: Optional[float] = None
    created_at: str
    notes: Optional[str] = None


class ComparisonCreate(BaseModel):
    """Request to start a new A/B comparison."""
    billing_id: str
    comparison_name: str
    before_snapshot_id: int
    before_start_date: str
    before_end_date: str


class ComparisonResponse(BaseModel):
    """Response model for a snapshot comparison."""
    id: int
    billing_id: str
    comparison_name: str
    before_snapshot_id: int
    after_snapshot_id: Optional[int] = None
    before_start_date: str
    before_end_date: str
    after_start_date: Optional[str] = None
    after_end_date: Optional[str] = None
    impressions_delta: Optional[int] = None
    impressions_delta_pct: Optional[float] = None
    spend_delta_usd: Optional[float] = None
    spend_delta_pct: Optional[float] = None
    ctr_delta_pct: Optional[float] = None
    cpm_delta_pct: Optional[float] = None
    status: str
    conclusion: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


@router.post("/settings/pretargeting/snapshot", response_model=SnapshotResponse)
async def create_pretargeting_snapshot(request: SnapshotCreate):
    """
    Create a snapshot of a pretargeting config's current state and performance.

    This captures:
    - Current config settings (geos, sizes, formats, etc.)
    - Accumulated performance metrics up to now
    - Computed averages (daily impressions, spend, CTR, CPM)

    Use this before making changes to track the "before" state.
    """
    try:
        # Get current config state
        config = await db_query_one(
            """SELECT * FROM pretargeting_configs WHERE billing_id = ?""",
            (request.billing_id,)
        )

        if not config:
            raise HTTPException(status_code=404, detail=f"Config not found for billing_id: {request.billing_id}")

        # Get accumulated performance for this billing_id
        # Try rtb_daily first (new schema), fallback to performance_metrics (old schema)
        perf = await db_query_one(
            """SELECT
                COUNT(DISTINCT metric_date) as days_tracked,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                SUM(spend_micros) / 1000000.0 as total_spend_usd
            FROM rtb_daily
            WHERE billing_id = ?""",
            (request.billing_id,)
        )

        # If no data in rtb_daily, try performance_metrics
        if not perf or perf["days_tracked"] == 0:
            perf = await db_query_one(
                """SELECT
                    COUNT(DISTINCT metric_date) as days_tracked,
                    SUM(impressions) as total_impressions,
                    SUM(clicks) as total_clicks,
                    SUM(spend_micros) / 1000000.0 as total_spend_usd
                FROM performance_metrics
                WHERE billing_id = ?""",
                (request.billing_id,)
            )

        days = perf["days_tracked"] or 0 if perf else 0
        imps = perf["total_impressions"] or 0 if perf else 0
        clicks = perf["total_clicks"] or 0 if perf else 0
        spend = perf["total_spend_usd"] or 0 if perf else 0

        # Compute averages
        avg_daily_imps = imps / days if days > 0 else None
        avg_daily_spend = spend / days if days > 0 else None
        ctr = (clicks / imps * 100) if imps > 0 else None
        cpm = (spend / imps * 1000) if imps > 0 else None

        # Create snapshot
        snapshot_id = await db_insert_returning_id(
            """INSERT INTO pretargeting_snapshots (
                billing_id, snapshot_name, snapshot_type,
                included_formats, included_platforms, included_sizes,
                included_geos, excluded_geos, state,
                total_impressions, total_clicks, total_spend_usd,
                days_tracked,
                avg_daily_impressions, avg_daily_spend_usd, ctr_pct, cpm_usd,
                notes
            ) VALUES (?, ?, 'manual', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.billing_id,
                request.snapshot_name,
                config["included_formats"],
                config["included_platforms"],
                config["included_sizes"],
                config["included_geos"],
                config["excluded_geos"],
                config["state"],
                imps, clicks, spend, days,
                avg_daily_imps, avg_daily_spend, ctr, cpm,
                request.notes
            )
        )

        # Fetch the created snapshot
        row = await db_query_one(
            "SELECT * FROM pretargeting_snapshots WHERE id = ?",
            (snapshot_id,)
        )

        return SnapshotResponse(
            id=row["id"],
            billing_id=row["billing_id"],
            snapshot_name=row["snapshot_name"],
            snapshot_type=row["snapshot_type"],
            state=row["state"],
            included_formats=row["included_formats"],
            included_platforms=row["included_platforms"],
            included_sizes=row["included_sizes"],
            included_geos=row["included_geos"],
            excluded_geos=row["excluded_geos"],
            total_impressions=row["total_impressions"],
            total_clicks=row["total_clicks"],
            total_spend_usd=row["total_spend_usd"],
            days_tracked=row["days_tracked"],
            avg_daily_impressions=row["avg_daily_impressions"],
            avg_daily_spend_usd=row["avg_daily_spend_usd"],
            ctr_pct=row["ctr_pct"],
            cpm_usd=row["cpm_usd"],
            created_at=row["created_at"],
            notes=row["notes"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create snapshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {str(e)}")


@router.get("/settings/pretargeting/snapshots", response_model=list[SnapshotResponse])
async def list_pretargeting_snapshots(
    billing_id: Optional[str] = Query(None, description="Filter by billing account"),
    limit: int = Query(50, ge=1, le=200),
):
    """List pretargeting snapshots, optionally filtered by billing account."""
    try:
        if billing_id:
            rows = await db_query(
                """SELECT * FROM pretargeting_snapshots
                WHERE billing_id = ?
                ORDER BY created_at DESC
                LIMIT ?""",
                (billing_id, limit)
            )
        else:
            rows = await db_query(
                """SELECT * FROM pretargeting_snapshots
                ORDER BY created_at DESC
                LIMIT ?""",
                (limit,)
            )

        return [
            SnapshotResponse(
                id=row["id"],
                billing_id=row["billing_id"],
                snapshot_name=row["snapshot_name"],
                snapshot_type=row["snapshot_type"],
                state=row["state"],
                included_formats=row["included_formats"],
                included_platforms=row["included_platforms"],
                included_sizes=row["included_sizes"],
                included_geos=row["included_geos"],
                excluded_geos=row["excluded_geos"],
                total_impressions=row["total_impressions"],
                total_clicks=row["total_clicks"],
                total_spend_usd=row["total_spend_usd"],
                days_tracked=row["days_tracked"],
                avg_daily_impressions=row["avg_daily_impressions"],
                avg_daily_spend_usd=row["avg_daily_spend_usd"],
                ctr_pct=row["ctr_pct"],
                cpm_usd=row["cpm_usd"],
                created_at=row["created_at"],
                notes=row["notes"],
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list snapshots: {str(e)}")


@router.post("/settings/pretargeting/comparison", response_model=ComparisonResponse)
async def create_comparison(request: ComparisonCreate):
    """
    Start a new A/B comparison for a pretargeting config.

    This creates a comparison record linking to a "before" snapshot.
    After making changes to the config, use the complete endpoint to
    capture the "after" snapshot and compute deltas.
    """
    try:
        # Verify before_snapshot exists
        snapshot = await db_query_one(
            "SELECT * FROM pretargeting_snapshots WHERE id = ?",
            (request.before_snapshot_id,)
        )

        if not snapshot:
            raise HTTPException(status_code=404, detail="Before snapshot not found")

        # Create comparison
        comparison_id = await db_insert_returning_id(
            """INSERT INTO snapshot_comparisons (
                billing_id, comparison_name, before_snapshot_id,
                before_start_date, before_end_date, status
            ) VALUES (?, ?, ?, ?, ?, 'in_progress')""",
            (
                request.billing_id,
                request.comparison_name,
                request.before_snapshot_id,
                request.before_start_date,
                request.before_end_date,
            )
        )

        row = await db_query_one(
            "SELECT * FROM snapshot_comparisons WHERE id = ?",
            (comparison_id,)
        )

        return ComparisonResponse(
            id=row["id"],
            billing_id=row["billing_id"],
            comparison_name=row["comparison_name"],
            before_snapshot_id=row["before_snapshot_id"],
            after_snapshot_id=row["after_snapshot_id"],
            before_start_date=row["before_start_date"],
            before_end_date=row["before_end_date"],
            after_start_date=row["after_start_date"],
            after_end_date=row["after_end_date"],
            impressions_delta=row["impressions_delta"],
            impressions_delta_pct=row["impressions_delta_pct"],
            spend_delta_usd=row["spend_delta_usd"],
            spend_delta_pct=row["spend_delta_pct"],
            ctr_delta_pct=row["ctr_delta_pct"],
            cpm_delta_pct=row["cpm_delta_pct"],
            status=row["status"],
            conclusion=row["conclusion"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create comparison: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create comparison: {str(e)}")


@router.get("/settings/pretargeting/comparisons", response_model=list[ComparisonResponse])
async def list_comparisons(
    billing_id: Optional[str] = Query(None, description="Filter by billing account"),
    status: Optional[str] = Query(None, description="Filter by status (in_progress, completed)"),
    limit: int = Query(50, ge=1, le=200),
):
    """List A/B comparisons, optionally filtered by billing account or status."""
    try:
        query = "SELECT * FROM snapshot_comparisons WHERE 1=1"
        params = []

        if billing_id:
            query += " AND billing_id = ?"
            params.append(billing_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await db_query(query, tuple(params))

        return [
            ComparisonResponse(
                id=row["id"],
                billing_id=row["billing_id"],
                comparison_name=row["comparison_name"],
                before_snapshot_id=row["before_snapshot_id"],
                after_snapshot_id=row["after_snapshot_id"],
                before_start_date=row["before_start_date"],
                before_end_date=row["before_end_date"],
                after_start_date=row["after_start_date"],
                after_end_date=row["after_end_date"],
                impressions_delta=row["impressions_delta"],
                impressions_delta_pct=row["impressions_delta_pct"],
                spend_delta_usd=row["spend_delta_usd"],
                spend_delta_pct=row["spend_delta_pct"],
                ctr_delta_pct=row["ctr_delta_pct"],
                cpm_delta_pct=row["cpm_delta_pct"],
                status=row["status"],
                conclusion=row["conclusion"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Failed to list comparisons: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list comparisons: {str(e)}")


# =============================================================================
# Pretargeting Pending Changes Endpoints (Local-Only - NO Google API Writes)
# =============================================================================

class PendingChangeCreate(BaseModel):
    """Request to create a pending change to a pretargeting config."""
    billing_id: str
    change_type: str = Field(..., description="Type: add_size, remove_size, add_geo, remove_geo, add_format, remove_format, change_state")
    field_name: str = Field(..., description="Field: included_sizes, included_geos, excluded_geos, included_formats, state")
    value: str = Field(..., description="The value to add/remove (e.g., '300x250', 'US', 'HTML')")
    reason: Optional[str] = Field(None, description="User-provided reason for this change")
    estimated_qps_impact: Optional[float] = Field(None, description="Estimated QPS waste reduction")


class PendingChangeResponse(BaseModel):
    """Response model for a pending change."""
    id: int
    billing_id: str
    config_id: str
    change_type: str
    field_name: str
    value: str
    reason: Optional[str] = None
    estimated_qps_impact: Optional[float] = None
    created_at: str
    created_by: Optional[str] = None
    status: str


class ConfigDetailResponse(BaseModel):
    """Detailed config response including current state and pending changes."""
    config_id: str
    billing_id: str
    display_name: Optional[str] = None
    user_name: Optional[str] = None
    state: str
    # Current values from last sync
    included_formats: list[str]
    included_platforms: list[str]
    included_sizes: list[str]
    included_geos: list[str]
    excluded_geos: list[str]
    synced_at: Optional[str] = None
    # Pending changes
    pending_changes: list[PendingChangeResponse]
    # Computed effective values (current + pending applied)
    effective_sizes: list[str]
    effective_geos: list[str]
    effective_formats: list[str]


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
# Pretargeting Write Operations (Google API)
# =============================================================================

class ApplyChangeRequest(BaseModel):
    """Request to apply a pending change to Google."""
    change_id: int
    dry_run: bool = Field(True, description="If true, preview changes without applying")


class ApplyChangeResponse(BaseModel):
    """Response from applying a change to Google."""
    status: str
    change_id: int
    dry_run: bool
    message: str
    updated_config: Optional[PretargetingConfigResponse] = None


class ApplyAllResponse(BaseModel):
    """Response from applying all pending changes."""
    status: str
    dry_run: bool
    changes_applied: int
    changes_failed: int
    message: str


class SuspendActivateResponse(BaseModel):
    """Response from suspend/activate operation."""
    status: str
    billing_id: str
    new_state: str
    message: str


class RollbackRequest(BaseModel):
    """Request to rollback to a snapshot."""
    snapshot_id: int
    dry_run: bool = Field(True, description="If true, preview rollback without applying")


class RollbackResponse(BaseModel):
    """Response from rollback operation."""
    status: str
    dry_run: bool
    snapshot_id: int
    changes_made: list[str]
    message: str


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

        update_body = {
            "includedCreativeDimensions": snapshot_dims,
            "geoTargeting": {
                "includedIds": list(snapshot_geos),
                "excludedIds": json.loads(snapshot["excluded_geos"]) if snapshot["excluded_geos"] else [],
            },
            "includedFormats": list(snapshot_formats),
        }

        # Apply the rollback
        await client.patch_pretargeting_config(
            config_id=config_id,
            update_body=update_body,
            update_mask="includedCreativeDimensions,geoTargeting,includedFormats",
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
