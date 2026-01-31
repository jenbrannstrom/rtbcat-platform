"""Creatives Router - Creative management endpoints.

Phase 11.1: Decision Context Foundation
Includes thumbnail status, waste flags, and country data for each creative.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_store, get_current_user, resolve_buyer_id, require_buyer_access
from services.auth_service import User
from services.creative_performance_service import CreativePerformanceService
from services.creative_preview_service import CreativePreviewService
from services.creative_language_service import CreativeLanguageService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Creatives"])
preview_service = CreativePreviewService()
language_service = CreativeLanguageService()


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
    country_iso3: Optional[str] = None
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


async def _get_thumbnail_status_for_creatives(
    store: Any, creative_ids: list[str]
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
    creative_ids: list[str],
    thumbnail_statuses: dict[str, ThumbnailStatusResponse],
    days: int = 7,
) -> dict[str, WasteFlagsResponse]:
    """Compute waste flags for multiple creatives."""
    service = CreativePerformanceService()
    status_map = {
        cid: {"status": ts.status} for cid, ts in thumbnail_statuses.items()
    }
    flags = await service.get_waste_flags(creative_ids, status_map, days)
    return {
        cid: WasteFlagsResponse(
            broken_video=data["broken_video"],
            zero_engagement=data["zero_engagement"],
        )
        for cid, data in flags.items()
    }


async def _get_primary_countries_for_creatives(
    creative_ids: list[str],
    days: int = 7,
) -> dict[str, str]:
    """Get the primary country (by spend) for each creative."""
    service = CreativePerformanceService()
    return await service.get_primary_countries(creative_ids, days)


async def _get_country_breakdown_for_creative(
    creative_id: str,
    days: int = 7,
) -> list[dict]:
    """Get country breakdown with spend/impressions for a single creative."""
    service = CreativePerformanceService()
    return await service.get_country_breakdown(creative_id, days)


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
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """List creatives with optional filtering.

    Phase 11.1: Decision Context Foundation
    - By default, slim=True excludes large fields like vast_xml and html snippets
    - Set active_only=True to hide creatives with zero activity in the timeframe
    - Includes thumbnail_status and waste_flags for each creative
    """
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
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
        perf_service = CreativePerformanceService()
        active_ids = await perf_service.get_active_creative_ids(creative_ids, days)
        if active_ids:
            creatives = [c for c in creatives if c.id in active_ids][:limit]

    # Get thumbnail status, waste flags, and country data for all creatives
    creative_ids = [c.id for c in creatives]
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, creative_ids)
    waste_flags = await _get_waste_flags_for_creatives(creative_ids, thumbnail_statuses, days)
    country_data = await _get_primary_countries_for_creatives(creative_ids, days)

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
            **preview_service.build_preview(
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
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """List creatives with pagination metadata.

    Phase 11.4: Scale Readiness
    Returns paginated results with metadata for large accounts.
    """
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)

    # Get total count for pagination (use same backend as list_creatives)
    total = await store.get_creative_count(
        buyer_id=buyer_id,
        format=format,
    )

    # Fetch creatives
    from storage.serving_database import db_query
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
        perf_service = CreativePerformanceService()
        active_ids = await perf_service.get_active_creative_ids(creative_ids, days)
        if active_ids:
            creatives = [c for c in creatives if c.id in active_ids][:limit]

    # Get thumbnail status, waste flags, and country data
    creative_ids = [c.id for c in creatives]
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, creative_ids)
    waste_flags = await _get_waste_flags_for_creatives(creative_ids, thumbnail_statuses, days)
    country_data = await _get_primary_countries_for_creatives(creative_ids, days)

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
            **preview_service.build_preview(
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
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get creatives that were first seen within the specified time period.

    Returns creatives that appeared for the first time in imports during the specified period.
    This is useful for identifying new creatives added to the account.
    """
    try:
        from storage.serving_database import db_query, db_query_one
        period_end = datetime.now()
        period_start = period_end - timedelta(days=days)
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)

        # Build query with Postgres syntax
        query = """
            SELECT c.*,
                (SELECT SUM(spend_micros) FROM rtb_daily WHERE creative_id = c.id) as total_spend_micros,
                (SELECT SUM(impressions) FROM rtb_daily WHERE creative_id = c.id) as total_impressions
            FROM creatives c
            WHERE c.first_seen_at >= %s
            AND c.first_seen_at <= %s
        """
        params: list = [period_start.isoformat(), period_end.isoformat()]

        if format:
            query += " AND c.format = %s"
            params.append(format.upper())

        if buyer_id:
            query += " AND c.buyer_id = %s"
            params.append(buyer_id)

        query += " ORDER BY c.first_seen_at DESC LIMIT %s"
        params.append(limit)

        rows = await db_query(query, tuple(params))

        # Get total count
        count_query = """
            SELECT COUNT(*) as cnt FROM creatives c
            WHERE c.first_seen_at >= %s
            AND c.first_seen_at <= %s
        """
        count_params: list = [period_start.isoformat(), period_end.isoformat()]
        if format:
            count_query += " AND c.format = %s"
            count_params.append(format.upper())
        if buyer_id:
            count_query += " AND c.buyer_id = %s"
            count_params.append(buyer_id)

        count_row = await db_query_one(count_query, tuple(count_params))
        total_count = count_row["cnt"] if count_row else 0

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
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get a specific creative by ID.

    Includes thumbnail_status and waste_flags.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    # Get thumbnail status and waste flags
    thumbnail_statuses = await _get_thumbnail_status_for_creatives(store, [creative_id])
    waste_flags = await _get_waste_flags_for_creatives([creative_id], thumbnail_statuses, days)

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
        **preview_service.build_preview(
            creative,
            html_thumbnail_url=thumbnail_statuses.get(creative_id).thumbnail_url if thumbnail_statuses.get(creative_id) else None
        ),
    )


