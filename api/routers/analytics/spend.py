"""Spend Analytics Router.

Handles spend statistics endpoint.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Analytics"])


@router.get("/analytics/spend-stats", tags=["RTB Analytics"])
async def get_spend_stats(
    days: int = Query(7, ge=1, le=90),
    billing_id: Optional[str] = Query(
        None,
        description="Filter by specific pretargeting config ID (billing_id)",
    )
):
    """
    Get overall spend statistics for the selected period.

    Returns total spend, impressions, and avg CPM from rtb_app_daily precompute table.
    Only includes data for pretargeting configs (`billing_id`) that belong to
    the current account. Optionally filter by a specific `billing_id`.
    """
    try:
        service = AnalyticsService()
        stats = await service.get_spend_stats(days, billing_id)

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

    except Exception as e:
        logger.error(f"Failed to get spend stats: {e}")
        return {
            "period_days": days,
            "total_impressions": 0,
            "total_spend_usd": 0,
            "avg_cpm_usd": None,
            "has_spend_data": False,
            "message": "No precompute available for requested date range.",
            "precompute_status": {"rtb_app_daily": {"table": "rtb_app_daily", "exists": False, "has_rows": False, "row_count": 0}},
        }
