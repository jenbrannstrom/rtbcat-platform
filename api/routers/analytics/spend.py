"""Spend Analytics Router.

Handles spend statistics endpoint.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_store, get_current_user, resolve_buyer_id
from services.analytics_service import AnalyticsService
from services.auth_service import User
from .common import validate_identifier_integrity, validate_billing_id_ownership

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Analytics"])


@router.get("/analytics/spend-stats", tags=["RTB Analytics"])
async def get_spend_stats(
    days: int = Query(7, ge=1, le=90),
    billing_id: Optional[str] = Query(
        None,
        description="Filter by specific pretargeting config ID (billing_id)",
    ),
    buyer_id: Optional[str] = Query(
        None,
        description="Filter by buyer seat ID",
    ),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Get overall spend statistics for the selected period.

    Returns total spend, impressions, and avg CPM from rtb_app_daily precompute table.
    Only includes data for pretargeting configs (`billing_id`) that belong to
    the current account. Optionally filter by a specific `billing_id`.

    `buyer_id` scopes the spend query. When `billing_id` is also provided, it is
    additionally used for ownership validation.
    """
    try:
        resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        if billing_id:
            validate_identifier_integrity(buyer_id=resolved_buyer_id, billing_id=billing_id)
            await validate_billing_id_ownership(billing_id, resolved_buyer_id)
        service = AnalyticsService()
        stats = await service.get_spend_stats(days, billing_id, resolved_buyer_id)

        response = {
            "period_days": stats.period_days,
            "total_impressions": stats.total_impressions,
            "total_spend_usd": stats.total_spend_usd,
            "avg_cpm_usd": stats.avg_cpm_usd,
            "has_spend_data": stats.has_spend_data,
            "precompute_status": stats.precompute_status,
        }
        if stats.message:
            response["message"] = stats.message
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get spend stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
