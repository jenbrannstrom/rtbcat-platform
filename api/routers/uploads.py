"""Uploads Router - Upload tracking and import history endpoints.

Handles upload tracking summary and detailed import history for CSV imports.
"""

import logging
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from api.dependencies import get_current_user, get_allowed_bidder_ids
from services.uploads_service import UploadsService
from services.auth_service import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Uploads"])


# =============================================================================
# Pydantic Models
# =============================================================================

class DailyUploadSummaryResponse(BaseModel):
    """Response model for daily upload summary."""
    upload_date: str
    total_uploads: int
    successful_uploads: int
    failed_uploads: int
    total_rows_written: int
    total_file_size_mb: float
    avg_rows_per_upload: float
    min_rows: Optional[int] = None
    max_rows: Optional[int] = None
    has_anomaly: bool = False
    anomaly_reason: Optional[str] = None


class UploadTrackingResponse(BaseModel):
    """Response model for upload tracking data."""
    daily_summaries: list[DailyUploadSummaryResponse]
    total_days: int
    total_uploads: int
    total_rows: int
    days_with_anomalies: int


class ImportHistoryResponse(BaseModel):
    """Response model for import history entry."""
    batch_id: str
    filename: Optional[str] = None
    imported_at: str
    rows_read: int
    rows_imported: int
    rows_skipped: int
    rows_duplicate: int
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    total_spend_usd: float
    file_size_mb: float
    status: str
    error_message: Optional[str] = None
    bidder_id: Optional[str] = None
    billing_ids_found: Optional[list[str]] = None
    columns_found: Optional[list[str]] = None
    columns_missing: Optional[list[str]] = None


class DailyFileUpload(BaseModel):
    """Single file upload for a day."""
    rows: int
    status: str
    error_message: Optional[str] = None


class DailyUploadRow(BaseModel):
    """One row in the daily uploads grid - shows all files for a day."""
    date: str
    date_iso: str
    uploads: list[DailyFileUpload]
    total_rows: int
    has_error: bool


class DailyUploadsGridResponse(BaseModel):
    """Response for the daily uploads grid view."""
    days: list[DailyUploadRow]
    expected_uploads_per_day: int


class AccountUploadStats(BaseModel):
    """Upload statistics for a single account."""
    bidder_id: str
    total_uploads: int
    total_rows: int
    latest_upload: Optional[str] = None
    latest_upload_status: Optional[str] = None
    billing_ids: list[str] = []


class AccountsUploadSummaryResponse(BaseModel):
    """Response for accounts upload summary."""
    accounts: list[AccountUploadStats]
    total_accounts: int
    unassigned_uploads: int


# =============================================================================
# Dependencies
# =============================================================================

def get_uploads_service() -> UploadsService:
    """Dependency to get UploadsService instance."""
    return UploadsService()


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/uploads/tracking", response_model=UploadTrackingResponse)
async def get_upload_tracking(
    days: int = Query(30, description="Number of days to retrieve", ge=1, le=365),
    user: User = Depends(get_current_user),
    service: UploadsService = Depends(get_uploads_service),
):
    """Get daily upload tracking summary."""
    if user.role != "admin":
        return UploadTrackingResponse(
            daily_summaries=[],
            total_days=0,
            total_uploads=0,
            total_rows=0,
            days_with_anomalies=0,
        )

    try:
        result = await service.get_tracking_summary(days)

        # Convert dataclasses to response models
        summaries = [
            DailyUploadSummaryResponse(**asdict(s))
            for s in result["daily_summaries"]
        ]

        return UploadTrackingResponse(
            daily_summaries=summaries,
            total_days=result["total_days"],
            total_uploads=result["total_uploads"],
            total_rows=result["total_rows"],
            days_with_anomalies=result["days_with_anomalies"],
        )

    except Exception as e:
        logger.error(f"Failed to get upload tracking: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get upload tracking: {str(e)}")


@router.get("/uploads/history", response_model=list[ImportHistoryResponse])
async def get_import_history(
    limit: int = Query(50, description="Maximum number of records to return", ge=1, le=500),
    offset: int = Query(0, description="Number of records to skip", ge=0),
    bidder_id: Optional[str] = Query(None, description="Filter by account (bidder_id)"),
    user: User = Depends(get_current_user),
    service: UploadsService = Depends(get_uploads_service),
):
    """Get import history records."""
    try:
        allowed_bidder_ids = await get_allowed_bidder_ids(user=user)
        if allowed_bidder_ids is not None:
            if not allowed_bidder_ids:
                return []
            if bidder_id and bidder_id not in allowed_bidder_ids:
                raise HTTPException(status_code=403, detail="You don't have access to this bidder account.")

        entries = await service.get_import_history(
            limit=limit,
            offset=offset,
            bidder_id=bidder_id,
            allowed_bidder_ids=allowed_bidder_ids,
        )

        return [ImportHistoryResponse(**asdict(e)) for e in entries]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get import history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get import history: {str(e)}")


@router.get("/uploads/daily-grid", response_model=DailyUploadsGridResponse)
async def get_daily_uploads_grid(
    days: int = Query(14, description="Number of days to show", ge=1, le=90),
    expected_per_day: int = Query(3, description="Expected uploads per day", ge=1, le=10),
    user: User = Depends(get_current_user),
    service: UploadsService = Depends(get_uploads_service),
):
    """Get daily uploads in a simple grid format."""
    try:
        allowed_bidder_ids = await get_allowed_bidder_ids(user=user)

        result = await service.get_daily_grid(
            days=days,
            expected_per_day=expected_per_day,
            allowed_bidder_ids=allowed_bidder_ids,
        )

        # Convert dataclasses to response models
        days_response = []
        for day in result["days"]:
            uploads = [
                DailyFileUpload(**asdict(u))
                for u in day.uploads
            ]
            days_response.append(DailyUploadRow(
                date=day.date,
                date_iso=day.date_iso,
                uploads=uploads,
                total_rows=day.total_rows,
                has_error=day.has_error,
            ))

        return DailyUploadsGridResponse(
            days=days_response,
            expected_uploads_per_day=result["expected_uploads_per_day"],
        )

    except Exception as e:
        logger.error(f"Failed to get daily uploads grid: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get daily uploads grid: {str(e)}")


@router.get("/uploads/accounts", response_model=AccountsUploadSummaryResponse)
async def get_accounts_upload_summary(
    user: User = Depends(get_current_user),
    service: UploadsService = Depends(get_uploads_service),
):
    """Get upload statistics grouped by account (bidder_id)."""
    try:
        allowed_bidder_ids = await get_allowed_bidder_ids(user=user)

        result = await service.get_accounts_summary(allowed_bidder_ids)

        # Convert dataclasses to response models
        accounts = [
            AccountUploadStats(
                bidder_id=a.bidder_id,
                total_uploads=a.total_uploads,
                total_rows=a.total_rows,
                latest_upload=a.latest_upload,
                billing_ids=a.billing_ids,
            )
            for a in result["accounts"]
        ]

        return AccountsUploadSummaryResponse(
            accounts=accounts,
            total_accounts=result["total_accounts"],
            unassigned_uploads=result["unassigned_uploads"],
        )

    except Exception as e:
        logger.error(f"Failed to get accounts upload summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get accounts upload summary: {str(e)}")
