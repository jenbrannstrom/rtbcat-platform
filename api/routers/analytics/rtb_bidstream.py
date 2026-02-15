"""RTB Funnel & Drilldowns Router.

Handles RTB funnel analysis, publisher/geo breakdowns, config performance,
creative win performance, and app drill-down endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from api.dependencies import get_store, get_current_user, resolve_buyer_id
from services.auth_service import User
from services.rtb_bidstream_service import RtbBidstreamService
from analytics.rtb_bidstream_analyzer import RTBFunnelAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Analytics"])

# Singleton service instance
_service: Optional[RtbBidstreamService] = None


def get_rtb_bidstream_service() -> RtbBidstreamService:
    """Get or create the RTB bidstream service singleton."""
    global _service
    if _service is None:
        _service = RtbBidstreamService()
    return _service


@router.get("/analytics/rtb-funnel", tags=["RTB Analytics"])
async def get_rtb_bidstream(
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Get RTB funnel analysis from database.

    Provides:
    - Funnel summary: Reached Queries -> Impressions
    - Publisher performance with win rates
    - Geographic breakdown

    Args:
        days: Number of days to analyze
        buyer_id: Optional buyer seat ID to filter results
    """
    try:
        resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        svc = get_rtb_bidstream_service()
        return await svc.get_rtb_funnel(days, resolved_buyer_id)
    except Exception as e:
        logger.error(f"Failed to get RTB funnel data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/publishers", tags=["RTB Analytics"])
async def get_rtb_publishers(
    limit: int = Query(30, ge=1, le=100),
    days: int = Query(7, ge=1, le=90)
):
    """
    Get publisher performance breakdown from database.

    Shows win rates and pretargeting filter rates by publisher.
    """
    try:
        svc = get_rtb_bidstream_service()
        return await svc.get_publishers(days, limit)
    except Exception as e:
        logger.error(f"Failed to get publisher performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/geos", tags=["RTB Analytics"])
async def get_rtb_geos(
    limit: int = Query(30, ge=1, le=100),
    days: int = Query(7, ge=1, le=90)
):
    """
    Get geographic performance breakdown from database.

    Shows win rates and auction participation by country.
    """
    try:
        svc = get_rtb_bidstream_service()
        return await svc.get_geos(days, limit)
    except Exception as e:
        logger.error(f"Failed to get geo performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs", tags=["RTB Analytics"])
async def get_config_performance(
    days: int = Query(7, ge=1, le=30),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Get performance breakdown by pretargeting config (billing_id).

    Reads from precomputed config breakdown tables and aggregates by
    pretargeting config ID (`billing_id`) to show:
    - Reached queries and impressions per config
    - Size-level performance within each config
    - Win rate vs waste percentages
    - Settings derived from the data (format, geos, platforms)

    Only returns data for `billing_id` values that belong to the specified buyer seat
    (or current account if not specified).

    Args:
        days: Number of days to analyze (default 7, max 30)
        buyer_id: Optional buyer seat ID to filter results
    """
    try:
        resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        svc = get_rtb_bidstream_service()
        return await svc.get_config_performance(days, resolved_buyer_id)
    except Exception as e:
        logger.error(f"Failed to get config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs/{billing_id}/breakdown", tags=["RTB Analytics"])
async def get_config_breakdown(
    billing_id: str,
    by: str = Query("size", pattern="^(size|geo|publisher|creative)$"),
    days: int = Query(7, ge=1, le=30),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Get detailed breakdown for a specific pretargeting config.

    Breakdown types:
    - size: By creative size (300x250, 320x50, etc.)
    - geo: By country/region
    - publisher: By app/publisher
    - creative: By individual creative ID
    """
    try:
        resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        svc = get_rtb_bidstream_service()
        return await svc.get_config_breakdown(billing_id, by, days, resolved_buyer_id)
    except Exception as e:
        logger.error(f"Failed to get config breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs/{billing_id}/creatives", tags=["RTB Analytics"])
async def get_config_creatives(
    billing_id: str,
    size: Optional[str] = Query(None, description="Filter by creative size (e.g. 320x50)"),
    days: int = Query(30, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """List creatives for a config (optionally filtered by size)."""
    try:
        resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        svc = get_rtb_bidstream_service()
        return await svc.get_config_creatives(billing_id, days, resolved_buyer_id, size)
    except Exception as e:
        logger.error(f"Failed to get creatives for config {billing_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/creatives", tags=["RTB Analytics"])
async def get_creative_win_performance(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get creative performance using WIN RATE metrics.

    Shows: reached, bids, impressions won, win rate, waste
    NOT: clicks, CTR, conversions (that's media buyer's job)

    Status classification:
    - great: >50% win rate
    - ok: 20-50% win rate
    - review: <20% win rate
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        result = analyzer.get_creative_win_performance(limit=limit)
        result["period_days"] = days
        return result
    except Exception as e:
        logger.error(f"Failed to get creative win performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/app-drilldown", tags=["RTB Analytics"])
async def get_app_drilldown(
    app_name: str = Query(..., description="App name to analyze"),
    billing_id: Optional[str] = Query(None, description="Filter by pretargeting config"),
    days: int = Query(7, ge=1, le=90),
):
    """
    Get detailed breakdown for a specific app/publisher.

    Returns:
    - Summary stats
    - Breakdown by creative size/format (identifies wasteful formats)
    - Breakdown by country
    - Breakdown by creative ID (with links to creative details)
    """
    try:
        svc = get_rtb_bidstream_service()
        return await svc.get_app_drilldown(app_name, days, billing_id)
    except Exception as e:
        logger.error(f"Failed to get app drilldown: {e}")
        raise HTTPException(status_code=500, detail=str(e))
