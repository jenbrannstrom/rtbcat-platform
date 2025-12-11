"""System and Thumbnails router for Cat-Scan Creative Intelligence.

This module provides system status and thumbnail management endpoints.
"""

import logging
import os
import shutil
import subprocess
import sys
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.dependencies import get_store, get_config
from storage import SQLiteStore
from storage.database import db_query, db_execute, DB_PATH
from config import ConfigManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


# =============================================================================
# Pydantic Models
# =============================================================================


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    configured: bool
    has_credentials: bool = False
    database_exists: bool = False


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    python_version: str
    node_available: bool
    node_version: Optional[str] = None
    ffmpeg_available: bool
    ffmpeg_version: Optional[str] = None
    database_size_mb: float
    thumbnails_count: int
    disk_space_gb: float
    creatives_count: int
    videos_count: int


class ThumbnailGenerateRequest(BaseModel):
    """Request model for generating thumbnail for a single creative."""
    creative_id: str = Field(..., description="The creative ID to generate thumbnail for")


class ThumbnailGenerateResponse(BaseModel):
    """Response model for single thumbnail generation."""
    creative_id: str
    status: str  # 'success', 'failed', 'skipped', 'no_video_url'
    error_reason: Optional[str] = None
    thumbnail_url: Optional[str] = None


class ThumbnailBatchRequest(BaseModel):
    """Request model for batch thumbnail generation."""
    seat_id: Optional[str] = Field(None, description="Generate for specific seat only")
    limit: int = Field(50, ge=1, le=500, description="Maximum thumbnails to generate")
    force: bool = Field(False, description="Retry previously failed thumbnails")


class ThumbnailBatchResponse(BaseModel):
    """Response model for batch thumbnail generation."""
    status: str  # 'started', 'completed'
    total_processed: int
    success_count: int
    failed_count: int
    skipped_count: int
    results: list[ThumbnailGenerateResponse]


class ThumbnailStatusSummary(BaseModel):
    """Summary of thumbnail generation status."""
    total_videos: int
    with_thumbnails: int
    pending: int
    failed: int
    coverage_percent: float
    ffmpeg_available: bool


class HTMLThumbnailRequest(BaseModel):
    """Request model for HTML thumbnail extraction."""
    limit: int = Field(100, ge=1, le=1000, description="Maximum creatives to process")
    force_retry: bool = Field(False, description="Retry previously failed extractions")


class HTMLThumbnailResponse(BaseModel):
    """Response model for HTML thumbnail extraction."""
    status: str
    processed: int
    success: int
    failed: int
    no_image_found: int
    message: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================


def _get_thumbnails_dir() -> Path:
    """Get the thumbnails directory, creating if needed."""
    thumb_dir = Path.home() / ".catscan" / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return thumb_dir


def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    if shutil.which("ffmpeg") is not None:
        return True
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return True
    return False


