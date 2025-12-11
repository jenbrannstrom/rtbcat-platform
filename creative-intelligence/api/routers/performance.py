"""Performance metrics router for Cat-Scan API.

This module provides endpoints for importing and querying performance metrics:
- Bulk import of performance metrics
- CSV import from Authorized Buyers exports
- Streaming/batch import for large files
- Performance summaries per creative/campaign
"""

import json
import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from pydantic import BaseModel

from api.dependencies import get_store
from api.schemas.performance import (
    PerformanceMetricInput,
    PerformanceMetricResponse,
    PerformanceSummaryResponse,
    ImportPerformanceRequest,
    ImportPerformanceResponse,
    BatchPerformanceRequest,
    CreativePerformanceSummary,
    BatchPerformanceResponse,
    CSVImportResult,
    StreamingImportResult,
)
from qps.importer import validate_csv, import_csv
from storage import SQLiteStore, PerformanceMetric
from storage.database import db_execute, db_query_one, db_transaction_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["Performance"])


class BatchImportRequest(BaseModel):
    """Request for batch import (array of rows)."""
    rows: list[dict]
    batch_id: Optional[str] = None
    is_final: bool = False
    filename: Optional[str] = None
    file_size_bytes: Optional[int] = None


class FinalizeImportRequest(BaseModel):
    """Request to finalize a chunked import and record history."""
    batch_id: str
    filename: Optional[str] = None
    file_size_bytes: int = 0
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    total_spend_usd: float = 0
    total_impressions: int = 0
    total_reached: int = 0


