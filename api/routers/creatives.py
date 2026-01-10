"""Creatives Router - Creative management endpoints.

Phase 11.1: Decision Context Foundation
Includes thumbnail status, waste flags, and country data for each creative.
"""

import os
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from storage import SQLiteStore
from api.dependencies import get_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Creatives"])


# =============================================================================
# Pydantic Models
# =============================================================================

class VideoPreview(BaseModel):
    """Video creative preview data."""
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    vast_xml: Optional[str] = None
    duration: Optional[str] = None


class HtmlPreview(BaseModel):
    """HTML creative preview data."""
    snippet: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail_url: Optional[str] = None  # Phase 22: Extracted from HTML snippet


class ImagePreview(BaseModel):
    """Image data for native creatives."""
    url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class NativePreview(BaseModel):
    """Native creative preview data."""
    headline: Optional[str] = None
    body: Optional[str] = None
    call_to_action: Optional[str] = None
    click_link_url: Optional[str] = None
    image: Optional[ImagePreview] = None
    logo: Optional[ImagePreview] = None


class ThumbnailStatusResponse(BaseModel):
    """Response model for thumbnail generation status."""
    status: Optional[str] = None  # 'success', 'failed', or None if not processed
    error_reason: Optional[str] = None  # 'url_expired', 'no_url', 'timeout', 'network_error', 'invalid_format'
    has_thumbnail: bool = False  # True if thumbnail file exists
    thumbnail_url: Optional[str] = None  # Phase 22: URL for HTML-extracted thumbnails


class WasteFlagsResponse(BaseModel):
    """Response model for waste detection flags."""
    broken_video: bool = False  # thumbnail_status='failed' AND impressions > 0
    zero_engagement: bool = False  # impressions > 1000 AND clicks = 0


class CreativeResponse(BaseModel):
    """Response model for creative data."""
    id: str
    name: str
    format: str
    account_id: Optional[str] = None
    buyer_id: Optional[str] = None
    approval_status: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    final_url: Optional[str] = None
    display_url: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    advertiser_name: Optional[str] = None
    campaign_id: Optional[str] = None
    cluster_id: Optional[str] = None
    seat_name: Optional[str] = None
    # Phase 22: Country data for clustering
    country: Optional[str] = None  # Primary country by spend
    # Preview data based on format
    video: Optional[VideoPreview] = None
    html: Optional[HtmlPreview] = None
    native: Optional[NativePreview] = None
    # Phase 10.4: Thumbnail status and waste detection
    thumbnail_status: Optional[ThumbnailStatusResponse] = None
    waste_flags: Optional[WasteFlagsResponse] = None
    # Phase 29: App info and disapproval tracking
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    app_store: Optional[str] = None
    is_disapproved: bool = False
    disapproval_reasons: Optional[list] = None
    serving_restrictions: Optional[list] = None
    # Language detection (Creative geo display)
    detected_language: Optional[str] = None
    detected_language_code: Optional[str] = None
    language_confidence: Optional[float] = None
    language_source: Optional[str] = None
    language_analyzed_at: Optional[str] = None
    language_analysis_error: Optional[str] = None


class LanguageDetectionResponse(BaseModel):
    """Response model for language detection."""
    creative_id: str
    detected_language: Optional[str] = None
    detected_language_code: Optional[str] = None
    language_confidence: Optional[float] = None
    language_source: Optional[str] = None
    language_analyzed_at: Optional[str] = None
    language_analysis_error: Optional[str] = None
    success: bool = False


class GeoMismatchAlert(BaseModel):
    """Response model for geo-language mismatch alert."""
    severity: str  # "warning"
    language: str
    language_code: str
    mismatched_countries: list[str]
    expected_countries: list[str]
    message: str


class GeoMismatchResponse(BaseModel):
    """Response for geo-mismatch check."""
    creative_id: str
    has_mismatch: bool
    alert: Optional[GeoMismatchAlert] = None
    serving_countries: list[str] = []


class ManualLanguageUpdate(BaseModel):
    """Request model for manual language update."""
    detected_language: str = Field(..., min_length=1, description="Language name (e.g., 'German')")
    detected_language_code: str = Field(..., min_length=2, max_length=3, description="ISO 639-1 code (e.g., 'de')")


class ClusterAssignment(BaseModel):
    """Request model for cluster assignment."""
    creative_id: str
    cluster_id: str


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    timeframe_days: Optional[int] = None
    total: int
    returned: int
    limit: int
    offset: int
    has_more: bool


