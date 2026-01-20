"""Pretargeting snapshot and comparison routes."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from storage.database import db_execute, db_insert_returning_id, db_query, db_query_one

from .models import ComparisonCreate, ComparisonResponse, SnapshotCreate, SnapshotResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


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
