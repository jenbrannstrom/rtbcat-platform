"""Uploads Router - Upload tracking and import history endpoints.

Handles upload tracking summary and detailed import history for CSV imports.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Uploads"])

# Database path for QPS data (import history lives here)
QPS_DB_PATH = Path.home() / ".catscan" / "catscan.db"


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


class DailyFileUpload(BaseModel):
    """Single file upload for a day."""
    rows: int
    status: str  # 'success', 'error', or 'missing'
    error_message: Optional[str] = None


class DailyUploadRow(BaseModel):
    """One row in the daily uploads grid - shows all files for a day."""
    date: str  # e.g. "Mon 8 Dec"
    date_iso: str  # e.g. "2024-12-08"
    uploads: list[DailyFileUpload]  # List of file uploads for this day
    total_rows: int
    has_error: bool


class DailyUploadsGridResponse(BaseModel):
    """Response for the daily uploads grid view."""
    days: list[DailyUploadRow]
    expected_uploads_per_day: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/uploads/tracking", response_model=UploadTrackingResponse)
async def get_upload_tracking(
    days: int = Query(30, description="Number of days to retrieve", ge=1, le=365),
):
    """Get daily upload tracking summary.

    Returns upload statistics for each day, including:
    - Date with success/failure indicator
    - File size in MB
    - Total rows written
    - Anomaly warnings for sudden drops/spikes in row counts
    """
    if not QPS_DB_PATH.exists():
        return UploadTrackingResponse(
            daily_summaries=[],
            total_days=0,
            total_uploads=0,
            total_rows=0,
            days_with_anomalies=0,
        )

    try:
        conn = sqlite3.connect(str(QPS_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT * FROM daily_upload_summary
            ORDER BY upload_date DESC
            LIMIT ?""",
            (days,),
        )
        rows = cursor.fetchall()
        conn.close()

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
):
    """Get import history records.

    Returns detailed history of all CSV imports with file sizes, row counts, and status.
    """
    if not QPS_DB_PATH.exists():
        return []

    try:
        conn = sqlite3.connect(str(QPS_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT * FROM import_history
            ORDER BY imported_at DESC
            LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            file_size_bytes = row["file_size_bytes"] if "file_size_bytes" in row.keys() else 0
            file_size_mb = (file_size_bytes or 0) / (1024 * 1024)

            results.append(
                ImportHistoryResponse(
                    batch_id=row["batch_id"],
                    filename=row["filename"],
                    imported_at=row["imported_at"] or "",
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


@router.get("/uploads/daily-grid", response_model=DailyUploadsGridResponse)
async def get_daily_uploads_grid(
    days: int = Query(14, description="Number of days to show", ge=1, le=90),
    expected_per_day: int = Query(3, description="Expected uploads per day", ge=1, le=10),
):
    """Get daily uploads in a simple grid format.

    Shows each day with its uploads:
    - Mon 8 Dec: 200 rows | 15 rows | error
    - Tue 9 Dec: 180 rows | 200 rows | 1,007,000 rows
    """
    from datetime import datetime, timedelta

    if not QPS_DB_PATH.exists():
        return DailyUploadsGridResponse(days=[], expected_uploads_per_day=expected_per_day)

    try:
        conn = sqlite3.connect(str(QPS_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all imports for the last N days
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor.execute(
            """
            SELECT
                date(imported_at) as import_date,
                rows_imported,
                status,
                error_message,
                filename
            FROM import_history
            WHERE date(imported_at) >= ?
            ORDER BY imported_at ASC
            """,
            (start_date,),
        )
        imports = cursor.fetchall()
        conn.close()

        # Group imports by date
        imports_by_date: dict[str, list] = {}
        for row in imports:
            date_str = row["import_date"]
            if date_str not in imports_by_date:
                imports_by_date[date_str] = []
            imports_by_date[date_str].append({
                "rows": row["rows_imported"] or 0,
                "status": row["status"] or "unknown",
                "error_message": row["error_message"],
            })

        # Build response for each day in range
        result_days = []
        current = datetime.now().date()

        for i in range(days):
            check_date = current - timedelta(days=i)
            date_iso = check_date.strftime("%Y-%m-%d")
            date_display = check_date.strftime("%a %d %b")  # e.g. "Mon 08 Dec"

            day_uploads = imports_by_date.get(date_iso, [])

            # Build upload list
            uploads = []
            total_rows = 0
            has_error = False

            for upload in day_uploads:
                status = "success" if upload["status"] == "complete" else "error"
                if status == "error":
                    has_error = True
                uploads.append(DailyFileUpload(
                    rows=upload["rows"],
                    status=status,
                    error_message=upload["error_message"],
                ))
                total_rows += upload["rows"]

            # Mark missing uploads if less than expected
            while len(uploads) < expected_per_day:
                uploads.append(DailyFileUpload(rows=0, status="missing"))

            result_days.append(DailyUploadRow(
                date=date_display,
                date_iso=date_iso,
                uploads=uploads,
                total_rows=total_rows,
                has_error=has_error,
            ))

        return DailyUploadsGridResponse(
            days=result_days,
            expected_uploads_per_day=expected_per_day,
        )

    except Exception as e:
        logger.error(f"Failed to get daily uploads grid: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get daily uploads grid: {str(e)}")
