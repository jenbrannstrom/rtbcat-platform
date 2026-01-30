"""Pretargeting snapshot and comparison routes."""

import json
import logging
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_store
from storage.sqlite_store import SQLiteStore
from storage.postgres_store import PostgresStore

from .models import ComparisonCreate, ComparisonResponse, SnapshotCreate, SnapshotResponse

# Store type can be either SQLite or Postgres
StoreType = Union[SQLiteStore, PostgresStore]

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


@router.post("/settings/pretargeting/snapshot", response_model=SnapshotResponse)
async def create_pretargeting_snapshot(
    request: SnapshotCreate,
    store: StoreType = Depends(get_store),
):
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
        config = await store.get_pretargeting_config_by_billing_id(request.billing_id)

        if not config:
            raise HTTPException(status_code=404, detail=f"Config not found for billing_id: {request.billing_id}")

        # Get accumulated performance for this billing_id
        perf = await store.get_performance_aggregates(request.billing_id)

        days = perf.get("days_tracked", 0) or 0
        imps = perf.get("total_impressions", 0) or 0
        clicks = perf.get("total_clicks", 0) or 0
        spend = perf.get("total_spend_usd", 0) or 0

        # Compute averages
        avg_daily_imps = imps / days if days > 0 else None
        avg_daily_spend = spend / days if days > 0 else None
        ctr = (clicks / imps * 100) if imps > 0 else None
        cpm = (spend / imps * 1000) if imps > 0 else None

        raw_config = json.loads(config["raw_config"]) if config.get("raw_config") else {}
        publisher_targeting = raw_config.get("publisherTargeting") or {}
        publisher_mode = publisher_targeting.get("targetingMode")
        publisher_values = publisher_targeting.get("values") or []

        # Create snapshot using store method
        config_data = {
            "included_formats": config.get("included_formats"),
            "included_platforms": config.get("included_platforms"),
            "included_sizes": config.get("included_sizes"),
            "included_geos": config.get("included_geos"),
            "excluded_geos": config.get("excluded_geos"),
            "state": config.get("state"),
        }
        performance_data = {
            "total_impressions": imps,
            "total_clicks": clicks,
            "total_spend_usd": spend,
            "days_tracked": days,
            "avg_daily_impressions": avg_daily_imps,
            "avg_daily_spend_usd": avg_daily_spend,
            "ctr_pct": ctr,
            "cpm_usd": cpm,
        }

        snapshot_id = await store.create_snapshot(
            billing_id=request.billing_id,
            snapshot_name=request.snapshot_name,
            snapshot_type=request.snapshot_type or "manual",
            config_data=config_data,
            performance_data=performance_data,
            publisher_targeting_mode=publisher_mode,
            publisher_targeting_values=json.dumps(publisher_values) if publisher_values else None,
            notes=request.notes,
        )

        # Fetch the created snapshot
        row = await store.get_snapshot(snapshot_id)

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
    store: StoreType = Depends(get_store),
):
    """List pretargeting snapshots, optionally filtered by billing account."""
    try:
        rows = await store.list_snapshots(billing_id=billing_id, limit=limit)

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
async def create_comparison(
    request: ComparisonCreate,
    store: StoreType = Depends(get_store),
):
    """
    Start a new A/B comparison for a pretargeting config.

    This creates a comparison record linking to a "before" snapshot.
    After making changes to the config, use the complete endpoint to
    capture the "after" snapshot and compute deltas.
    """
    try:
        # Verify before_snapshot exists
        snapshot = await store.get_snapshot(request.before_snapshot_id)

        if not snapshot:
            raise HTTPException(status_code=404, detail="Before snapshot not found")

        # Create comparison
        comparison_id = await store.create_comparison(
            billing_id=request.billing_id,
            comparison_name=request.comparison_name,
            before_snapshot_id=request.before_snapshot_id,
            before_start_date=request.before_start_date,
            before_end_date=request.before_end_date,
        )

        row = await store.get_comparison(comparison_id)

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
    store: StoreType = Depends(get_store),
):
    """List A/B comparisons, optionally filtered by billing account or status."""
    try:
        rows = await store.list_comparisons(billing_id=billing_id, status=status, limit=limit)

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