class PaginatedCreativesResponse(BaseModel):
    """Paginated response for creatives list."""
    data: list[CreativeResponse]
    meta: PaginationMeta


class NewlyUploadedCreativesResponse(BaseModel):
    """Response model for newly uploaded creatives."""
    creatives: list[dict]
    total_count: int
    period_start: str
    period_end: str


class CreativeCountryMetrics(BaseModel):
    """Country-level metrics for a creative."""
    country_code: str
    country_name: str  # Human-readable name
    spend_micros: int
    impressions: int
    clicks: int
    spend_percent: float  # % of total spend for this creative


class CreativeCountryBreakdownResponse(BaseModel):
    """Response for creative country breakdown."""
    creative_id: str
    countries: list[CreativeCountryMetrics]
    total_countries: int
    period_days: int


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_video_url_from_vast(vast_xml: str) -> str | None:
    """Extract video URL from VAST XML."""
    if not vast_xml:
        return None
    match = re.search(r'<MediaFile[^>]*>(?:<!\[CDATA\[)?(https?://[^\]<]+)', vast_xml)
    return match.group(1).strip() if match else None


def _extract_thumbnail_from_vast(vast_xml: str) -> str | None:
    """Extract thumbnail URL from VAST XML CompanionAds.

    Looks for StaticResource images in CompanionAds section.
    """
    if not vast_xml:
        return None

    # Look for StaticResource with image type in CompanionAds
    # Pattern: <StaticResource creativeType="image/..."><![CDATA[URL]]></StaticResource>
    patterns = [
        # StaticResource with CDATA
        r'<StaticResource[^>]*creativeType="image/[^"]*"[^>]*><!\[CDATA\[(https?://[^\]]+)\]\]></StaticResource>',
        # StaticResource without CDATA
        r'<StaticResource[^>]*creativeType="image/[^"]*"[^>]*>(https?://[^<]+)</StaticResource>',
        # Any image URL in CompanionAds section (fallback)
        r'<Companion[^>]*>.*?<StaticResource[^>]*><!\[CDATA\[(https?://[^\]]+\.(?:jpg|jpeg|png|gif))\]\]>',
    ]

    for pattern in patterns:
        match = re.search(pattern, vast_xml, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

    return None


def _extract_preview_data(creative, slim: bool = False, html_thumbnail_url: Optional[str] = None) -> dict:
    """Extract preview data from creative raw_data based on format.

    Args:
        creative: The creative object
        slim: If True, exclude large fields (vast_xml, html snippet) for list views
        html_thumbnail_url: Optional thumbnail URL for HTML creatives (from thumbnail_status)
    """
    raw_data = creative.raw_data or {}
    result = {"video": None, "html": None, "native": None}

    if creative.format == "VIDEO":
        video_data = raw_data.get("video")
        if video_data:
            vast_xml = video_data.get("vastXml")
            video_url = video_data.get("videoUrl")
            # Pre-extract video URL from VAST if not already present
            if not video_url and vast_xml:
                video_url = _extract_video_url_from_vast(vast_xml)
            # Check for local thumbnail first (generated by CLI), then VAST
            local_thumb_path = video_data.get("localThumbnailPath")
            if local_thumb_path and os.path.exists(local_thumb_path):
                # Serve via API endpoint
                thumbnail_url = f"/thumbnails/{creative.id}.jpg"
            else:
                # Fall back to extracting from VAST CompanionAds
                thumbnail_url = _extract_thumbnail_from_vast(vast_xml) if vast_xml else None
            result["video"] = VideoPreview(
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                vast_xml=None if slim else vast_xml,  # Exclude in slim mode
                duration=video_data.get("duration"),
            )

    elif creative.format == "HTML":
        html_data = raw_data.get("html")
        if html_data:
            result["html"] = HtmlPreview(
                snippet=None if slim else html_data.get("snippet"),  # Exclude in slim mode
                width=html_data.get("width"),
                height=html_data.get("height"),
                thumbnail_url=html_thumbnail_url,  # Phase 22: From thumbnail_status
            )

    elif creative.format == "NATIVE":
        native_data = raw_data.get("native")
        if native_data:
            image_data = native_data.get("image")
            logo_data = native_data.get("logo")
            result["native"] = NativePreview(
                headline=native_data.get("headline"),
                body=native_data.get("body"),
                call_to_action=native_data.get("callToAction"),
                click_link_url=native_data.get("clickLinkUrl"),
                image=ImagePreview(**image_data) if image_data else None,
                logo=ImagePreview(**logo_data) if logo_data else None,
            )

    return result


async def _get_thumbnail_status_for_creatives(
    store: SQLiteStore, creative_ids: list[str]
) -> dict[str, ThumbnailStatusResponse]:
    """Get thumbnail status for multiple creatives.

    Returns a dict mapping creative_id to ThumbnailStatusResponse.
    """
    if not creative_ids:
        return {}

    statuses = await store.get_thumbnail_statuses(creative_ids)
    thumbnails_dir = Path.home() / ".catscan" / "thumbnails"

    result = {}
    for cid in creative_ids:
        status_data = statuses.get(cid)
        has_thumbnail = (thumbnails_dir / f"{cid}.jpg").exists()

        if status_data:
            result[cid] = ThumbnailStatusResponse(
                status=status_data["status"],
                error_reason=status_data["error_reason"],
                has_thumbnail=has_thumbnail,
                thumbnail_url=status_data.get("thumbnail_url"),  # Phase 22: HTML thumbnails
            )
        else:
            result[cid] = ThumbnailStatusResponse(
                status=None,
                error_reason=None,
                has_thumbnail=has_thumbnail,
                thumbnail_url=None,
            )

    return result


async def _get_waste_flags_for_creatives(
    store: SQLiteStore,
    creative_ids: list[str],
    thumbnail_statuses: dict[str, ThumbnailStatusResponse],
    days: int = 7,
) -> dict[str, WasteFlagsResponse]:
    """Compute waste flags for multiple creatives.

    Args:
        store: Database store
        creative_ids: List of creative IDs
        thumbnail_statuses: Pre-fetched thumbnail status data
        days: Timeframe for performance data (default 7 days)

    Returns:
        Dict mapping creative_id to WasteFlagsResponse
    """
    if not creative_ids:
        return {}

    # Get performance data for all creatives in timeframe
    # We need to query the rtb_daily table for impressions/clicks
    perf_data = {}
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _get_perf():
                placeholders = ",".join("?" * len(creative_ids))
                cursor = conn.execute(
                    f"""
                    SELECT creative_id,
                           SUM(impressions) as total_impressions,
                           SUM(clicks) as total_clicks
                    FROM rtb_daily
                    WHERE creative_id IN ({placeholders})
                      AND metric_date >= date('now', '-{days} days')
                    GROUP BY creative_id
                    """,
                    creative_ids,
                )
                return {row["creative_id"]: {"impressions": row["total_impressions"], "clicks": row["total_clicks"]}
                        for row in cursor.fetchall()}

            perf_data = await loop.run_in_executor(None, _get_perf)
    except Exception as e:
        # rtb_daily table may not exist yet (no performance data imported)
        logger.debug(f"Could not fetch performance data: {e}")

    result = {}
    for cid in creative_ids:
        ts = thumbnail_statuses.get(cid)
        perf = perf_data.get(cid, {"impressions": 0, "clicks": 0})
        impressions = perf["impressions"] or 0
        clicks = perf["clicks"] or 0

        # broken_video: thumbnail failed AND has impressions (wasting money on broken video)
        broken_video = (
            ts is not None
            and ts.status == "failed"
            and impressions > 0
        )

        # zero_engagement: high impressions but no clicks (poor creative performance)
        zero_engagement = impressions > 1000 and clicks == 0

        result[cid] = WasteFlagsResponse(
            broken_video=broken_video,
            zero_engagement=zero_engagement,
        )

    return result


async def _get_primary_countries_for_creatives(
    store: SQLiteStore,
    creative_ids: list[str],
    days: int = 7,
) -> dict[str, str]:
    """Get the primary country (by spend) for each creative.

    Args:
        store: Database store
        creative_ids: List of creative IDs
        days: Timeframe for performance data (default 7 days)

    Returns:
        Dict mapping creative_id to country code
    """
    if not creative_ids:
        return {}

    result = {}
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _get_countries():
                placeholders = ",".join("?" * len(creative_ids))
                # Get the country with highest spend for each creative
                cursor = conn.execute(
                    f"""
                    WITH ranked AS (
                        SELECT creative_id, geography,
                               SUM(spend_micros) as total_spend,
                               ROW_NUMBER() OVER (
                                   PARTITION BY creative_id
                                   ORDER BY SUM(spend_micros) DESC
                               ) as rn
                        FROM performance_metrics
                        WHERE creative_id IN ({placeholders})
                          AND geography IS NOT NULL
                          AND metric_date >= date('now', '-{days} days')
                        GROUP BY creative_id, geography
                    )
                    SELECT creative_id, geography
                    FROM ranked
                    WHERE rn = 1
                    """,
                    creative_ids,
                )
                return {row["creative_id"]: row["geography"] for row in cursor.fetchall()}

            result = await loop.run_in_executor(None, _get_countries)
    except Exception as e:
        # performance_metrics table may not exist or have geography data
        logger.debug(f"Could not fetch country data: {e}")

    return result


async def _get_country_breakdown_for_creative(
    store: SQLiteStore,
    creative_id: str,
    days: int = 7,
) -> list[dict]:
    """Get country breakdown with spend/impressions for a single creative.

    Returns list of {country_code, spend_micros, impressions, clicks}
    sorted by spend descending.
    """
    result = []
    try:
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT
                        country as country_code,
                        SUM(spend_micros) as spend_micros,
                        SUM(impressions) as impressions,
                        SUM(clicks) as clicks
                    FROM rtb_daily
                    WHERE creative_id = ?
                      AND country IS NOT NULL
                      AND country != ''
                      AND metric_date >= date('now', ? || ' days')
                    GROUP BY country
                    ORDER BY spend_micros DESC
                    """,
                    (creative_id, f"-{days}"),
                )
                return [dict(row) for row in cursor.fetchall()]

            result = await loop.run_in_executor(None, _query)
    except Exception as e:
        logger.debug(f"Could not fetch country breakdown: {e}")

    return result


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/creatives", response_model=list[CreativeResponse])
async def list_creatives(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    format: Optional[str] = Query(None, description="Filter by creative format"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    slim: bool = Query(True, description="Exclude large fields (vast_xml, html snippets) for faster loading"),
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection (default 7 days)"),
    active_only: bool = Query(False, description="Only return creatives with activity (impressions/clicks/spend) in timeframe"),
    store: SQLiteStore = Depends(get_store),
):
    """List creatives with optional filtering.

    Phase 11.1: Decision Context Foundation
    - By default, slim=True excludes large fields like vast_xml and html snippets
    - Set active_only=True to hide creatives with zero activity in the timeframe
    - Includes thumbnail_status and waste_flags for each creative
    """
    creatives = await store.list_creatives(
        campaign_id=campaign_id,
        cluster_id=cluster_id,
        buyer_id=buyer_id,
        format=format,
        limit=limit if not active_only else limit * 3,  # Fetch more if filtering
        offset=offset,
    )

    # If active_only, filter to creatives with activity in timeframe
    if active_only and creatives:
        creative_ids = [c.id for c in creatives]
        try:
            async with store._connection() as conn:
                import asyncio
                loop = asyncio.get_event_loop()

                def _get_active_ids():
                    placeholders = ",".join("?" * len(creative_ids))
                    cursor = conn.execute(
                        f"""
                        SELECT DISTINCT creative_id
                        FROM rtb_daily
                        WHERE creative_id IN ({placeholders})
                          AND metric_date >= date('now', '-{days} days')
                          AND (impressions > 0 OR clicks > 0 OR spend_micros > 0)
                        """,
                        creative_ids,
                    )
                    return set(row["creative_id"] for row in cursor.fetchall())

                active_ids = await loop.run_in_executor(None, _get_active_ids)
                creatives = [c for c in creatives if c.id in active_ids][:limit]
        except Exception as e:
            # rtb_daily table may not exist - return all creatives
            logger.debug(f"Could not filter active creatives: {e}")

    # Get thumbnail status, waste flags, and country data for all creatives
    creative_ids = [c.id for c in creatives]
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, creative_ids)
    waste_flags = await _get_waste_flags_for_creatives(store, creative_ids, thumbnail_statuses, days)
    country_data = await _get_primary_countries_for_creatives(store, creative_ids, days)

    return [
        CreativeResponse(
            id=c.id,
            name=c.name,
            format=c.format,
            account_id=c.account_id,
            buyer_id=c.buyer_id,
            approval_status=c.approval_status,
            width=c.width,
            height=c.height,
            final_url=c.final_url,
            display_url=c.display_url,
            utm_source=c.utm_source,
            utm_medium=c.utm_medium,
            utm_campaign=c.utm_campaign,
            utm_content=c.utm_content,
            utm_term=c.utm_term,
            advertiser_name=c.advertiser_name,
            campaign_id=c.campaign_id,
            cluster_id=c.cluster_id,
            seat_name=c.seat_name,
            country=country_data.get(c.id),
            thumbnail_status=thumbnail_statuses.get(c.id),
            waste_flags=waste_flags.get(c.id),
            # Phase 29: App info and disapproval
            app_id=c.app_id,
            app_name=c.app_name,
            app_store=c.app_store,
            is_disapproved=c.approval_status == "DISAPPROVED",
            disapproval_reasons=c.disapproval_reasons,
            serving_restrictions=c.serving_restrictions,
            # Language detection
            detected_language=c.detected_language,
            detected_language_code=c.detected_language_code,
            language_confidence=c.language_confidence,
            language_source=c.language_source,
            language_analyzed_at=c.language_analyzed_at.isoformat() if c.language_analyzed_at else None,
            language_analysis_error=c.language_analysis_error,
            **_extract_preview_data(
                c,
                slim=slim,
                html_thumbnail_url=thumbnail_statuses.get(c.id).thumbnail_url if thumbnail_statuses.get(c.id) else None
            ),
        )
        for c in creatives
    ]


@router.get("/creatives/v2", response_model=PaginatedCreativesResponse)
async def list_creatives_paginated(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    format: Optional[str] = Query(None, description="Filter by creative format"),
    limit: int = Query(50, ge=1, le=200, description="Page size (max 200)"),
    offset: int = Query(0, ge=0, description="Results offset"),
    slim: bool = Query(True, description="Exclude large fields for faster loading"),
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection"),
    active_only: bool = Query(False, description="Only return creatives with activity in timeframe"),
    store: SQLiteStore = Depends(get_store),
):
    """List creatives with pagination metadata.

    Phase 11.4: Scale Readiness
    Returns paginated results with metadata for large accounts.
    """
    # Get total count for pagination
    async with store._connection() as conn:
        import asyncio
        loop = asyncio.get_event_loop()

        def _count():
            cursor = conn.execute("SELECT COUNT(*) FROM creatives")
            return cursor.fetchone()[0]

        total = await loop.run_in_executor(None, _count)

    # Fetch creatives
    creatives = await store.list_creatives(
        campaign_id=campaign_id,
        cluster_id=cluster_id,
        buyer_id=buyer_id,
        format=format,
        limit=limit if not active_only else limit * 3,
        offset=offset,
    )

    # Filter by activity if requested
    if active_only and creatives:
        creative_ids = [c.id for c in creatives]
        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            def _get_active_ids():
                placeholders = ",".join("?" * len(creative_ids))
                cursor = conn.execute(
                    f"""
                    SELECT DISTINCT creative_id
                    FROM rtb_daily
                    WHERE creative_id IN ({placeholders})
                      AND metric_date >= date('now', '-{days} days')
                      AND (impressions > 0 OR clicks > 0 OR spend_micros > 0)
                    """,
                    creative_ids,
                )
                return set(row["creative_id"] for row in cursor.fetchall())

            active_ids = await loop.run_in_executor(None, _get_active_ids)
            creatives = [c for c in creatives if c.id in active_ids][:limit]

    # Get thumbnail status, waste flags, and country data
    creative_ids = [c.id for c in creatives]
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, creative_ids)
    waste_flags = await _get_waste_flags_for_creatives(store, creative_ids, thumbnail_statuses, days)
    country_data = await _get_primary_countries_for_creatives(store, creative_ids, days)

    data = [
        CreativeResponse(
            id=c.id,
            name=c.name,
            format=c.format,
            account_id=c.account_id,
            buyer_id=c.buyer_id,
            approval_status=c.approval_status,
            width=c.width,
            height=c.height,
            final_url=c.final_url,
            display_url=c.display_url,
            utm_source=c.utm_source,
            utm_medium=c.utm_medium,
            utm_campaign=c.utm_campaign,
            utm_content=c.utm_content,
            utm_term=c.utm_term,
            advertiser_name=c.advertiser_name,
            campaign_id=c.campaign_id,
            cluster_id=c.cluster_id,
            seat_name=c.seat_name,
            country=country_data.get(c.id),
            thumbnail_status=thumbnail_statuses.get(c.id),
            waste_flags=waste_flags.get(c.id),
            # Phase 29: App info and disapproval
            app_id=c.app_id,
            app_name=c.app_name,
            app_store=c.app_store,
            is_disapproved=c.approval_status == "DISAPPROVED",
            disapproval_reasons=c.disapproval_reasons,
            serving_restrictions=c.serving_restrictions,
            # Language detection
            detected_language=c.detected_language,
            detected_language_code=c.detected_language_code,
            language_confidence=c.language_confidence,
            language_source=c.language_source,
            language_analyzed_at=c.language_analyzed_at.isoformat() if c.language_analyzed_at else None,
            language_analysis_error=c.language_analysis_error,
            **_extract_preview_data(
                c,
                slim=slim,
                html_thumbnail_url=thumbnail_statuses.get(c.id).thumbnail_url if thumbnail_statuses.get(c.id) else None
            ),
        )
        for c in creatives
    ]

    return PaginatedCreativesResponse(
        data=data,
        meta=PaginationMeta(
            timeframe_days=days,
            total=total,
            returned=len(data),
            limit=limit,
            offset=offset,
            has_more=offset + len(data) < total,
        ),
    )


@router.get("/creatives/newly-uploaded", response_model=NewlyUploadedCreativesResponse)
async def get_newly_uploaded_creatives(
    days: int = Query(7, description="Number of days to look back", ge=1, le=90),
    limit: int = Query(100, description="Maximum number of creatives to return", ge=1, le=1000),
    format: Optional[str] = Query(None, description="Filter by format (HTML, VIDEO, NATIVE)"),
    store: SQLiteStore = Depends(get_store),
):
    """Get creatives that were first seen within the specified time period.

    Returns creatives that appeared for the first time in imports during the specified period.
    This is useful for identifying new creatives added to the account.
    """
    try:
        period_end = datetime.now()
        period_start = period_end - timedelta(days=days)

        async with store._connection() as conn:
            import asyncio
            loop = asyncio.get_event_loop()

            # Build query
            query = """
                SELECT c.*,
                    (SELECT SUM(spend_micros) FROM rtb_daily WHERE creative_id = c.id) as total_spend_micros,
                    (SELECT SUM(impressions) FROM rtb_daily WHERE creative_id = c.id) as total_impressions
                FROM creatives c
                WHERE c.first_seen_at >= ?
                AND c.first_seen_at <= ?
            """
            params = [period_start.isoformat(), period_end.isoformat()]

            if format:
                query += " AND c.format = ?"
                params.append(format.upper())

            query += " ORDER BY c.first_seen_at DESC LIMIT ?"
            params.append(limit)

            rows = await loop.run_in_executor(
                None,
                lambda: conn.execute(query, params).fetchall(),
            )

            # Get total count
            count_query = """
                SELECT COUNT(*) FROM creatives c
                WHERE c.first_seen_at >= ?
                AND c.first_seen_at <= ?
            """
            count_params = [period_start.isoformat(), period_end.isoformat()]
            if format:
                count_query += " AND c.format = ?"
                count_params.append(format.upper())

            total_count = await loop.run_in_executor(
                None,
                lambda: conn.execute(count_query, count_params).fetchone()[0],
            )

        creatives = []
        for row in rows:
            creative = {
                "id": row["id"],
                "name": row["name"],
                "format": row["format"],
                "approval_status": row["approval_status"],
                "width": row["width"],
                "height": row["height"],
                "canonical_size": row["canonical_size"],
                "final_url": row["final_url"],
                "first_seen_at": row["first_seen_at"],
                "first_import_batch_id": row["first_import_batch_id"],
                "total_spend_usd": (row["total_spend_micros"] or 0) / 1_000_000,
                "total_impressions": row["total_impressions"] or 0,
            }
            creatives.append(creative)

        return NewlyUploadedCreativesResponse(
            creatives=creatives,
            total_count=total_count or 0,
            period_start=period_start.strftime("%Y-%m-%d"),
            period_end=period_end.strftime("%Y-%m-%d"),
        )

    except Exception as e:
        logger.error(f"Failed to get newly uploaded creatives: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get newly uploaded creatives: {str(e)}")


@router.get("/creatives/{creative_id}", response_model=CreativeResponse)
async def get_creative(
    creative_id: str,
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection (default 7 days)"),
    store: SQLiteStore = Depends(get_store),
):
    """Get a specific creative by ID.

    Includes thumbnail_status and waste_flags.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    # Get thumbnail status and waste flags
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, [creative_id])
    waste_flags = await _get_waste_flags_for_creatives(store, [creative_id], thumbnail_statuses, days)

    return CreativeResponse(
        id=creative.id,
        name=creative.name,
        format=creative.format,
        account_id=creative.account_id,
        buyer_id=creative.buyer_id,
        approval_status=creative.approval_status,
        width=creative.width,
        height=creative.height,
        final_url=creative.final_url,
        display_url=creative.display_url,
        utm_source=creative.utm_source,
        utm_medium=creative.utm_medium,
        utm_campaign=creative.utm_campaign,
        utm_content=creative.utm_content,
        utm_term=creative.utm_term,
        advertiser_name=creative.advertiser_name,
        campaign_id=creative.campaign_id,
        cluster_id=creative.cluster_id,
        seat_name=creative.seat_name,
        thumbnail_status=thumbnail_statuses.get(creative_id),
        waste_flags=waste_flags.get(creative_id),
        # Phase 29: App info and disapproval
        app_id=creative.app_id,
        app_name=creative.app_name,
        app_store=creative.app_store,
        is_disapproved=creative.approval_status == "DISAPPROVED",
        disapproval_reasons=creative.disapproval_reasons,
        serving_restrictions=creative.serving_restrictions,
        # Language detection
        detected_language=creative.detected_language,
        detected_language_code=creative.detected_language_code,
        language_confidence=creative.language_confidence,
        language_source=creative.language_source,
        language_analyzed_at=creative.language_analyzed_at.isoformat() if creative.language_analyzed_at else None,
        language_analysis_error=creative.language_analysis_error,
        **_extract_preview_data(
            creative,
            html_thumbnail_url=thumbnail_statuses.get(creative_id).thumbnail_url if thumbnail_statuses.get(creative_id) else None
        ),
    )


