"""Creatives Router - Creative management endpoints.

Phase 11.1: Decision Context Foundation
Includes thumbnail status, waste flags, and country data for each creative.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_store, get_current_user, resolve_buyer_id, require_buyer_access
from services.auth_service import User
from services.creative_preview_service import CreativePreviewService
from services.creative_countries_service import CreativeCountriesService
from services.creatives_service import CreativesService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Creatives"])
preview_service = CreativePreviewService()
countries_service = CreativeCountriesService()
creatives_service = CreativesService()


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


def _convert_thumbnail_status(ts) -> ThumbnailStatusResponse:
    """Convert service ThumbnailStatus to response model."""
    return ThumbnailStatusResponse(
        status=ts.status,
        error_reason=ts.error_reason,
        has_thumbnail=ts.has_thumbnail,
        thumbnail_url=ts.thumbnail_url,
    )


def _convert_waste_flags(wf) -> WasteFlagsResponse:
    """Convert service WasteFlags to response model."""
    return WasteFlagsResponse(
        broken_video=wf.broken_video,
        zero_engagement=wf.zero_engagement,
    )


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
        creatives = await creatives_service.filter_active_creatives(creatives, days, limit)

    # Get thumbnail status, waste flags, and country data via service
    creative_ids = [c.id for c in creatives]
    ctx = await creatives_service.get_list_context(store, creative_ids, days)

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
            country=ctx.country_data.get(c.id),
            thumbnail_status=_convert_thumbnail_status(ctx.thumbnail_statuses[c.id]) if c.id in ctx.thumbnail_statuses else None,
            waste_flags=_convert_waste_flags(ctx.waste_flags[c.id]) if c.id in ctx.waste_flags else None,
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
            **creatives_service.build_preview(
                c,
                slim=slim,
                html_thumbnail_url=ctx.thumbnail_statuses[c.id].thumbnail_url if c.id in ctx.thumbnail_statuses else None
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

    # Get total count for pagination
    total = await store.get_creative_count(
        buyer_id=buyer_id,
        format=format,
    )

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
        creatives = await creatives_service.filter_active_creatives(creatives, days, limit)

    # Get thumbnail status, waste flags, and country data via service
    creative_ids = [c.id for c in creatives]
    ctx = await creatives_service.get_list_context(store, creative_ids, days)

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
            country=ctx.country_data.get(c.id),
            thumbnail_status=_convert_thumbnail_status(ctx.thumbnail_statuses[c.id]) if c.id in ctx.thumbnail_statuses else None,
            waste_flags=_convert_waste_flags(ctx.waste_flags[c.id]) if c.id in ctx.waste_flags else None,
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
            **creatives_service.build_preview(
                c,
                slim=slim,
                html_thumbnail_url=ctx.thumbnail_statuses[c.id].thumbnail_url if c.id in ctx.thumbnail_statuses else None
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

    # Get thumbnail status and waste flags via service
    ctx = await creatives_service.get_list_context(store, [creative_id], days)

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
        thumbnail_status=_convert_thumbnail_status(ctx.thumbnail_statuses[creative_id]) if creative_id in ctx.thumbnail_statuses else None,
        waste_flags=_convert_waste_flags(ctx.waste_flags[creative_id]) if creative_id in ctx.waste_flags else None,
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
        **creatives_service.build_preview(
            creative,
            html_thumbnail_url=ctx.thumbnail_statuses[creative_id].thumbnail_url if creative_id in ctx.thumbnail_statuses else None
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

    payload = await countries_service.build_country_metrics(creative_id, days)
    return CreativeCountryBreakdownResponse(**payload)
