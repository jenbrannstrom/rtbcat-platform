"""Uploads Router - Upload tracking and import history endpoints.

Handles upload tracking summary and detailed import history for CSV imports.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from storage.database import db_query, DB_PATH

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


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/uploads/tracking", response_model=UploadTrackingResponse)
async def get_upload_tracking(
    days: int = Query(30, description="Number of days to retrieve", ge=1, le=365),
):
    """Get daily upload tracking summary."""
    if not DB_PATH.exists():
        return UploadTrackingResponse(
            daily_summaries=[],
            total_days=0,
            total_uploads=0,
            total_rows=0,
            days_with_anomalies=0,
        )

    try:
        rows = await db_query(
            """SELECT * FROM daily_upload_summary
            ORDER BY upload_date DESC
            LIMIT ?""",
            (days,),
        )

        daily_summaries = []
        total_uploads = 0
        total_rows = 0
        days_with_anomalies = 0

        for row in rows:
            file_size_mb = (row["total_file_size_bytes"] or 0) / (1024 * 1024)
            has_anomaly = bool(row["has_anomaly"]) if "has_anomaly" in row.keys() else False

            daily_summaries.append(
                DailyUploadSummaryResponse(
                    upload_date=row["upload_date"],
                    total_uploads=row["total_uploads"] or 0,
                    successful_uploads=row["successful_uploads"] or 0,
                    failed_uploads=row["failed_uploads"] or 0,
                    total_rows_written=row["total_rows_written"] or 0,
                    total_file_size_mb=round(file_size_mb, 2),
                    avg_rows_per_upload=round(row["avg_rows_per_upload"] or 0, 1),
                    min_rows=row["min_rows"] if "min_rows" in row.keys() else None,
                    max_rows=row["max_rows"] if "max_rows" in row.keys() else None,
                    has_anomaly=has_anomaly,
                    anomaly_reason=row["anomaly_reason"] if "anomaly_reason" in row.keys() else None,
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
    bidder_id: Optional[str] = Query(None, description="Filter by account (bidder_id)"),
):
    """Get import history records."""
    if not DB_PATH.exists():
        return []

    try:
        if bidder_id:
            rows = await db_query(
                """SELECT * FROM import_history
                WHERE bidder_id = ?
                ORDER BY imported_at DESC
                LIMIT ? OFFSET ?""",
                (bidder_id, limit, offset),
            )
        else:
            rows = await db_query(
                """SELECT * FROM import_history
                ORDER BY imported_at DESC
                LIMIT ? OFFSET ?""",
                (limit, offset),
            )

        results = []
        for row in rows:
            file_size_bytes = row["file_size_bytes"] if "file_size_bytes" in row.keys() else 0
            file_size_mb = (file_size_bytes or 0) / (1024 * 1024)

            billing_ids = None
            if "billing_ids_found" in row.keys() and row["billing_ids_found"]:
                try:
                    billing_ids = json.loads(row["billing_ids_found"])
                except json.JSONDecodeError:
                    billing_ids = None

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
                    bidder_id=row["bidder_id"] if "bidder_id" in row.keys() else None,
                    billing_ids_found=billing_ids,
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
    """Get daily uploads in a simple grid format."""
    if not DB_PATH.exists():
        return DailyUploadsGridResponse(days=[], expected_uploads_per_day=expected_per_day)

    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        imports = await db_query(
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
            date_display = check_date.strftime("%a %d %b")

            day_uploads = imports_by_date.get(date_iso, [])

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


# =============================================================================
# Multi-Account Upload Tracking Endpoints
# =============================================================================

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


@router.get("/uploads/accounts", response_model=AccountsUploadSummaryResponse)
async def get_accounts_upload_summary():
    """Get upload statistics grouped by account (bidder_id)."""
    if not DB_PATH.exists():
        return AccountsUploadSummaryResponse(
            accounts=[],
            total_accounts=0,
            unassigned_uploads=0,
        )

    try:
        rows = await db_query("""
            SELECT
                bidder_id,
                COUNT(*) as upload_count,
                SUM(rows_imported) as total_rows,
                MAX(imported_at) as latest_upload,
                GROUP_CONCAT(DISTINCT billing_ids_found) as all_billing_ids
            FROM import_history
            WHERE bidder_id IS NOT NULL
            GROUP BY bidder_id
            ORDER BY latest_upload DESC
        """)

        unassigned_row = await db_query("""
            SELECT COUNT(*) as cnt FROM import_history WHERE bidder_id IS NULL
        """)
        unassigned = unassigned_row[0]["cnt"] if unassigned_row else 0

        accounts = []
        for row in rows:
            billing_ids = set()
            if row["all_billing_ids"]:
                for json_str in row["all_billing_ids"].split(","):
                    if json_str:
                        try:
                            ids = json.loads(json_str)
                            if isinstance(ids, list):
                                billing_ids.update(ids)
                        except json.JSONDecodeError:
                            pass

            accounts.append(AccountUploadStats(
                bidder_id=row["bidder_id"],
                total_uploads=row["upload_count"] or 0,
                total_rows=row["total_rows"] or 0,
                latest_upload=row["latest_upload"],
                billing_ids=sorted(list(billing_ids)),
            ))

        return AccountsUploadSummaryResponse(
            accounts=accounts,
            total_accounts=len(accounts),
            unassigned_uploads=unassigned,
        )

    except Exception as e:
        logger.error(f"Failed to get accounts upload summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get accounts upload summary: {str(e)}")