@router.delete("/creatives/{creative_id}")
async def delete_creative(
    creative_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Delete a creative by ID."""
    deleted = await store.delete_creative(creative_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Creative not found")
    return {"status": "deleted", "id": creative_id}


@router.post("/creatives/cluster")
async def assign_cluster(
    assignment: ClusterAssignment,
    store: SQLiteStore = Depends(get_store),
):
    """Assign a creative to a cluster."""
    await store.update_creative_cluster(
        assignment.creative_id,
        assignment.cluster_id,
    )
    return {"status": "updated", "creative_id": assignment.creative_id}


@router.delete("/creatives/{creative_id}/campaign")
async def remove_from_campaign(
    creative_id: str,
    store: SQLiteStore = Depends(get_store),
):
    """Remove a creative from its campaign."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    await store.update_creative_campaign(creative_id, None)
    return {"status": "removed", "creative_id": creative_id}


@router.get("/creatives/{creative_id}/countries", response_model=CreativeCountryBreakdownResponse)
async def get_creative_countries(
    creative_id: str,
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    store: SQLiteStore = Depends(get_store),
):
    """Get country breakdown for a specific creative.

    Returns all countries where this creative has served,
    with spend, impressions, and clicks per country.
    Useful for verifying localization configuration.
    """
    # Verify creative exists
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    breakdown = await _get_country_breakdown_for_creative(store, creative_id, days)

    # Calculate total spend for percentage calculation
    total_spend = sum(c.get("spend_micros", 0) or 0 for c in breakdown)

    # Map country codes to names
    from utils.country_codes import get_country_name

    countries = [
        CreativeCountryMetrics(
            country_code=c["country_code"],
            country_name=get_country_name(c["country_code"]),
            spend_micros=c.get("spend_micros", 0) or 0,
            impressions=c.get("impressions", 0) or 0,
            clicks=c.get("clicks", 0) or 0,
            spend_percent=round((c.get("spend_micros", 0) or 0) / total_spend * 100, 1) if total_spend > 0 else 0,
        )
        for c in breakdown
    ]

    return CreativeCountryBreakdownResponse(
        creative_id=creative_id,
        countries=countries,
        total_countries=len(countries),
        period_days=days,
    )


# =============================================================================
# Language Detection Endpoints
# =============================================================================

@router.post("/creatives/{creative_id}/analyze-language", response_model=LanguageDetectionResponse)
async def analyze_creative_language(
    creative_id: str,
    force: bool = Query(False, description="Force re-analysis even if already analyzed"),
    store: SQLiteStore = Depends(get_store),
):
    """Analyze a creative's content to detect its language.

    Uses Gemini API to detect language from HTML, VAST, or Native content.
    Set force=true to re-analyze even if previously analyzed.

    Requires GEMINI_API_KEY environment variable to be set.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    # Check if already analyzed (unless force=True)
    if not force and creative.language_analyzed_at:
        return LanguageDetectionResponse(
            creative_id=creative_id,
            detected_language=creative.detected_language,
            detected_language_code=creative.detected_language_code,
            language_confidence=creative.language_confidence,
            language_source=creative.language_source,
            language_analyzed_at=creative.language_analyzed_at.isoformat() if creative.language_analyzed_at else None,
            language_analysis_error=creative.language_analysis_error,
            success=creative.detected_language is not None,
        )

    # Import analyzer
    try:
        from api.analysis.language_analyzer import GeminiLanguageAnalyzer
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Language analyzer not available: {e}"
        )

    analyzer = GeminiLanguageAnalyzer(db_path=store.db_path)

    if not analyzer.is_configured:
        # Save error to database
        await store.creative_repository.update_language_detection(
            creative_id=creative_id,
            detected_language=None,
            detected_language_code=None,
            language_confidence=None,
            language_source="gemini",
            language_analysis_error="Gemini API key not configured",
        )
        raise HTTPException(
            status_code=503,
            detail="Gemini API key not configured. Set it in Settings > Connected Accounts."
        )

    # Run language detection
    result = await analyzer.analyze_creative(
        creative_id=creative_id,
        raw_data=creative.raw_data,
        creative_format=creative.format,
    )

    # Save results to database
    await store.creative_repository.update_language_detection(
        creative_id=creative_id,
        detected_language=result.language,
        detected_language_code=result.language_code,
        language_confidence=result.confidence,
        language_source=result.source,
        language_analysis_error=result.error,
    )

    return LanguageDetectionResponse(
        creative_id=creative_id,
        detected_language=result.language,
        detected_language_code=result.language_code,
        language_confidence=result.confidence,
        language_source=result.source,
        language_analyzed_at=datetime.now().isoformat(),
        language_analysis_error=result.error,
        success=result.success,
    )


@router.put("/creatives/{creative_id}/language", response_model=LanguageDetectionResponse)
async def update_creative_language(
    creative_id: str,
    update: ManualLanguageUpdate,
    store: SQLiteStore = Depends(get_store),
):
    """Manually update a creative's detected language.

    Use this endpoint when automated detection was incorrect
    and you want to manually specify the correct language.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    # Save manual update
    await store.creative_repository.update_language_detection(
        creative_id=creative_id,
        detected_language=update.detected_language,
        detected_language_code=update.detected_language_code.lower(),
        language_confidence=1.0,  # Manual updates have full confidence
        language_source="manual",
        language_analysis_error=None,
    )

    return LanguageDetectionResponse(
        creative_id=creative_id,
        detected_language=update.detected_language,
        detected_language_code=update.detected_language_code.lower(),
        language_confidence=1.0,
        language_source="manual",
        language_analyzed_at=datetime.now().isoformat(),
        language_analysis_error=None,
        success=True,
    )


@router.get("/creatives/{creative_id}/geo-mismatch", response_model=GeoMismatchResponse)
async def get_creative_geo_mismatch(
    creative_id: str,
    days: int = Query(7, ge=1, le=90, description="Days to look back for serving data"),
    store: SQLiteStore = Depends(get_store),
):
    """Check if a creative's language matches its serving countries.

    Returns an alert if the detected language doesn't match the countries
    where the creative is being served, indicating a potential localization issue.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    # If no language detected, no mismatch check possible
    if not creative.detected_language_code:
        return GeoMismatchResponse(
            creative_id=creative_id,
            has_mismatch=False,
            alert=None,
            serving_countries=[],
        )

    # Get serving countries for this creative
    country_breakdown = await _get_country_breakdown_for_creative(store, creative_id, days)

    if not country_breakdown:
        return GeoMismatchResponse(
            creative_id=creative_id,
            has_mismatch=False,
            alert=None,
            serving_countries=[],
        )

    serving_countries = [c["country_code"] for c in country_breakdown if c.get("country_code")]

    # Check for mismatch
    from utils.language_country_map import get_mismatch_alert

    alert_data = get_mismatch_alert(
        language_code=creative.detected_language_code,
        language_name=creative.detected_language or creative.detected_language_code,
        serving_countries=serving_countries,
    )

    if alert_data:
        return GeoMismatchResponse(
            creative_id=creative_id,
            has_mismatch=True,
            alert=GeoMismatchAlert(**alert_data),
            serving_countries=serving_countries,
        )

    return GeoMismatchResponse(
        creative_id=creative_id,
        has_mismatch=False,
        alert=None,
        serving_countries=serving_countries,
    )
