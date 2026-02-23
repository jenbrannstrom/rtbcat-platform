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
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile, File, Form
from pydantic import BaseModel

from api.dependencies import get_store, get_current_user, get_allowed_buyer_ids
from services.auth_service import User
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
from importers.unified_importer import unified_import, parse_bidder_id_from_filename
from storage import PerformanceMetric
from services.home_precompute import refresh_home_summaries
from services.performance_service import PerformanceService
from storage.postgres_repositories.uploads_repo import UploadsRepository
from services.precompute_validation import run_precompute_validation
from services.config_precompute import refresh_config_breakdowns
from services.rtb_precompute import refresh_rtb_summaries

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["Performance"])

UPLOAD_DIR = Path(tempfile.gettempdir()) / "catscan_uploads"
UPLOAD_TTL_SECONDS = 24 * 60 * 60


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
    date_gaps: Optional[list[str]] = None
    date_gap_warning: Optional[str] = None


class StreamStartRequest(BaseModel):
    filename: str
    file_size_bytes: int


class StreamStartResponse(BaseModel):
    upload_id: str
    message: str
    expires_in_seconds: int


class StreamChunkResponse(BaseModel):
    upload_id: str
    chunk_index: int
    bytes_received: int
    total_bytes: int


class StreamCompleteRequest(BaseModel):
    upload_id: str


def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _meta_path(upload_id: str) -> Path:
    return UPLOAD_DIR / f"{upload_id}.json"


def _data_path(upload_id: str) -> Path:
    return UPLOAD_DIR / f"{upload_id}.part"


def _load_meta(upload_id: str) -> dict:
    meta_file = _meta_path(upload_id)
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Upload not found")
    meta = json.loads(meta_file.read_text())
    created_at = int(meta.get("created_at", 0) or 0)
    if created_at and (int(time.time()) - created_at) > UPLOAD_TTL_SECONDS:
        raise HTTPException(status_code=410, detail="Upload expired")
    return meta


def _save_meta(upload_id: str, meta: dict) -> None:
    _meta_path(upload_id).write_text(json.dumps(meta))


def _safe_filename(filename: str) -> str:
    return "".join(ch if ch.isalnum() or ch in (".", "_", "-") else "_" for ch in filename)


def _build_import_response(result) -> CSVImportResult:
    fallback_error = result.error_message
    if not fallback_error and getattr(result, "errors", None):
        fallback_error = result.errors[0]

    if result.success:
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
            columns_imported=list(result.columns_mapped.keys()),
            columns_mapped=result.columns_mapped,
            columns_defaulted=result.columns_defaulted,
            date_gaps=result.date_gaps,
            date_gap_warning=result.date_gap_warning,
            report_type=result.report_type,
            target_table=result.target_table,
        )

    return CSVImportResult(
        success=False,
        error=fallback_error,
        errors=result.errors,
        columns_mapped=result.columns_mapped,
        columns_found=list(result.columns_mapped.values()) + result.columns_unmapped,
        date_gaps=getattr(result, "date_gaps", None),
        date_gap_warning=getattr(result, "date_gap_warning", None),
    )


