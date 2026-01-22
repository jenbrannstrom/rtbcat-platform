"""Home page analytics from precomputed tables."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_store, get_current_user, resolve_buyer_id
from storage import SQLiteStore
from storage.database import db_query, db_query_one
from .common import get_precompute_status
from storage.repositories.user_repository import User
from services.home_precompute import refresh_home_summaries

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Home Analytics"])


@router.get("/analytics/home/funnel", tags=["Home Analytics"])
async def get_home_funnel(
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    limit: int = Query(30, ge=1, le=200),
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get Home funnel summary + publishers/geos from precomputed tables."""
    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        params = [f'-{days} days']
        buyer_filter = ""
        buyer_filter_applied = False
        buyer_filter_message = None
        if buyer_id:
            buyer_filter = " AND buyer_account_id = ?"
            params.append(buyer_id)
            buyer_filter_applied = True

        seat_status = await get_precompute_status(
            "home_seat_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        publisher_status = await get_precompute_status(
            "home_publisher_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        geo_status = await get_precompute_status(
            "home_geo_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        if not seat_status["has_rows"]:
            if buyer_id:
                buyer_filter_applied = False
                buyer_filter_message = (
                    "No precomputed data for this seat. Run a refresh after imports."
                )
            return {
                "has_data": False,
                "funnel": {
                    "total_reached_queries": 0,
                    "total_impressions": 0,
                    "total_bids": 0,
                    "win_rate": 0,
                    "waste_rate": 100,
                },
                "publishers": [],
                "geos": [],
                "data_sources": {
                    "publisher_count": 0,
                    "country_count": 0,
                    "period_days": days,
                    "buyer_filter_applied": buyer_filter_applied,
                    "buyer_filter_message": buyer_filter_message or (
                        "No precompute available for requested date range."
                    ),
                    "precomputed": True,
                    "precompute_status": {
                        "home_seat_daily": seat_status,
                        "home_publisher_daily": publisher_status,
                        "home_geo_daily": geo_status,
                    },
                },
            }

        funnel_row = await db_query_one(
            f"""
            SELECT
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids,
                SUM(successful_responses) as total_successful_responses,
                SUM(bid_requests) as total_bid_requests
            FROM home_seat_daily
            WHERE metric_date >= date('now', ?){buyer_filter}
            """,
            tuple(params),
        )

        total_reached = (funnel_row["total_reached"] or 0) if funnel_row else 0
        total_impressions = (funnel_row["total_impressions"] or 0) if funnel_row else 0
        total_bids = (funnel_row["total_bids"] or 0) if funnel_row else 0
        total_successful = (funnel_row["total_successful_responses"] or 0) if funnel_row else 0
        total_bid_requests = (funnel_row["total_bid_requests"] or 0) if funnel_row else 0

        effective_reached = total_reached or total_successful or total_bid_requests
        win_rate = (total_impressions / effective_reached * 100) if effective_reached > 0 else 0
        waste_rate = 100 - win_rate

        pub_rows = await db_query(
            f"""
            SELECT
                publisher_id,
                MAX(publisher_name) as publisher_name,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(bids) as total_bids,
                SUM(auctions_won) as auctions_won,
                SUM(successful_responses) as successful_responses,
                SUM(bid_requests) as bid_requests
            FROM home_publisher_daily
            WHERE metric_date >= date('now', ?){buyer_filter}
            GROUP BY publisher_id
            ORDER BY reached DESC
            LIMIT ?
            """,
            (*params, limit),
        )

        publishers = []
        for row in pub_rows:
            reached = row["reached"] or 0
            if reached == 0:
                reached = (row["successful_responses"] or 0) or (row["bid_requests"] or 0)
            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            wins = row["auctions_won"] or 0
            pub_win_rate = (imps / reached * 100) if reached > 0 else 0
            raw_name = row["publisher_name"]
            name = (raw_name or "").strip() or "Unknown publisher"
            publishers.append({
                "publisher_id": row["publisher_id"],
                "publisher_name": name,
                "reached_queries": reached,
                "bids": bids,
                "impressions": imps,
                "auctions_won": wins,
                "win_rate": round(pub_win_rate, 2),
            })

        geo_rows = await db_query(
            f"""
            SELECT
                country,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(bids) as total_bids,
                SUM(auctions_won) as auctions_won,
                SUM(successful_responses) as successful_responses,
                SUM(bid_requests) as bid_requests
            FROM home_geo_daily
            WHERE metric_date >= date('now', ?){buyer_filter}
            GROUP BY country
            ORDER BY reached DESC
            LIMIT ?
            """,
            (*params, limit),
        )

        geos = []
        for row in geo_rows:
            reached = row["reached"] or 0
            if reached == 0:
                reached = (row["successful_responses"] or 0) or (row["bid_requests"] or 0)
            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            wins = row["auctions_won"] or 0
            geo_win_rate = (imps / reached * 100) if reached > 0 else 0
            geos.append({
                "country": row["country"],
                "reached_queries": reached,
                "bids": bids,
                "impressions": imps,
                "auctions_won": wins,
                "win_rate": round(geo_win_rate, 2),
            })

        if buyer_id and total_reached == 0 and total_impressions == 0:
            buyer_filter_applied = False
            buyer_filter_message = (
                "No precomputed data for this seat. Run a refresh after imports."
            )

        publisher_count_row = await db_query_one(
            f"""
            SELECT COUNT(DISTINCT publisher_id) as cnt
            FROM home_publisher_daily
            WHERE metric_date >= date('now', ?){buyer_filter}
            """,
            tuple(params),
        )
        country_count_row = await db_query_one(
            f"""
            SELECT COUNT(DISTINCT country) as cnt
            FROM home_geo_daily
            WHERE metric_date >= date('now', ?){buyer_filter}
            """,
            tuple(params),
        )

        return {
            "has_data": effective_reached > 0,
            "funnel": {
                "total_reached_queries": effective_reached,
                "total_impressions": total_impressions,
                "total_bids": total_bids,
                "win_rate": round(win_rate, 2),
                "waste_rate": round(waste_rate, 2),
            },
            "publishers": publishers,
            "geos": geos,
            "data_sources": {
                "publisher_count": (publisher_count_row["cnt"] or 0) if publisher_count_row else 0,
                "country_count": (country_count_row["cnt"] or 0) if country_count_row else 0,
                "period_days": days,
                "buyer_filter_applied": buyer_filter_applied,
                "buyer_filter_message": buyer_filter_message,
                "precomputed": True,
                "precompute_status": {
                    "home_seat_daily": seat_status,
                    "home_publisher_daily": publisher_status,
                    "home_geo_daily": geo_status,
                },
            }
        }
    except Exception as e:
        logger.error(f"Failed to get home funnel data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/home/configs", tags=["Home Analytics"])
async def get_home_config_performance(
    days: int = Query(7, ge=1, le=30),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get per-config performance from precomputed data."""
    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        params = [f'-{days} days']
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = ?"
            params.append(buyer_id)

        config_status = await get_precompute_status(
            "home_config_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        if not config_status["has_rows"]:
            return {
                "period_days": days,
                "data_source": "home_precompute",
                "message": "No precompute available for requested date range.",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
                "precompute_status": {"home_config_daily": config_status},
            }

        rows = await db_query(
            f"""
            SELECT
                billing_id,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids_in_auction) as total_bids_in_auction,
                SUM(auctions_won) as total_auctions_won
            FROM home_config_daily
            WHERE metric_date >= date('now', ?){buyer_filter}
            GROUP BY billing_id
            ORDER BY total_reached DESC
            """,
            tuple(params),
        )

        if not rows:
            return {
                "period_days": days,
                "data_source": "home_precompute",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
            }

        configs = []
        total_reached = 0
        total_impressions = 0

        for row in rows:
            reached = row["total_reached"] or 0
            impressions = row["total_impressions"] or 0
            bids_in_auction = row["total_bids_in_auction"] or 0
            auctions_won = row["total_auctions_won"] or 0

            if bids_in_auction > 0:
                win_rate = (auctions_won / bids_in_auction * 100)
            elif reached > 0:
                win_rate = (impressions / reached * 100)
            else:
                win_rate = 0

            total_reached += reached
            total_impressions += impressions

            configs.append({
                "billing_id": row["billing_id"],
                "name": f"Config {row['billing_id']}",
                "reached": reached,
                "bids": 0,
                "impressions": impressions,
                "win_rate_pct": round(win_rate, 1),
                "waste_pct": round(100 - win_rate, 1),
                "settings": {
                    "format": "BANNER",
                    "geos": [],
                    "platforms": [],
                    "qps_limit": None,
                    "budget_usd": None,
                },
                "sizes": [],
            })

        overall_win = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        return {
            "period_days": days,
            "data_source": "home_precompute",
            "configs": configs[:20],
            "total_reached": total_reached,
            "total_impressions": total_impressions,
            "overall_win_rate_pct": round(overall_win, 1),
            "overall_waste_pct": round(100 - overall_win, 1),
            "precompute_status": {"home_config_daily": config_status},
        }
    except Exception as e:
        logger.error(f"Failed to get home config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics/home/refresh", tags=["Home Analytics"])
async def refresh_home_cache(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    dates: Optional[list[str]] = Query(None, description="Explicit YYYY-MM-DD dates to refresh"),
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = None,
    store: SQLiteStore = Depends(get_store),
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