@router.delete("/creatives/{creative_id}")
async def delete_creative(
    creative_id: str,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Delete a creative by ID."""
    creative = await store.get_creative(creative_id)
    if creative and creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)
    deleted = await store.delete_creative(creative_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Creative not found")
    return {"status": "deleted", "id": creative_id}


@router.post("/creatives/cluster")
async def assign_cluster(
    assignment: ClusterAssignment,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Assign a creative to a cluster."""
    creative = await store.get_creative(assignment.creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)
    await store.update_creative_cluster(
        assignment.creative_id,
        assignment.cluster_id,
    )
    return {"status": "updated", "creative_id": assignment.creative_id}


@router.delete("/creatives/{creative_id}/campaign")
async def remove_from_campaign(
    creative_id: str,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Remove a creative from its campaign."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    await store.update_creative_campaign(creative_id, None)
    return {"status": "removed", "creative_id": creative_id}


@router.get("/creatives/{creative_id}/countries", response_model=CreativeCountryBreakdownResponse)
async def get_creative_countries(
    creative_id: str,
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
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
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    breakdown = await _get_country_breakdown_for_creative(creative_id, days)

    # Calculate total spend for percentage calculation
    total_spend = sum(c.get("spend_micros", 0) or 0 for c in breakdown)

    # Map country codes to names
    from utils.country_codes import get_country_name, get_country_alpha3

    countries = [
        CreativeCountryMetrics(
            country_code=c["country_code"],
            country_name=get_country_name(c["country_code"]),
            country_iso3=get_country_alpha3(c["country_code"]),
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
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Analyze a creative's content to detect its language.

    Uses Gemini API to detect language from HTML, VAST, or Native content.
    Set force=true to re-analyze even if previously analyzed.

    Requires GEMINI_API_KEY environment variable to be set.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    response = await language_service.analyze_language(
        creative=creative,
        store=store,
        force=force,
    )

    return LanguageDetectionResponse(**response)


@router.put("/creatives/{creative_id}/language", response_model=LanguageDetectionResponse)
async def update_creative_language(
    creative_id: str,
    update: ManualLanguageUpdate,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Manually update a creative's detected language.

    Use this endpoint when automated detection was incorrect
    and you want to manually specify the correct language.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    response = await language_service.update_manual_language(
        creative=creative,
        update=update,
        store=store,
    )

    return LanguageDetectionResponse(**response)


@router.get("/creatives/{creative_id}/geo-mismatch", response_model=GeoMismatchResponse)
async def get_creative_geo_mismatch(
    creative_id: str,
    days: int = Query(7, ge=1, le=90, description="Days to look back for serving data"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Check if a creative's language matches its serving countries.

    Returns an alert if the detected language doesn't match the countries
    where the creative is being served, indicating a potential localization issue.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    mismatch = await language_service.get_geo_mismatch(
        creative=creative,
        days=days,
    )

    if mismatch["alert"]:
        return GeoMismatchResponse(
            creative_id=creative_id,
            has_mismatch=mismatch["has_mismatch"],
            alert=GeoMismatchAlert(**mismatch["alert"]),
            serving_countries=mismatch["serving_countries"],
        )

    return GeoMismatchResponse(
        creative_id=creative_id,
        has_mismatch=mismatch["has_mismatch"],
        alert=None,
        serving_countries=mismatch["serving_countries"],
    )
