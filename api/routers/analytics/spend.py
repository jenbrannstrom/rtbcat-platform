"""Spend Analytics Router.

Handles spend statistics endpoint.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from storage.serving_database import db_query_one
from .common import get_precompute_status, get_valid_billing_ids

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Analytics"])


@router.get("/analytics/spend-stats", tags=["RTB Analytics"])
async def get_spend_stats(
    days: int = Query(7, ge=1, le=90),
    billing_id: Optional[str] = Query(None, description="Filter by specific billing account ID")
):
    """
    Get overall spend statistics for the selected period.

    Returns total spend, impressions, and avg CPM from rtb_app_daily precompute table.
    Only includes data for billing_ids that belong to the current account.
    Optionally filter by a specific billing_id.
    """
    try:
        precompute_status = await get_precompute_status(
            "rtb_app_daily",
            days,
            filters=["billing_id = ?"] if billing_id else None,
            params=[billing_id] if billing_id else None,
        )
        if not precompute_status["has_rows"]:
            return {
                "period_days": days,
                "total_impressions": 0,
                "total_spend_usd": 0,
                "avg_cpm_usd": None,
                "has_spend_data": False,
                "message": "No precompute available for requested date range.",
                "precompute_status": {"rtb_app_daily": precompute_status},
            }

        if billing_id:
            # Filter by specific billing_id
            row = await db_query_one("""
                SELECT
                    COALESCE(SUM(impressions), 0) as total_impressions,
                    COALESCE(SUM(spend_micros), 0) as total_spend_micros
                FROM rtb_app_daily
                WHERE metric_date::date >= (CURRENT_DATE + ?::interval)
                  AND billing_id = ?
            """, (f'-{days} days', billing_id))
        else:
            # Get valid billing IDs for current account to prevent cross-account data mixing
            valid_billing_ids = await get_valid_billing_ids()

            if valid_billing_ids:
                # Filter by valid billing IDs
                placeholders = ",".join("?" * len(valid_billing_ids))
                row = await db_query_one(f"""
                    SELECT
                        COALESCE(SUM(impressions), 0) as total_impressions,
                        COALESCE(SUM(spend_micros), 0) as total_spend_micros
                    FROM rtb_app_daily
                    WHERE metric_date::date >= (CURRENT_DATE + ?::interval)
                      AND billing_id IN ({placeholders})
                """, (f'-{days} days', *valid_billing_ids))
            else:
                # No pretargeting configs synced yet - return no data
                row = await db_query_one("""
                    SELECT
                        COALESCE(SUM(impressions), 0) as total_impressions,
                        COALESCE(SUM(spend_micros), 0) as total_spend_micros
                    FROM rtb_app_daily
                    WHERE metric_date::date >= (CURRENT_DATE + ?::interval)
                """, (f'-{days} days',))

        total_impressions = row["total_impressions"] if row else 0
        total_spend_micros = row["total_spend_micros"] if row else 0
        total_spend_usd = total_spend_micros / 1_000_000

        # Calculate CPM: (spend / impressions) * 1000
        avg_cpm = None
        if total_impressions > 0 and total_spend_micros > 0:
            avg_cpm = (total_spend_usd / total_impressions) * 1000

        return {
            "period_days": days,
            "total_impressions": total_impressions,
            "total_spend_usd": round(total_spend_usd, 2),
            "avg_cpm_usd": round(avg_cpm, 2) if avg_cpm else None,
            "has_spend_data": total_spend_micros > 0,
            "precompute_status": {"rtb_app_daily": precompute_status},
        }
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