@router.post("/import", response_model=ImportPerformanceResponse)
async def import_performance_metrics(
    request: ImportPerformanceRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Import performance metrics in bulk.

    Accepts an array of performance metrics and stores them using UPSERT semantics.
    If a record with the same (creative_id, metric_date, geography, device_type, placement)
    already exists, it will be updated.
    """
    try:
        metrics = [
            PerformanceMetric(
                creative_id=m.creative_id,
                metric_date=m.metric_date,
                impressions=m.impressions,
                clicks=m.clicks,
                spend_micros=m.spend_micros,
                campaign_id=m.campaign_id,
                geography=m.geography,
                device_type=m.device_type,
                placement=m.placement,
            )
            for m in request.metrics
        ]

        count = await store.save_performance_metrics(metrics)

        return ImportPerformanceResponse(
            status="completed",
            records_imported=count,
            message=f"Successfully imported {count} performance metrics.",
        )

    except Exception as e:
        logger.error(f"Performance import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Performance import failed: {str(e)}")


@router.get("/creative/{creative_id}", response_model=PerformanceSummaryResponse)
async def get_creative_performance(
    creative_id: str,
    days: int = Query(30, ge=1, le=365, description="Days to aggregate"),
    store: SQLiteStore = Depends(get_store),
):
    """Get aggregated performance summary for a creative."""
    try:
        summary = await store.get_creative_performance_summary(creative_id, days=days)

        return PerformanceSummaryResponse(
            total_impressions=summary.get("total_impressions"),
            total_clicks=summary.get("total_clicks"),
            total_spend_micros=summary.get("total_spend_micros"),
            avg_cpm_micros=summary.get("avg_cpm_micros"),
            avg_cpc_micros=summary.get("avg_cpc_micros"),
            ctr_percent=round(summary.get("ctr_percent"), 2) if summary.get("ctr_percent") else None,
            days_with_data=summary.get("days_with_data"),
            earliest_date=summary.get("earliest_date"),
            latest_date=summary.get("latest_date"),
        )

    except Exception as e:
        logger.error(f"Performance lookup failed for {creative_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Performance lookup failed: {str(e)}")


@router.get("/metrics", response_model=list[PerformanceMetricResponse])
async def list_performance_metrics(
    creative_id: Optional[str] = Query(None, description="Filter by creative ID"),
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    geography: Optional[str] = Query(None, description="Filter by country code"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    store: SQLiteStore = Depends(get_store),
):
    """List performance metrics with optional filtering."""
    try:
        metrics = await store.get_performance_metrics(
            creative_id=creative_id,
            campaign_id=campaign_id,
            start_date=start_date,
            end_date=end_date,
            geography=geography,
            device_type=device_type,
            limit=limit,
        )

        return [
            PerformanceMetricResponse(
                id=m.id,
                creative_id=m.creative_id,
                campaign_id=m.campaign_id,
                metric_date=m.metric_date,
                impressions=m.impressions,
                clicks=m.clicks,
                spend_micros=m.spend_micros,
                cpm_micros=m.cpm_micros,
                cpc_micros=m.cpc_micros,
                geography=m.geography,
                device_type=m.device_type,
                placement=m.placement,
            )
            for m in metrics
        ]

    except Exception as e:
        logger.error(f"Performance metrics query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Performance query failed: {str(e)}")


@router.post("/campaign/{campaign_id}/refresh-cache")
async def refresh_campaign_performance_cache(
    campaign_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Refresh cached performance aggregates for a campaign."""
    try:
        campaign = await store.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        await store.update_campaign_performance_cache(campaign_id)

        return {"status": "completed", "campaign_id": campaign_id, "message": "Cache refreshed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache refresh failed for {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Cache refresh failed: {str(e)}")


@router.delete("/cleanup")
async def cleanup_old_rtb_daily(
    days_to_keep: int = Query(90, ge=7, le=365, description="Days of data to retain"),
    store: SQLiteStore = Depends(get_store),
):
    """Delete performance data older than the retention period."""
    try:
        deleted = await store.clear_old_rtb_daily(days_to_keep=days_to_keep)

        return {
            "status": "completed",
            "records_deleted": deleted,
            "message": f"Deleted {deleted} records older than {days_to_keep} days.",
        }

    except Exception as e:
        logger.error(f"Performance cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/import-csv", response_model=CSVImportResult)
async def import_performance_csv(
    file: UploadFile = File(..., description="CSV file with performance data"),
):
    """Import performance data from Authorized Buyers CSV export.

    Uses the unified importer which:
    - Validates required columns (Day, Creative ID, Billing ID, Creative size, Reached queries, Impressions)
    - Stores raw data in rtb_daily table
    - Returns detailed import statistics
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        validation = validate_csv(tmp_path)

        if not validation.is_valid:
            return CSVImportResult(
                success=False,
                error=validation.error_message,
                fix_instructions=validation.get_fix_instructions(),
                columns_found=validation.columns_found,
                columns_mapped=validation.columns_mapped,
                required_missing=validation.required_missing,
            )

        result = import_csv(tmp_path)

        if not result.success:
            return CSVImportResult(
                success=False,
                error=result.error_message,
                errors=result.errors,
            )

        return CSVImportResult(
            success=True,
            batch_id=result.batch_id,
            rows_read=result.rows_read,
            rows_imported=result.rows_imported,
            rows_duplicate=result.rows_duplicate,
            rows_skipped=result.rows_skipped,
            date_range={
                "start": result.date_range_start,
                "end": result.date_range_end,
            },
            unique_creatives=result.unique_creatives,
            unique_sizes=len(result.unique_sizes),
            unique_countries=len(result.unique_countries),
            billing_ids=result.unique_billing_ids,
            total_reached=result.total_reached,
            total_impressions=result.total_impressions,
            total_spend_usd=result.total_spend_usd,
            columns_imported=result.columns_imported,
        )

    except Exception as e:
        logger.error(f"Import failed: {e}")
        return CSVImportResult(
            success=False,
            error=str(e),
        )

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/metrics/batch", response_model=BatchPerformanceResponse)
async def get_batch_performance(
    request: BatchPerformanceRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Get performance summaries for multiple creatives in a single request."""
    try:
        period_days = {
            "yesterday": 1,
            "7d": 7,
            "30d": 30,
            "all_time": 365,
        }
        days = period_days.get(request.period, 7)

        results: dict[str, CreativePerformanceSummary] = {}

        for creative_id in request.creative_ids:
            try:
                summary = await store.get_creative_performance_summary(
                    creative_id, days=days
                )

                has_data = summary.get("total_impressions", 0) > 0 or summary.get("total_spend_micros", 0) > 0

                results[creative_id] = CreativePerformanceSummary(
                    creative_id=creative_id,
                    total_impressions=summary.get("total_impressions") or 0,
                    total_clicks=summary.get("total_clicks") or 0,
                    total_spend_micros=summary.get("total_spend_micros") or 0,
                    avg_cpm_micros=summary.get("avg_cpm_micros"),
                    avg_cpc_micros=summary.get("avg_cpc_micros"),
                    ctr_percent=round(summary.get("ctr_percent"), 2) if summary.get("ctr_percent") else None,
                    days_with_data=summary.get("days_with_data") or 0,
                    has_data=has_data,
                )
            except Exception as e:
                logger.warning(f"Failed to get performance for {creative_id}: {e}")
                results[creative_id] = CreativePerformanceSummary(
                    creative_id=creative_id,
                    has_data=False,
                )

        return BatchPerformanceResponse(
            performance=results,
            period=request.period,
            count=len(results),
        )

    except Exception as e:
        logger.error(f"Batch performance lookup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch lookup failed: {str(e)}")


@router.post("/import/stream", response_model=StreamingImportResult)
async def import_performance_stream(
    request: Request,
):
    """Streaming import endpoint for large CSV files.

    Accepts NDJSON (newline-delimited JSON) stream of performance rows.
    """
    from storage.performance_repository import PerformanceRepository
    from storage.database import _get_connection

    BATCH_SIZE = 1000
    batch: list[dict] = []
    total_processed = 0
    total_imported = 0
    total_skipped = 0
    batch_count = 0
    errors: list[dict] = []
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    total_spend = 0.0

    try:
        # Use connection from database module
        db_conn = _get_connection()
        repo = PerformanceRepository(db_conn)

        body = b""
        async for chunk in request.stream():
            body += chunk

        lines = body.decode("utf-8").strip().split("\n")

        for line_num, line in enumerate(lines, start=1):
            if not line.strip():
                continue

            try:
                row = json.loads(line)

                date = row.get("date") or row.get("metric_date")
                if date:
                    if min_date is None or date < min_date:
                        min_date = date
                    if max_date is None or date > max_date:
                        max_date = date

                spend = row.get("spend", 0)
                if isinstance(spend, str):
                    spend = float(spend.replace("$", "").replace(",", ""))
                total_spend += float(spend)

                batch.append(row)
                total_processed += 1

                if len(batch) >= BATCH_SIZE:
                    try:
                        count = repo.insert_batch(batch)
                        total_imported += count
                        batch_count += 1
                    except Exception as e:
                        logger.warning(f"Batch insert failed: {e}")
                        total_skipped += len(batch)
                        errors.append({
                            "batch": batch_count + 1,
                            "error": str(e),
                            "rows_affected": len(batch),
                        })
                    batch = []

            except json.JSONDecodeError as e:
                total_skipped += 1
                if len(errors) < 50:
                    errors.append({
                        "line": line_num,
                        "error": f"Invalid JSON: {str(e)}",
                        "data": line[:100] if len(line) > 100 else line,
                    })
            except Exception as e:
                total_skipped += 1
                if len(errors) < 50:
                    errors.append({
                        "line": line_num,
                        "error": str(e),
                    })

        if batch:
            try:
                count = repo.insert_batch(batch)
                total_imported += count
                batch_count += 1
            except Exception as e:
                logger.warning(f"Final batch insert failed: {e}")
                total_skipped += len(batch)
                errors.append({
                    "batch": batch_count + 1,
                    "error": str(e),
                    "rows_affected": len(batch),
                })

        db_conn.commit()
        db_conn.close()

        return StreamingImportResult(
            status="completed",
            total_rows=total_processed,
            imported=total_imported,
            skipped=total_skipped,
            batches=batch_count,
            errors=[str(e) for e in errors[:50]],
            date_range={"start": min_date, "end": max_date} if min_date else None,
            total_spend=round(total_spend, 2) if total_spend > 0 else None,
        )

    except Exception as e:
        logger.error(f"Streaming import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming import failed: {str(e)}")


@router.post("/import/batch", response_model=StreamingImportResult)
async def import_performance_batch(
    request: BatchImportRequest,
):
    """Batch import endpoint for chunked uploads.

    Writes directly to the unified performance_metrics table.
    """
    try:
        min_date: Optional[str] = None
        max_date: Optional[str] = None
        total_spend = 0.0
        imported = 0
        skipped = 0

        def _do_batch_import(conn):
            nonlocal min_date, max_date, total_spend, imported, skipped
            cursor = conn.cursor()

            for row in request.rows:
                try:
                    date = row.get("date") or row.get("metric_date")
                    if not date:
                        skipped += 1
                        continue

                    if min_date is None or date < min_date:
                        min_date = date
                    if max_date is None or date > max_date:
                        max_date = date

                    spend = row.get("spend", 0)
                    if isinstance(spend, str):
                        spend = float(spend.replace("$", "").replace(",", ""))
                    spend_micros = int(float(spend) * 1_000_000)
                    total_spend += float(spend)

                    impressions = int(row.get("impressions", 0) or 0)
                    clicks = int(row.get("clicks", 0) or 0)
                    reached = int(row.get("reached_queries", 0) or 0)

                    geography = row.get("geography") or row.get("country") or None
                    device_type = row.get("device_type") or row.get("platform") or None
                    placement = row.get("placement") or None
                    campaign_id = row.get("campaign_id") or None
                    billing_id = row.get("billing_id") or None

                    cursor.execute("""
                        INSERT OR REPLACE INTO performance_metrics (
                            creative_id, campaign_id, metric_date,
                            impressions, clicks, spend_micros,
                            geography, device_type, placement, reached_queries,
                            billing_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row.get("creative_id"),
                        campaign_id,
                        date,
                        impressions,
                        clicks,
                        spend_micros,
                        geography,
                        device_type,
                        placement,
                        reached,
                        billing_id,
                    ))

                    if cursor.rowcount > 0:
                        imported += 1
                    else:
                        skipped += 1

                except Exception as row_err:
                    logger.warning(f"Row error: {row_err}")
                    skipped += 1
                    continue

            return imported

        await db_transaction_async(_do_batch_import)

        return StreamingImportResult(
            status="completed",
            total_rows=len(request.rows),
            imported=imported,
            skipped=skipped,
            batches=1,
            errors=[],
            date_range={"start": min_date, "end": max_date} if min_date else None,
            total_spend=round(total_spend, 2) if total_spend > 0 else None,
        )

    except Exception as e:
        logger.error(f"Batch import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch import failed: {str(e)}")


@router.post("/import/finalize")
async def finalize_import(request: FinalizeImportRequest):
    """Finalize a chunked import session and record in import_history."""
    try:
        def _do_finalize(conn):
            cursor = conn.cursor()

            # Record in import_history
            cursor.execute("""
                INSERT INTO import_history (
                    batch_id, filename, rows_read, rows_imported, rows_skipped, rows_duplicate,
                    date_range_start, date_range_end, total_reached, total_impressions,
                    total_spend_usd, status, file_size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.batch_id,
                request.filename,
                request.rows_read,
                request.rows_imported,
                request.rows_skipped,
                request.rows_duplicate,
                request.date_range_start,
                request.date_range_end,
                request.total_reached,
                request.total_impressions,
                request.total_spend_usd,
                "complete",
                request.file_size_bytes,
            ))

            # Update daily upload summary
            import_date = cursor.execute("SELECT date('now')").fetchone()[0]

            cursor.execute("""
                INSERT INTO daily_upload_summary (
                    upload_date, total_uploads, successful_uploads, failed_uploads,
                    total_rows_written, total_file_size_bytes, min_rows, max_rows, avg_rows_per_upload
                ) VALUES (?, 1, 1, 0, ?, ?, ?, ?, ?)
                ON CONFLICT(upload_date) DO UPDATE SET
                    total_uploads = total_uploads + 1,
                    successful_uploads = successful_uploads + 1,
                    total_rows_written = total_rows_written + excluded.total_rows_written,
                    total_file_size_bytes = total_file_size_bytes + excluded.total_file_size_bytes,
                    min_rows = MIN(min_rows, excluded.min_rows),
                    max_rows = MAX(max_rows, excluded.max_rows),
                    avg_rows_per_upload = (total_rows_written + excluded.total_rows_written) / (total_uploads + 1)
            """, (
                import_date,
                request.rows_imported,
                request.file_size_bytes,
                request.rows_imported,
                request.rows_imported,
                request.rows_imported,
            ))

        await db_transaction_async(_do_finalize)

        logger.info(f"Import finalized: batch_id={request.batch_id}, rows={request.rows_imported}")

        return {
            "status": "recorded",
            "batch_id": request.batch_id,
            "rows_imported": request.rows_imported,
        }

    except Exception as e:
        logger.error(f"Failed to finalize import: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to finalize import: {str(e)}")
