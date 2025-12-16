"""RTB Settings Router - Endpoints and Pretargeting configuration.

Handles RTB endpoint sync and pretargeting configuration management
from the Google Authorized Buyers API.
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
from collectors import EndpointsClient, PretargetingClient

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


# =============================================================================
# Endpoints
# =============================================================================

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
        (service_account.id,)
    )
    account_id = bidder_row["bidder_id"] if bidder_row else service_account.project_id

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
    service_account_id: Optional[str] = Query(None, description="Service account ID to filter by"),
    store: SQLiteStore = Depends(get_store),
):
    """Get stored RTB endpoints with aggregated QPS data.

    Returns all RTB endpoints that have been synced from the Google API,
    along with total allocated QPS and current usage.
    """
    try:
        # Get credentials for bidder_id from new multi-account system
        bidder_id = ""
        account_name = None

        if service_account_id:
            service_account = await store.get_service_account(service_account_id)
            if service_account:
                account_name = service_account.display_name
                bidder_row = await db_query_one(
                    "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
                    (service_account.id,)
                )
                if bidder_row:
                    bidder_id = bidder_row["bidder_id"]
        else:
            accounts = await store.get_service_accounts(active_only=True)
            if accounts:
                service_account = accounts[0]
                account_name = service_account.display_name
                bidder_row = await db_query_one(
                    "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
                    (service_account.id,)
                )
                if bidder_row:
                    bidder_id = bidder_row["bidder_id"]

        # Filter by bidder_id if we have one (account-specific)
        if bidder_id:
            rows = await db_query(
                "SELECT * FROM rtb_endpoints WHERE bidder_id = ? ORDER BY trading_location, endpoint_id",
                (bidder_id,)
            )
        else:
            rows = await db_query(
                "SELECT * FROM rtb_endpoints ORDER BY trading_location, endpoint_id"
            )

        endpoints = []
        total_qps = 0
        synced_at = None

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
            if row["synced_at"] and (synced_at is None or row["synced_at"] > synced_at):
                synced_at = row["synced_at"]
            if not bidder_id and row["bidder_id"]:
                bidder_id = row["bidder_id"]

        return RTBEndpointsResponse(
            bidder_id=bidder_id,
            account_name=account_name,
            endpoints=endpoints,
            total_qps_allocated=total_qps,
            qps_current=None,  # Would need real-time monitoring to populate
            synced_at=synced_at,
        )

    except Exception as e:
        logger.error(f"Failed to get RTB endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get endpoints: {str(e)}")


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
    account_id = bidder_row["bidder_id"] if bidder_row else service_account.project_id

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

            await db_execute(
                """
                INSERT INTO pretargeting_configs
                (bidder_id, config_id, billing_id, display_name, state,
                 included_formats, included_platforms, included_sizes,
                 included_geos, excluded_geos, raw_config, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bidder_id, config_id) DO UPDATE SET
                    billing_id = excluded.billing_id,
                    display_name = excluded.display_name,
                    state = excluded.state,
                    included_formats = excluded.included_formats,
                    included_platforms = excluded.included_platforms,
                    included_sizes = excluded.included_sizes,
                    included_geos = excluded.included_geos,
                    excluded_geos = excluded.excluded_geos,
                    raw_config = excluded.raw_config,
                    synced_at = CURRENT_TIMESTAMP
                """,
                (
                    account_id,
                    cfg["configId"],
                    cfg.get("billingId"),
                    cfg.get("displayName"),
                    cfg.get("state", "ACTIVE"),
                    json.dumps(cfg.get("includedFormats", [])),
                    json.dumps(cfg.get("includedPlatforms", [])),
                    json.dumps(sizes),
                    json.dumps(included_geos),
                    json.dumps(excluded_geos),
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
    service_account_id: Optional[str] = Query(None, description="Service account ID to filter by"),
    store: SQLiteStore = Depends(get_store),
):
    """Get stored pretargeting configs for the current account.

    Returns pretargeting configurations that have been synced from the Google API
    for the currently configured account (bidder_id). This prevents cross-account
    data mixing when multiple accounts have been synced.

    Includes user-defined names if set.
    """
    try:
        # Get the current account's bidder_id from new multi-account system
        current_bidder_id = None

        if service_account_id:
            service_account = await store.get_service_account(service_account_id)
            if service_account:
                bidder_row = await db_query_one(
                    "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
                    (service_account.id,)
                )
                if bidder_row:
                    current_bidder_id = bidder_row["bidder_id"]
        else:
            accounts = await store.get_service_accounts(active_only=True)
            if accounts:
                service_account = accounts[0]
                bidder_row = await db_query_one(
                    "SELECT bidder_id FROM buyer_seats WHERE service_account_id = ? LIMIT 1",
                    (service_account.id,)
                )
                if bidder_row:
                    current_bidder_id = bidder_row["bidder_id"]

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