def _get_ffmpeg_path() -> str:
    """Get the ffmpeg executable path."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return "ffmpeg"


def _classify_ffmpeg_error(returncode: int, stderr: str, url: str) -> str:
    """Classify ffmpeg error into categories."""
    stderr_lower = stderr.lower() if stderr else ""

    if "403" in stderr or "forbidden" in stderr_lower:
        return "url_expired"
    if "404" in stderr or "not found" in stderr_lower:
        return "url_not_found"
    if "timed out" in stderr_lower or "timeout" in stderr_lower:
        return "timeout"
    if "protocol" in stderr_lower or "invalid" in stderr_lower:
        return "invalid_url"
    if "network" in stderr_lower or "connection" in stderr_lower:
        return "network_error"

    return "unknown"


def _generate_thumbnail_ffmpeg(video_url: str, output_path: Path, timeout: int = 15) -> dict:
    """Generate thumbnail from video URL using ffmpeg."""
    try:
        cmd = [
            _get_ffmpeg_path(),
            "-y",
            "-ss", "1",
            "-t", "2",
            "-rw_timeout", "5000000",
            "-i", video_url,
            "-vframes", "1",
            "-vf", "scale='min(480,iw)':'-1'",
            "-q:v", "2",
            str(output_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )

        if result.returncode == 0 and output_path.exists():
            return {'success': True, 'error_reason': None}
        else:
            error_reason = _classify_ffmpeg_error(result.returncode, result.stderr, video_url)
            return {'success': False, 'error_reason': error_reason}

    except subprocess.TimeoutExpired:
        return {'success': False, 'error_reason': 'timeout'}
    except Exception:
        return {'success': False, 'error_reason': 'unknown'}


def _extract_video_url_from_vast(vast_xml: str) -> str | None:
    """Extract video URL from VAST XML."""
    if not vast_xml:
        return None
    import re
    match = re.search(r'<MediaFile[^>]*>(?:<!\[CDATA\[)?(https?://[^\]<]+)', vast_xml)
    return match.group(1).strip() if match else None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check(
    config: ConfigManager = Depends(get_config),
    store: SQLiteStore = Depends(get_store),
):
    """Check API health status including credential and database state.

    For the new multi-account system, configured=True only when there are
    service accounts in the database. Legacy config.enc is ignored for
    the configured status since the UI now uses the multi-account system.
    """
    has_credentials = False
    configured = False

    # Check new multi-account system - this is the primary credential source
    try:
        service_accounts = await store.get_service_accounts(active_only=True)
        if service_accounts:
            configured = True
            has_credentials = True
    except Exception:
        pass

    # Note: We intentionally do NOT fall back to legacy config.is_configured()
    # because the UI now uses the multi-account system exclusively.
    # The legacy config.enc may exist but is not used for displaying
    # "Connected Accounts" in the Setup page.

    db_path = Path.home() / ".catscan" / "catscan.db"

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        configured=configured,
        has_credentials=has_credentials,
        database_exists=db_path.exists(),
    )


@router.get("/thumbnails/{creative_id}.jpg", tags=["Thumbnails"])
async def get_thumbnail(creative_id: str):
    """Serve locally-generated video thumbnail."""
    thumb_path = Path.home() / ".catscan" / "thumbnails" / f"{creative_id}.jpg"
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb_path, media_type="image/jpeg")


@router.get("/thumbnails/status", response_model=ThumbnailStatusSummary, tags=["Thumbnails"])
async def get_thumbnail_status(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store: SQLiteStore = Depends(get_store),
):
    """Get summary of thumbnail generation status.

    Optionally filter by buyer_id to see status for a specific account.
    """
    ffmpeg_available = _check_ffmpeg()

    if not DB_PATH.exists():
        return ThumbnailStatusSummary(
            total_videos=0,
            with_thumbnails=0,
            pending=0,
            failed=0,
            coverage_percent=0.0,
            ffmpeg_available=ffmpeg_available,
        )

    # Build WHERE clause with optional buyer_id filter
    where_clause = "WHERE c.format = 'VIDEO'"
    params = []
    if buyer_id:
        where_clause += " AND c.buyer_id = ?"
        params.append(buyer_id)

    count_rows = await db_query(
        f"SELECT COUNT(*) as cnt FROM creatives c {where_clause}",
        tuple(params)
    )
    total_videos = count_rows[0]["cnt"] if count_rows else 0

    status_rows = await db_query(f"""
        SELECT
            COALESCE(ts.status, 'pending') as status,
            COUNT(*) as count
        FROM creatives c
        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
        {where_clause}
        GROUP BY COALESCE(ts.status, 'pending')
    """, tuple(params))

    status_counts = {row['status']: row['count'] for row in status_rows}

    with_thumbnails = status_counts.get('success', 0)
    failed = status_counts.get('failed', 0)
    pending = total_videos - with_thumbnails - failed

    coverage = (with_thumbnails / total_videos * 100) if total_videos > 0 else 0.0

    return ThumbnailStatusSummary(
        total_videos=total_videos,
        with_thumbnails=with_thumbnails,
        pending=pending,
        failed=failed,
        coverage_percent=round(coverage, 1),
        ffmpeg_available=ffmpeg_available,
    )


@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get system status including installed tools and resource usage."""
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    node_available = shutil.which("node") is not None
    node_version = None
    if node_available:
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
            node_version = result.stdout.strip()
        except Exception:
            pass

    ffmpeg_available = _check_ffmpeg()
    ffmpeg_version = None
    if ffmpeg_available:
        try:
            result = subprocess.run([_get_ffmpeg_path(), '-version'], capture_output=True, text=True, timeout=5)
            first_line = result.stdout.split('\n')[0]
            parts = first_line.split(' ')
            ffmpeg_version = parts[2] if len(parts) > 2 else 'Unknown'
        except Exception:
            pass

    database_size_mb = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0

    thumbnails_dir = Path.home() / ".catscan" / "thumbnails"
    thumbnails_count = len(list(thumbnails_dir.glob("*.jpg"))) if thumbnails_dir.exists() else 0

    total, used, free = shutil.disk_usage(Path.home())
    disk_space_gb = free / (1024 ** 3)

    creatives_count = 0
    videos_count = 0
    if DB_PATH.exists():
        try:
            rows = await db_query("SELECT COUNT(*) as cnt FROM creatives")
            creatives_count = rows[0]["cnt"] if rows else 0
            video_rows = await db_query("SELECT COUNT(*) as cnt FROM creatives WHERE format = 'VIDEO'")
            videos_count = video_rows[0]["cnt"] if video_rows else 0
        except Exception:
            pass

    return SystemStatusResponse(
        python_version=python_version,
        node_available=node_available,
        node_version=node_version,
        ffmpeg_available=ffmpeg_available,
        ffmpeg_version=ffmpeg_version,
        database_size_mb=round(database_size_mb, 2),
        thumbnails_count=thumbnails_count,
        disk_space_gb=round(disk_space_gb, 1),
        creatives_count=creatives_count,
        videos_count=videos_count,
    )