@router.post("/import", response_model=ImportPerformanceResponse)
async def import_performance_metrics(
    request: ImportPerformanceRequest,
    store=Depends(get_store),
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
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get aggregated performance summary for a creative."""
    try:
        creative = await store.get_creative(creative_id)
        if not creative:
            raise HTTPException(status_code=404, detail="Creative not found")
        if creative.buyer_id:
            allowed = await get_allowed_buyer_ids(store=store, user=user)
            if allowed is not None and creative.buyer_id not in allowed:
                raise HTTPException(status_code=403, detail="You don't have access to this buyer account.")

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
    store=Depends(get_store),
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
    store=Depends(get_store),
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
    store=Depends(get_store),
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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with performance data"),
):
    """Import performance data from Authorized Buyers CSV export.

    Uses the unified importer which:
    - Validates required columns (Day, Creative ID, Pretargeting config/Billing ID, Creative size, Reached queries, Impressions)
    - Stores raw data in rtb_daily table
    - Returns detailed import statistics
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    tmp_path = None
    run_id = str(uuid.uuid4())
    uploads_repo = UploadsRepository()

    try:
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Extract buyer_id from filename as fallback
        buyer_id = parse_bidder_id_from_filename(file.filename or "")
        error_summary = None if buyer_id else "buyer_id_unresolved_from_upload"

        # Start ingestion run tracking
        await uploads_repo.start_ingestion_run(
            run_id=run_id,
            source_type="csv",
            buyer_id=buyer_id,
            bidder_id=buyer_id,
            filename=file.filename,
        )

        # Try flexible unified importer first - it auto-maps columns
        result = unified_import(tmp_path, source_filename=file.filename)
        file_size_bytes = os.path.getsize(tmp_path) if tmp_path and os.path.exists(tmp_path) else 0
        columns_found = []
        seen_columns = set()
        for col in list(result.columns_mapped.values()) + result.columns_unmapped:
            if col not in seen_columns:
                columns_found.append(col)
                seen_columns.add(col)

        # Finish ingestion run
        await uploads_repo.finish_ingestion_run(
            run_id=run_id,
            status="success" if result.success else "failed",
            row_count=result.rows_imported,
            error_summary=result.error_message if not result.success else error_summary,
            report_type=result.report_type or None,
        )

        perf_service = PerformanceService()
        await perf_service.record_import(
            batch_id=result.batch_id,
            filename=file.filename,
            rows_read=result.rows_read,
            rows_imported=result.rows_imported,
            rows_skipped=result.rows_skipped,
            rows_duplicate=result.rows_duplicate,
            date_range_start=result.date_range_start,
            date_range_end=result.date_range_end,
            columns_found=columns_found,
            status="complete" if result.success else "failed",
            error_message=result.error_message,
            file_size_bytes=file_size_bytes,
            date_gaps=result.date_gaps,
            date_gap_warning=result.date_gap_warning,
            buyer_id=buyer_id,
            bidder_id=buyer_id,
        )
        if result.success and result.date_range_start and result.date_range_end:
            background_tasks.add_task(
                refresh_home_summaries,
                start_date=result.date_range_start,
                end_date=result.date_range_end,
            )
            background_tasks.add_task(
                refresh_config_breakdowns,
                start_date=result.date_range_start,
                end_date=result.date_range_end,
            )
            background_tasks.add_task(
                refresh_rtb_summaries,
                result.date_range_start,
                result.date_range_end,
            )
            background_tasks.add_task(
                run_precompute_validation,
                result.date_range_start,
                result.date_range_end,
            )
        return _build_import_response(result)

    except Exception as e:
        logger.error(f"Import failed: {e}")
        # Mark ingestion run as failed
        try:
            await uploads_repo.finish_ingestion_run(
                run_id=run_id,
                status="failed",
                row_count=0,
                error_summary=str(e),
            )
        except Exception:
            logger.warning("Failed to record ingestion_run failure", exc_info=True)
        return CSVImportResult(
            success=False,
            error=str(e),
        )

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/import/stream/start", response_model=StreamStartResponse)
async def start_stream_import(request: StreamStartRequest):
    """Start a streamed CSV upload for large files."""
    if request.file_size_bytes <= 0:
        raise HTTPException(status_code=400, detail="Invalid file size")

    _ensure_upload_dir()
    upload_id = str(uuid.uuid4())
    meta = {
        "filename": request.filename,
        "file_size_bytes": request.file_size_bytes,
        "bytes_received": 0,
        "chunks_received": 0,
        "total_chunks": None,
        "created_at": int(time.time()),
    }
    _save_meta(upload_id, meta)
    _data_path(upload_id).write_bytes(b"")

    return StreamStartResponse(
        upload_id=upload_id,
        message="Upload started",
        expires_in_seconds=UPLOAD_TTL_SECONDS,
    )


@router.post("/import/stream/chunk", response_model=StreamChunkResponse)
async def upload_stream_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(..., ge=0),
    total_chunks: int = Form(..., ge=1),
    chunk: UploadFile = File(...),
):
    """Append a chunk to a streamed CSV upload."""
    _ensure_upload_dir()
    meta = _load_meta(upload_id)
    expected_index = meta.get("chunks_received", 0)
    if chunk_index != expected_index:
        raise HTTPException(status_code=409, detail="Unexpected chunk index")

    if meta.get("total_chunks") is None:
        meta["total_chunks"] = total_chunks
    elif meta["total_chunks"] != total_chunks:
        raise HTTPException(status_code=400, detail="Total chunks mismatch")

    data = await chunk.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty chunk")

    with _data_path(upload_id).open("ab") as f:
        f.write(data)

    prev_bytes = int(meta.get("bytes_received", 0))
    meta["chunks_received"] = expected_index + 1
    meta["bytes_received"] = prev_bytes + len(data)
    _save_meta(upload_id, meta)

    logger.debug(
        f"Chunk {chunk_index + 1}/{total_chunks} received for {upload_id}: "
        f"chunk_bytes={len(data)}, total_received={meta['bytes_received']}, "
        f"expected_total={meta['file_size_bytes']}"
    )

    return StreamChunkResponse(
        upload_id=upload_id,
        chunk_index=chunk_index,
        bytes_received=meta["bytes_received"],
        total_bytes=meta["file_size_bytes"],
    )


