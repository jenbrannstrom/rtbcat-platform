"""Retention Router - Data retention configuration and management endpoints.

Handles retention configuration, storage statistics, and running retention jobs.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from storage.database import db_query, db_execute, db_transaction_async, DB_PATH

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Retention"])


# =============================================================================
# Pydantic Models
# =============================================================================

class RetentionConfigRequest(BaseModel):
    """Request model for updating retention configuration."""
    raw_retention_days: int = Field(..., ge=7, le=365, description="Days to keep raw data")
    summary_retention_days: int = Field(..., ge=-1, le=3650, description="Days to keep summaries (-1 = forever)")
    auto_aggregate_after_days: int = Field(30, ge=1, le=90, description="Days before auto-aggregation")


class RetentionConfigResponse(BaseModel):
    """Response model for retention configuration."""
    raw_retention_days: int
    summary_retention_days: int
    auto_aggregate_after_days: int


class StorageStatsResponse(BaseModel):
    """Response model for storage statistics."""
    raw_rows: int
    raw_earliest_date: Optional[str]
    raw_latest_date: Optional[str]
    summary_rows: int
    summary_earliest_date: Optional[str]
    summary_latest_date: Optional[str]


class RetentionJobResponse(BaseModel):
    """Response model for retention job results."""
    aggregated_rows: int
    deleted_raw_rows: int
    deleted_summary_rows: int = 0


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/retention/config", response_model=RetentionConfigResponse)
async def get_retention_config():
    """Get current retention configuration."""
    from storage.retention_manager import RetentionManager

    if not DB_PATH.exists():
        # Return defaults if no database
        return RetentionConfigResponse(
            raw_retention_days=90,
            summary_retention_days=365,
            auto_aggregate_after_days=30,
        )

    try:
        def _get_config(conn):
            manager = RetentionManager(conn)
            return manager.get_retention_config()

        config = await db_transaction_async(_get_config)

        return RetentionConfigResponse(
            raw_retention_days=config.get('raw_retention_days', 90),
            summary_retention_days=config.get('summary_retention_days', 365),
            auto_aggregate_after_days=config.get('auto_aggregate_after_days', 30),
        )
    except Exception as e:
        logger.error(f"Failed to get retention config: {e}")
        # Return defaults on error
        return RetentionConfigResponse(
            raw_retention_days=90,
            summary_retention_days=365,
            auto_aggregate_after_days=30,
        )


@router.post("/retention/config", response_model=RetentionConfigResponse)
async def set_retention_config(request: RetentionConfigRequest):
    """Update retention configuration."""
    from storage.retention_manager import RetentionManager

    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        def _set_config(conn):
            # Ensure retention_config table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retention_config (
                    id INTEGER PRIMARY KEY,
                    seat_id INTEGER,
                    raw_retention_days INTEGER NOT NULL DEFAULT 90,
                    summary_retention_days INTEGER NOT NULL DEFAULT 365,
                    auto_aggregate_after_days INTEGER NOT NULL DEFAULT 30,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(seat_id)
                )
            """)

            manager = RetentionManager(conn)
            manager.set_retention_config(
                raw_retention_days=request.raw_retention_days,
                summary_retention_days=request.summary_retention_days,
                auto_aggregate_after_days=request.auto_aggregate_after_days,
            )

        await db_transaction_async(_set_config)

        return RetentionConfigResponse(
            raw_retention_days=request.raw_retention_days,
            summary_retention_days=request.summary_retention_days,
            auto_aggregate_after_days=request.auto_aggregate_after_days,
        )
    except Exception as e:
        logger.error(f"Failed to set retention config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save retention config: {str(e)}")


@router.get("/retention/stats", response_model=StorageStatsResponse)
async def get_storage_stats():
    """Get storage statistics for performance data."""
    from storage.retention_manager import RetentionManager

    if not DB_PATH.exists():
        return StorageStatsResponse(
            raw_rows=0,
            raw_earliest_date=None,
            raw_latest_date=None,
            summary_rows=0,
            summary_earliest_date=None,
            summary_latest_date=None,
        )

    try:
        def _get_stats(conn):
            # Ensure daily_creative_summary table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_creative_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seat_id INTEGER,
                    creative_id TEXT NOT NULL,
                    date DATE NOT NULL,
                    total_queries INTEGER DEFAULT 0,
                    total_impressions INTEGER DEFAULT 0,
                    total_clicks INTEGER DEFAULT 0,
                    total_spend REAL DEFAULT 0,
                    win_rate REAL,
                    ctr REAL,
                    cpm REAL,
                    unique_geos INTEGER DEFAULT 0,
                    unique_apps INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(seat_id, creative_id, date)
                )
            """)

            manager = RetentionManager(conn)
            return manager.get_storage_stats()

        stats = await db_transaction_async(_get_stats)

        return StorageStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        return StorageStatsResponse(
            raw_rows=0,
            raw_earliest_date=None,
            raw_latest_date=None,
            summary_rows=0,
            summary_earliest_date=None,
            summary_latest_date=None,
        )


@router.post("/retention/run", response_model=RetentionJobResponse)
async def run_retention_job():
    """Run the retention job to aggregate and clean up old data."""
    from storage.retention_manager import RetentionManager

    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        def _run_job(conn):
            # Ensure required tables exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retention_config (
                    id INTEGER PRIMARY KEY,
                    seat_id INTEGER,
                    raw_retention_days INTEGER NOT NULL DEFAULT 90,
                    summary_retention_days INTEGER NOT NULL DEFAULT 365,
                    auto_aggregate_after_days INTEGER NOT NULL DEFAULT 30,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(seat_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_creative_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seat_id INTEGER,
                    creative_id TEXT NOT NULL,
                    date DATE NOT NULL,
                    total_queries INTEGER DEFAULT 0,
                    total_impressions INTEGER DEFAULT 0,
                    total_clicks INTEGER DEFAULT 0,
                    total_spend REAL DEFAULT 0,
                    win_rate REAL,
                    ctr REAL,
                    cpm REAL,
                    unique_geos INTEGER DEFAULT 0,
                    unique_apps INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(seat_id, creative_id, date)
                )
            """)

            manager = RetentionManager(conn)
            return manager.run_retention_job()

        result = await db_transaction_async(_run_job)

        return RetentionJobResponse(**result)
    except Exception as e:
        logger.error(f"Failed to run retention job: {e}")
        raise HTTPException(status_code=500, detail=f"Retention job failed: {str(e)}")
