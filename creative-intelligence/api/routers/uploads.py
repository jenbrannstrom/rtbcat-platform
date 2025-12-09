"""Uploads Router - Upload tracking and import history endpoints.

Handles upload tracking summary and detailed import history for CSV imports.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from storage import SQLiteStore
from api.dependencies import get_store

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


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/uploads/tracking", response_model=UploadTrackingResponse)
async def get_upload_tracking(
    days: int = Query(30, description="Number of days to retrieve", ge=1, le=365),
    store: SQLiteStore = Depends(get_store),
):
    """Get daily upload tracking summary.

    Returns upload statistics for each day, including:
    - Date with success/failure indicator
    - File size in MB
    - Total rows written
    - Anomaly warnings for sudden drops/spikes in row counts
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """SELECT * FROM daily_upload_summary
                    ORDER BY upload_date DESC
                    LIMIT ?""",
                    (days,),
                ).fetchall(),
            )

        daily_summaries = []
        total_uploads = 0
        total_rows = 0
        days_with_anomalies = 0

        for row in rows:
            file_size_mb = (row["total_file_size_bytes"] or 0) / (1024 * 1024)
            has_anomaly = bool(row["has_anomaly"])

            daily_summaries.append(
                DailyUploadSummaryResponse(
                    upload_date=row["upload_date"],
                    total_uploads=row["total_uploads"] or 0,
                    successful_uploads=row["successful_uploads"] or 0,
                    failed_uploads=row["failed_uploads"] or 0,
                    total_rows_written=row["total_rows_written"] or 0,
                    total_file_size_mb=round(file_size_mb, 2),
                    avg_rows_per_upload=round(row["avg_rows_per_upload"] or 0, 1),
                    min_rows=row["min_rows"],
                    max_rows=row["max_rows"],
                    has_anomaly=has_anomaly,
                    anomaly_reason=row["anomaly_reason"],
                )
            )

            total_uploads += row["total_uploads"] or 0
            total_rows += row["total_rows_written"] or 0
            if has_anomaly:
                days_with_anomalies += 1

        return UploadTrackingResponse(
            daily_summaries=daily_summaries,
            total_days=len(daily_summaries),
            total_uploads=total_uploads,
            total_rows=total_rows,
            days_with_anomalies=days_with_anomalies,
        )

    except Exception as e:
        logger.error(f"Failed to get upload tracking: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get upload tracking: {str(e)}")


@router.get("/uploads/history", response_model=list[ImportHistoryResponse])
async def get_import_history(
    limit: int = Query(50, description="Maximum number of records to return", ge=1, le=500),
    offset: int = Query(0, description="Number of records to skip", ge=0),
    store: SQLiteStore = Depends(get_store),
):
    """Get import history records.

    Returns detailed history of all CSV imports with file sizes, row counts, and status.
    """
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """SELECT * FROM import_history
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall(),
            )

        results = []
        for row in rows:
            file_size_bytes = row["file_size_bytes"] if "file_size_bytes" in row.keys() else 0
            file_size_mb = (file_size_bytes or 0) / (1024 * 1024)

            results.append(
                ImportHistoryResponse(
                    batch_id=row["batch_id"],
                    filename=row["filename"],
                    imported_at=row["created_at"],
                    rows_read=row["rows_read"] or 0,
                    rows_imported=row["rows_imported"] or 0,
                    rows_skipped=row["rows_skipped"] or 0,
                    rows_duplicate=row["rows_duplicate"] or 0,
                    date_range_start=row["date_range_start"],
                    date_range_end=row["date_range_end"],
                    total_spend_usd=row["total_spend_usd"] or 0,
                    file_size_mb=round(file_size_mb, 2),
                    status=row["status"] or "unknown",
                    error_message=row["error_message"],
                )
            )

        return results

    except Exception as e:
        logger.error(f"Failed to get import history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get import history: {str(e)}")