@router.post("/import/stream/complete", response_model=CSVImportResult)
async def complete_stream_import(
    request: StreamCompleteRequest,
    background_tasks: BackgroundTasks,
):
    """Finalize a streamed CSV upload and run the unified importer."""
    _ensure_upload_dir()
    meta = _load_meta(request.upload_id)
    total_chunks = meta.get("total_chunks")
    if total_chunks is None:
        raise HTTPException(status_code=400, detail="Upload not initialized")

    if meta.get("chunks_received") != total_chunks:
        raise HTTPException(status_code=400, detail="Upload incomplete")

    bytes_received = meta.get("bytes_received", 0)
    file_size_bytes = meta.get("file_size_bytes", 0)
    if bytes_received != file_size_bytes:
        logger.error(
            f"File size mismatch for upload {request.upload_id}: "
            f"received={bytes_received}, expected={file_size_bytes}, "
            f"diff={file_size_bytes - bytes_received}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"File size mismatch: received {bytes_received} bytes but expected {file_size_bytes} bytes"
        )

    data_path = _data_path(request.upload_id)
    if not data_path.exists():
        raise HTTPException(status_code=404, detail="Upload data missing")

    safe_name = _safe_filename(meta.get("filename", "upload.csv"))
    timestamp = int(time.time())

    # Prefer persistent imports dir, but fall back to upload temp dir if mount permissions
    # on ~/.catscan/imports are too restrictive in the current runtime.
    final_path: Path
    imports_dir = Path.home() / ".catscan" / "imports"
    preferred_path = imports_dir / f"{timestamp}_{safe_name}"
    fallback_path = UPLOAD_DIR / f"{timestamp}_{safe_name}"
    try:
        imports_dir.mkdir(parents=True, exist_ok=True)
        # Use shutil.move instead of rename to handle cross-filesystem moves
        # (e.g., /tmp -> mounted volume in Docker).
        shutil.move(str(data_path), str(preferred_path))
        final_path = preferred_path
    except (OSError, PermissionError) as move_error:
        logger.warning(
            f"Failed to move upload {request.upload_id} to {preferred_path}: {move_error}. "
            f"Falling back to {fallback_path}"
        )
        try:
            shutil.move(str(data_path), str(fallback_path))
            final_path = fallback_path
        except Exception as fallback_error:
            logger.error(
                f"Failed to place completed upload {request.upload_id} in both destinations: "
                f"primary_error={move_error}; fallback_error={fallback_error}"
            )
            raise HTTPException(
                status_code=500,
                detail="Import processing failed: unable to place uploaded file on server storage",
            )

    try:
        result = unified_import(str(final_path), source_filename=meta.get("filename"))
        columns_found = []
        seen_columns = set()
        for col in list(result.columns_mapped.values()) + result.columns_unmapped:
            if col not in seen_columns:
                columns_found.append(col)
                seen_columns.add(col)

        buyer_id = parse_bidder_id_from_filename(meta.get("filename") or "")
        perf_service = PerformanceService()
        await perf_service.record_import(
            batch_id=result.batch_id,
            filename=meta.get("filename"),
            rows_read=result.rows_read,
            rows_imported=result.rows_imported,
            rows_skipped=result.rows_skipped,
            rows_duplicate=result.rows_duplicate,
            date_range_start=result.date_range_start,
            date_range_end=result.date_range_end,
            columns_found=columns_found,
            status="complete" if result.success else "failed",
            error_message=result.error_message,
            file_size_bytes=file_size_bytes,
            date_gaps=result.date_gaps,
            date_gap_warning=result.date_gap_warning,
            buyer_id=buyer_id,
            bidder_id=buyer_id,
        )

        if result.success and result.date_range_start and result.date_range_end:
            background_tasks.add_task(
                refresh_home_summaries,
                start_date=result.date_range_start,
                end_date=result.date_range_end,
            )
            background_tasks.add_task(
                refresh_config_breakdowns,
                start_date=result.date_range_start,
                end_date=result.date_range_end,
            )
            background_tasks.add_task(
                refresh_rtb_summaries,
                result.date_range_start,
                result.date_range_end,
            )
        return _build_import_response(result)
    except Exception as e:
        logger.error(f"Import failed for {final_path}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Import processing failed: {str(e)}"
        )
    finally:
        try:
            _meta_path(request.upload_id).unlink()
        except FileNotFoundError:
            pass


