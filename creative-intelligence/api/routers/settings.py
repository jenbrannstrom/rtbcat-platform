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
from storage import SQLiteStore
from api.dependencies import get_store, get_config
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
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Sync RTB endpoints from Google Authorized Buyers API.

    Fetches all RTB endpoints for the configured bidder account and stores them
    in the rtb_endpoints table.
    """
    try:
        app_config = config.load()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Configuration not set. Use /config to configure."
        )

    if not app_config.authorized_buyers:
        raise HTTPException(
            status_code=400,
            detail="Authorized Buyers not configured. Upload credentials via /config/credentials."
        )

    creds_path = Path(app_config.authorized_buyers.service_account_path).expanduser()
    if not creds_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Service account credentials file not found. Upload via /config/credentials."
        )

    account_id = app_config.authorized_buyers.account_id

    try:
        client = EndpointsClient(
            credentials_path=str(creds_path),
            account_id=account_id,
        )
        endpoints = await client.list_endpoints()

        # Store endpoints in database
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            for ep in endpoints:
                await loop.run_in_executor(
                    None,
                    lambda ep=ep: conn.execute(
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
                    ),
                )
            await loop.run_in_executor(None, conn.commit)

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
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Get stored RTB endpoints with aggregated QPS data.

    Returns all RTB endpoints that have been synced from the Google API,
    along with total allocated QPS and current usage.
    """
    try:
        # Get credentials for bidder_id
        bidder_id = ""
        account_name = None
        try:
            app_config = config.load()
            if app_config and app_config.authorized_buyers:
                bidder_id = app_config.authorized_buyers.account_id
        except Exception:
            pass

        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT * FROM rtb_endpoints ORDER BY trading_location, endpoint_id"
                ).fetchall(),
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
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Sync pretargeting configs from Google Authorized Buyers API.

    Fetches all pretargeting configurations for the configured bidder account
    and stores them in the pretargeting_configs table.
    """
    try:
        app_config = config.load()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Configuration not set. Use /config to configure."
        )

    if not app_config.authorized_buyers:
        raise HTTPException(
            status_code=400,
            detail="Authorized Buyers not configured. Upload credentials via /config/credentials."
        )

    creds_path = Path(app_config.authorized_buyers.service_account_path).expanduser()
    if not creds_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Service account credentials file not found. Upload via /config/credentials."
        )

    account_id = app_config.authorized_buyers.account_id

    try:
        client = PretargetingClient(
            credentials_path=str(creds_path),
            account_id=account_id,
        )
        configs = await client.fetch_all_pretargeting_configs()

        # Store configs in database
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

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

                await loop.run_in_executor(
                    None,
                    lambda cfg=cfg, sizes=sizes, included_geos=included_geos, excluded_geos=excluded_geos: conn.execute(
                        """
                        INSERT OR REPLACE INTO pretargeting_configs
                        (bidder_id, config_id, billing_id, display_name, state,
                         included_formats, included_platforms, included_sizes,
                         included_geos, excluded_geos, raw_config, synced_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
                    ),
                )
            await loop.run_in_executor(None, conn.commit)

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
    store: SQLiteStore = Depends(get_store),
):
    """Get stored pretargeting configs.

    Returns all pretargeting configurations that have been synced from the Google API.
    Includes user-defined names if set.
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT * FROM pretargeting_configs ORDER BY billing_id"
                ).fetchall(),
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
    store: SQLiteStore = Depends(get_store),
):
    """Set a custom user-defined name for a pretargeting config.

    This name will be displayed in the UI alongside the billing_id,
    making it easier to identify configs.
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            # Get current value for history tracking
            current = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT user_name, config_id, bidder_id FROM pretargeting_configs WHERE billing_id = ?",
                    (billing_id,),
                ).fetchone(),
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
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "UPDATE pretargeting_configs SET user_name = ? WHERE billing_id = ?",
                    (body.user_name, billing_id),
                ),
            )

            # Record history if value changed
            if old_name != body.user_name:
                await loop.run_in_executor(
                    None,
                    lambda: conn.execute(
                        """INSERT INTO pretargeting_history
                        (config_id, bidder_id, change_type, field_changed, old_value, new_value, change_source)
                        VALUES (?, ?, 'update', 'user_name', ?, ?, 'user')""",
                        (config_id, bidder_id, old_name, body.user_name),
                    ),
                )

            await loop.run_in_executor(None, conn.commit)

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
    store: SQLiteStore = Depends(get_store),
):
    """Get pretargeting settings change history.

    Returns a log of all changes made to pretargeting configurations,
    including who made the change and when.
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

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

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(query, params).fetchall(),
            )

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
