"""Retention Router - Data retention configuration and management endpoints.

Handles retention configuration, storage statistics, and running retention jobs.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from api.dependencies import require_admin
from services.auth_service import User
from services.retention_service import RetentionService

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
    conversion_event_rows: int = 0
    conversion_event_earliest_ts: Optional[str] = None
    conversion_event_latest_ts: Optional[str] = None
    conversion_failure_rows: int = 0
    conversion_failure_earliest_ts: Optional[str] = None
    conversion_failure_latest_ts: Optional[str] = None
    conversion_join_rows: int = 0
    conversion_join_earliest_ts: Optional[str] = None
    conversion_join_latest_ts: Optional[str] = None
    conversion_raw_event_rows: int = 0
    conversion_raw_event_earliest_ts: Optional[str] = None
    conversion_raw_event_latest_ts: Optional[str] = None


class RetentionJobResponse(BaseModel):
    """Response model for retention job results."""
    aggregated_rows: int
    deleted_raw_rows: int
    deleted_summary_rows: int = 0
    deleted_conversion_event_rows: int = 0
    deleted_conversion_failure_rows: int = 0
    deleted_conversion_join_rows: int = 0
    deleted_conversion_raw_event_rows: int = 0


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/retention/config", response_model=RetentionConfigResponse)
async def get_retention_config(
):
    """Get current retention configuration."""
    try:
        service = RetentionService()
        config = await service.get_config()

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
async def set_retention_config(
    request: RetentionConfigRequest,
    _user: User = Depends(require_admin),
):
    """Update retention configuration."""
    try:
        service = RetentionService()
        await service.set_config(
            raw_retention_days=request.raw_retention_days,
            summary_retention_days=request.summary_retention_days,
            auto_aggregate_after_days=request.auto_aggregate_after_days,
        )

        return RetentionConfigResponse(
            raw_retention_days=request.raw_retention_days,
            summary_retention_days=request.summary_retention_days,
            auto_aggregate_after_days=request.auto_aggregate_after_days,
        )
    except Exception as e:
        logger.error(f"Failed to set retention config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save retention config: {str(e)}")


@router.get("/retention/stats", response_model=StorageStatsResponse)
async def get_storage_stats(
):
    """Get storage statistics for performance data."""
    try:
        service = RetentionService()
        stats = await service.get_storage_stats()
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
            conversion_event_rows=0,
            conversion_event_earliest_ts=None,
            conversion_event_latest_ts=None,
            conversion_failure_rows=0,
            conversion_failure_earliest_ts=None,
            conversion_failure_latest_ts=None,
            conversion_join_rows=0,
            conversion_join_earliest_ts=None,
            conversion_join_latest_ts=None,
            conversion_raw_event_rows=0,
            conversion_raw_event_earliest_ts=None,
            conversion_raw_event_latest_ts=None,
        )


@router.post("/retention/run", response_model=RetentionJobResponse)
async def run_retention_job(
    _user: User = Depends(require_admin),
):
    """Run the retention job to aggregate and clean up old data."""
    try:
        service = RetentionService()
        result = await service.run_retention_job()
        return RetentionJobResponse(**result)
    except Exception as e:
        logger.error(f"Failed to run retention job: {e}")
        raise HTTPException(status_code=500, detail=f"Retention job failed: {str(e)}")