@router.post("/metrics/batch", response_model=BatchPerformanceResponse)
async def get_batch_performance(
    request: BatchPerformanceRequest,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get performance summaries for multiple creatives in a single request."""
    try:
        period_days = {
            "yesterday": 1,
            "7d": 7,
            "14d": 14,
            "30d": 30,
            "all_time": 365,
        }
        days = period_days.get(request.period, 7)

        allowed = await get_allowed_buyer_ids(store=store, user=user)
        if allowed is not None:
            if not allowed:
                raise HTTPException(status_code=403, detail="No buyer accounts assigned.")
            # Validate all creatives belong to allowed buyers
            perf_service = PerformanceService()
            rows = await perf_service.get_creative_buyer_ids(request.creative_ids)
            for row in rows:
                buyer_id = row["buyer_id"]
                if buyer_id and buyer_id not in allowed:
                    raise HTTPException(status_code=403, detail="You don't have access to this buyer account.")

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
    total_processed = 0
    total_imported = 0
    total_skipped = 0
    errors: list[dict] = []
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    total_spend = 0.0
    perf_service = PerformanceService()

    try:
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
                if not date:
                    total_skipped += 1
                    continue

                if min_date is None or date < min_date:
                    min_date = date
                if max_date is None or date > max_date:
                    max_date = date

                spend_micros, spend_usd = perf_service.parse_spend(row.get("spend", 0))
                total_spend += spend_usd

                impressions = int(row.get("impressions", 0) or 0)
                clicks = int(row.get("clicks", 0) or 0)
                reached = int(row.get("reached_queries", 0) or 0)
                geography = row.get("geography") or row.get("country") or None
                device_type = row.get("device_type") or row.get("platform") or None
                placement = row.get("placement") or None
                campaign_id = row.get("campaign_id") or None

                await perf_service.upsert_metric(
                    creative_id=row.get("creative_id"),
                    metric_date=date,
                    impressions=impressions,
                    clicks=clicks,
                    spend_micros=spend_micros,
                    reached_queries=reached,
                    campaign_id=campaign_id,
                    geography=geography,
                    device_type=device_type,
                    placement=placement,
                )

                total_imported += 1
                total_processed += 1

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

        return StreamingImportResult(
            status="completed",
            total_rows=total_processed,
            imported=total_imported,
            skipped=total_skipped,
            batches=1,
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
    perf_service = PerformanceService()
    try:
        min_date: Optional[str] = None
        max_date: Optional[str] = None
        total_spend = 0.0
        imported = 0
        skipped = 0

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

                spend_micros, spend_usd = perf_service.parse_spend(row.get("spend", 0))
                total_spend += spend_usd

                impressions = int(row.get("impressions", 0) or 0)
                clicks = int(row.get("clicks", 0) or 0)
                reached = int(row.get("reached_queries", 0) or 0)

                geography = row.get("geography") or row.get("country") or None
                device_type = row.get("device_type") or row.get("platform") or None
                placement = row.get("placement") or None
                campaign_id = row.get("campaign_id") or None

                await perf_service.upsert_metric(
                    creative_id=row.get("creative_id"),
                    metric_date=date,
                    impressions=impressions,
                    clicks=clicks,
                    spend_micros=spend_micros,
                    reached_queries=reached,
                    campaign_id=campaign_id,
                    geography=geography,
                    device_type=device_type,
                    placement=placement,
                )

                imported += 1

            except Exception as row_err:
                logger.warning(f"Row error: {row_err}")
                skipped += 1
                continue

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
        perf_service = PerformanceService()
        await perf_service.finalize_import(
            batch_id=request.batch_id,
            filename=request.filename,
            rows_read=request.rows_read,
            rows_imported=request.rows_imported,
            rows_skipped=request.rows_skipped,
            rows_duplicate=request.rows_duplicate,
            date_range_start=request.date_range_start,
            date_range_end=request.date_range_end,
            total_reached=request.total_reached,
            total_impressions=request.total_impressions,
            total_spend_usd=request.total_spend_usd,
            file_size_bytes=request.file_size_bytes,
            date_gaps=request.date_gaps,
            date_gap_warning=request.date_gap_warning,
        )

        logger.info(f"Import finalized: batch_id={request.batch_id}, rows={request.rows_imported}")

        return {
            "status": "recorded",
            "batch_id": request.batch_id,
            "rows_imported": request.rows_imported,
        }

    except Exception as e:
        logger.error(f"Failed to finalize import: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to finalize import: {str(e)}")