@router.post("/thumbnails/generate", response_model=ThumbnailGenerateResponse, tags=["Thumbnails"])
async def generate_single_thumbnail(
    request: ThumbnailGenerateRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Generate thumbnail for a single video creative."""
    if not _check_ffmpeg():
        raise HTTPException(status_code=503, detail="ffmpeg not installed on server")

    thumb_dir = _get_thumbnails_dir()

    rows = await db_query("""
        SELECT id, format, raw_data
        FROM creatives
        WHERE id = ?
    """, (request.creative_id,))

    if not rows:
        raise HTTPException(status_code=404, detail="Creative not found")

    row = rows[0]
    if row['format'] != 'VIDEO':
        return ThumbnailGenerateResponse(
            creative_id=request.creative_id,
            status='skipped',
            error_reason='not_video',
        )

    raw_data = json.loads(row['raw_data']) if row['raw_data'] else {}
    video_data = raw_data.get('video', {})
    video_url = video_data.get('videoUrl')

    if not video_url and video_data.get('vastXml'):
        video_url = _extract_video_url_from_vast(video_data['vastXml'])

    if not video_url:
        await db_execute("""
            INSERT INTO thumbnail_status (creative_id, status, error_reason, attempted_at)
            VALUES (?, 'failed', 'no_url', CURRENT_TIMESTAMP)
            ON CONFLICT(creative_id) DO UPDATE SET
                status = 'failed',
                error_reason = 'no_url',
                attempted_at = CURRENT_TIMESTAMP
        """, (request.creative_id,))

        return ThumbnailGenerateResponse(
            creative_id=request.creative_id,
            status='failed',
            error_reason='no_video_url',
        )

    thumb_path = thumb_dir / f"{request.creative_id}.jpg"
    result = _generate_thumbnail_ffmpeg(video_url, thumb_path)

    if result['success']:
        video_data['localThumbnailPath'] = str(thumb_path)
        raw_data['video'] = video_data
        await db_execute(
            "UPDATE creatives SET raw_data = ? WHERE id = ?",
            (json.dumps(raw_data), request.creative_id)
        )

        await db_execute("""
            INSERT INTO thumbnail_status (creative_id, status, video_url, attempted_at)
            VALUES (?, 'success', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(creative_id) DO UPDATE SET
                status = 'success',
                error_reason = NULL,
                video_url = excluded.video_url,
                attempted_at = CURRENT_TIMESTAMP
        """, (request.creative_id, video_url))

        return ThumbnailGenerateResponse(
            creative_id=request.creative_id,
            status='success',
            thumbnail_url=f"/thumbnails/{request.creative_id}.jpg",
        )
    else:
        await db_execute("""
            INSERT INTO thumbnail_status (creative_id, status, error_reason, video_url, attempted_at)
            VALUES (?, 'failed', ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(creative_id) DO UPDATE SET
                status = 'failed',
                error_reason = excluded.error_reason,
                video_url = excluded.video_url,
                attempted_at = CURRENT_TIMESTAMP
        """, (request.creative_id, result['error_reason'], video_url))

        return ThumbnailGenerateResponse(
            creative_id=request.creative_id,
            status='failed',
            error_reason=result['error_reason'],
        )


@router.post("/thumbnails/generate-batch", response_model=ThumbnailBatchResponse, tags=["Thumbnails"])
async def generate_batch_thumbnails(
    request: ThumbnailBatchRequest,
    store: SQLiteStore = Depends(get_store),
):
    """Generate thumbnails for multiple video creatives.

    Processes videos that don't have thumbnails yet (or failed ones if force=True).
    """
    if not _check_ffmpeg():
        raise HTTPException(status_code=503, detail="ffmpeg not installed on server")

    thumb_dir = _get_thumbnails_dir()

    if request.force:
        query = """
            SELECT c.id, c.raw_data
            FROM creatives c
            LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
            WHERE c.format = 'VIDEO'
            AND (ts.status IS NULL OR ts.status = 'failed')
        """
    else:
        query = """
            SELECT c.id, c.raw_data
            FROM creatives c
            LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
            WHERE c.format = 'VIDEO'
            AND ts.status IS NULL
        """

    if request.seat_id:
        query += " AND c.buyer_id = ?"
        rows = await db_query(query + f" LIMIT {request.limit}", (request.seat_id,))
    else:
        rows = await db_query(query + f" LIMIT {request.limit}")

    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for row in rows:
        creative_id = row['id']
        raw_data = json.loads(row['raw_data']) if row['raw_data'] else {}
        video_data = raw_data.get('video', {})
        video_url = video_data.get('videoUrl')

        if not video_url and video_data.get('vastXml'):
            video_url = _extract_video_url_from_vast(video_data['vastXml'])

        if not video_url:
            await db_execute("""
                INSERT INTO thumbnail_status (creative_id, status, error_reason, attempted_at)
                VALUES (?, 'failed', 'no_url', CURRENT_TIMESTAMP)
                ON CONFLICT(creative_id) DO UPDATE SET
                    status = 'failed', error_reason = 'no_url', attempted_at = CURRENT_TIMESTAMP
            """, (creative_id,))

            results.append(ThumbnailGenerateResponse(
                creative_id=creative_id,
                status='failed',
                error_reason='no_video_url',
            ))
            failed_count += 1
            continue

        thumb_path = thumb_dir / f"{creative_id}.jpg"
        result = _generate_thumbnail_ffmpeg(video_url, thumb_path)

        if result['success']:
            video_data['localThumbnailPath'] = str(thumb_path)
            raw_data['video'] = video_data
            await db_execute(
                "UPDATE creatives SET raw_data = ? WHERE id = ?",
                (json.dumps(raw_data), creative_id)
            )

            await db_execute("""
                INSERT INTO thumbnail_status (creative_id, status, video_url, attempted_at)
                VALUES (?, 'success', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(creative_id) DO UPDATE SET
                    status = 'success', error_reason = NULL, video_url = excluded.video_url,
                    attempted_at = CURRENT_TIMESTAMP
            """, (creative_id, video_url))

            results.append(ThumbnailGenerateResponse(
                creative_id=creative_id,
                status='success',
                thumbnail_url=f"/thumbnails/{creative_id}.jpg",
            ))
            success_count += 1
        else:
            await db_execute("""
                INSERT INTO thumbnail_status (creative_id, status, error_reason, video_url, attempted_at)
                VALUES (?, 'failed', ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(creative_id) DO UPDATE SET
                    status = 'failed', error_reason = excluded.error_reason,
                    video_url = excluded.video_url, attempted_at = CURRENT_TIMESTAMP
            """, (creative_id, result['error_reason'], video_url))

            results.append(ThumbnailGenerateResponse(
                creative_id=creative_id,
                status='failed',
                error_reason=result['error_reason'],
            ))
            failed_count += 1

    return ThumbnailBatchResponse(
        status='completed',
        total_processed=len(rows),
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        results=results,
    )


@router.post("/thumbnails/extract-html", response_model=HTMLThumbnailResponse, tags=["Thumbnails"])
async def extract_html_thumbnails(
    request: HTMLThumbnailRequest = HTMLThumbnailRequest(),
    store: SQLiteStore = Depends(get_store),
):
    """Extract thumbnail URLs from HTML creatives.

    Parses HTML creative snippets to find embedded image URLs (from <img src> tags,
    JavaScript document.write, or background-image styles) and saves them to
    thumbnail_status for display in the dashboard.
    """
    result = await store.process_html_thumbnails(
        limit=request.limit,
        force_retry=request.force_retry
    )

    return HTMLThumbnailResponse(
        status="completed",
        processed=result.get("processed", 0),
        success=result.get("success", 0),
        failed=result.get("failed", 0),
        no_image_found=result.get("no_image_found", 0),
        message=result.get("message"),
    )


# =============================================================================
# Stats and Sizes endpoints
# =============================================================================


class StatsResponse(BaseModel):
    """Response model for database statistics."""
    creative_count: int
    campaign_count: int
    cluster_count: int
    formats: dict[str, int]
    db_path: str


class SizesResponse(BaseModel):
    """Response model for available creative sizes."""
    sizes: list[str]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(store: SQLiteStore = Depends(get_store)):
    """Get database statistics."""
    stats = await store.get_stats()
    return StatsResponse(**stats)


@router.get("/sizes", response_model=SizesResponse)
async def get_sizes(store: SQLiteStore = Depends(get_store)):
    """Get available creative sizes from the database."""
    sizes = await store.get_available_sizes()
    return SizesResponse(sizes=sizes)
