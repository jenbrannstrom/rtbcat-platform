"""Home page analytics from precomputed tables."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_store, get_current_user, resolve_buyer_id
from services.auth_service import User
from services.home_precompute import refresh_home_summaries
from services.home_analytics_service import HomeAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Home Analytics"])


@router.get("/analytics/home/funnel", tags=["Home Analytics"])
async def get_home_funnel(
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    limit: int = Query(30, ge=1, le=200),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get Home funnel summary + publishers/geos from precomputed tables."""
    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        service = HomeAnalyticsService()
        return await service.get_funnel_payload(
            days=days,
            buyer_id=buyer_id,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Failed to get home funnel data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/home/configs", tags=["Home Analytics"])
async def get_home_config_performance(
    days: int = Query(7, ge=1, le=30),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get per-config performance from precomputed data."""
    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        service = HomeAnalyticsService()
        return await service.get_config_payload(days=days, buyer_id=buyer_id)
    except Exception as e:
        logger.error(f"Failed to get home config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/home/endpoint-efficiency", tags=["Home Analytics"])
async def get_home_endpoint_efficiency(
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get allocated-vs-observed endpoint efficiency and reconciliation."""
    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        service = HomeAnalyticsService()
        return await service.get_endpoint_efficiency_payload(days=days, buyer_id=buyer_id)
    except Exception as e:
        logger.error(f"Failed to get endpoint efficiency data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics/home/refresh", tags=["Home Analytics"])
async def refresh_home_cache(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    dates: Optional[list[str]] = Query(None, description="Explicit YYYY-MM-DD dates to refresh"),
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = None,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Refresh Home precomputed tables for a date range."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    refresh_kwargs = {"buyer_account_id": buyer_id}
    if dates:
        refresh_kwargs["dates"] = dates
    elif start_date and end_date:
        refresh_kwargs["start_date"] = start_date
        refresh_kwargs["end_date"] = end_date
    else:
        refresh_kwargs["days"] = days
    return await refresh_home_summaries(**refresh_kwargs)
