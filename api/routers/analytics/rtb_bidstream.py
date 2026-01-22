"""RTB Funnel & Drilldowns Router.

Handles RTB funnel analysis, publisher/geo breakdowns, config performance,
creative win performance, and app drill-down endpoints.
"""

import json
import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from storage.database import db_query, db_query_one
from api.dependencies import get_store, get_current_user, resolve_buyer_id
from storage import SQLiteStore
from storage.repositories.user_repository import User
from analytics.rtb_bidstream_analyzer import RTBFunnelAnalyzer
from .common import get_precompute_status, get_valid_billing_ids_for_buyer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Analytics"])


@router.get("/analytics/rtb-funnel", tags=["RTB Analytics"])
async def get_rtb_bidstream(
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store: SQLiteStore = Depends(get_store),
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
        # Build filter for buyer seat if specified
        buyer_filter = ""
        buyer_params = []
        buyer_filter_applied = False
        buyer_filter_message = None
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        if buyer_id:
            buyer_filter = " AND buyer_account_id = ?"
            buyer_params = [buyer_id]
            buyer_filter_applied = True
        funnel_status = await get_precompute_status(
            "rtb_funnel_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        publisher_status = await get_precompute_status(
            "rtb_publisher_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        geo_status = await get_precompute_status(
            "rtb_geo_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )

        if not funnel_status["has_rows"]:
            buyer_filter_applied = False if buyer_id else buyer_filter_applied
            buyer_filter_message = (
                "No precompute available for requested date range."
                if not buyer_id
                else "No precompute available for this seat. Run an RTB refresh after imports."
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
                    "buyer_filter_message": buyer_filter_message,
                    "bidder_id_populated": None,
                    "buyer_account_id_populated": None,
                    "precompute_status": {
                        "rtb_funnel_daily": funnel_status,
                        "rtb_publisher_daily": publisher_status,
                        "rtb_geo_daily": geo_status,
                    },
                },
            }

        funnel_row = await db_query_one(f"""
            SELECT
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids,
                SUM(successful_responses) as total_successful_responses,
                SUM(bid_requests) as total_bid_requests
            FROM rtb_funnel_daily
            WHERE metric_date >= date('now', ?){buyer_filter}
        """, (f'-{days} days', *buyer_params))

        total_reached = funnel_row["total_reached"] or 0

        total_impressions = funnel_row["total_impressions"] or 0
        total_bids = funnel_row["total_bids"] or 0
        total_successful = funnel_row["total_successful_responses"] or 0
        total_bid_requests = funnel_row["total_bid_requests"] or 0

        effective_reached = total_reached
        if effective_reached == 0:
            effective_reached = total_successful or total_bid_requests

        win_rate = (total_impressions / effective_reached * 100) if effective_reached > 0 else 0
        waste_rate = 100 - win_rate

        pub_rows = []
        if publisher_status["has_rows"]:
            pub_rows = await db_query(f"""
                SELECT
                    publisher_id,
                    publisher_name,
                    SUM(reached_queries) as reached,
                    SUM(impressions) as impressions,
                    SUM(bids) as total_bids,
                    SUM(auctions_won) as auctions_won,
                    SUM(successful_responses) as successful_responses,
                    SUM(bid_requests) as bid_requests
                FROM rtb_publisher_daily
                WHERE metric_date >= date('now', ?)
                  AND publisher_id != ''{buyer_filter}
                GROUP BY publisher_id
                ORDER BY reached DESC
                LIMIT 10
            """, (f'-{days} days', *buyer_params))

        publishers = []
        for row in pub_rows:
            reached = row["reached"] or 0
            if reached == 0:
                reached = (row["successful_responses"] or 0) or (row["bid_requests"] or 0)
            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            wins = row["auctions_won"] or 0
            pub_win_rate = (imps / reached * 100) if reached > 0 else 0
            # Handle NULL, empty string, and whitespace-only for publisher_name
            raw_name = row["publisher_name"]
            pub_name = raw_name.strip() if raw_name and raw_name.strip() else row["publisher_id"]
            if not pub_name or not str(pub_name).strip():
                pub_name = "Unknown publisher"
            publishers.append({
                "publisher_id": row["publisher_id"],
                "publisher_name": pub_name,
                "reached_queries": reached,
                "bids": bids,
                "impressions": imps,
                "auctions_won": wins,
                "win_rate": round(pub_win_rate, 2),
            })

        geo_rows = []
        if geo_status["has_rows"]:
            geo_rows = await db_query(f"""
                SELECT
                    country,
                    SUM(reached_queries) as reached,
                    SUM(impressions) as impressions,
                    SUM(bids) as total_bids,
                    SUM(auctions_won) as auctions_won,
                    SUM(successful_responses) as successful_responses,
                    SUM(bid_requests) as bid_requests
                FROM rtb_geo_daily
                WHERE metric_date >= date('now', ?)
                  AND country != ''{buyer_filter}
                GROUP BY country
                ORDER BY reached DESC
                LIMIT 10
            """, (f'-{days} days', *buyer_params))

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

        publisher_count = 0
        country_count = 0
        if publisher_status["has_rows"]:
            publisher_count_row = await db_query_one(
                f"""
                SELECT COUNT(DISTINCT publisher_id) as cnt
                FROM rtb_publisher_daily
                WHERE metric_date >= date('now', ?)
                  AND publisher_id != ''{buyer_filter}
                """,
                (f'-{days} days', *buyer_params),
            )
            publisher_count = publisher_count_row["cnt"] or 0 if publisher_count_row else 0
        if geo_status["has_rows"]:
            country_count_row = await db_query_one(
                f"""
                SELECT COUNT(DISTINCT country) as cnt
                FROM rtb_geo_daily
                WHERE metric_date >= date('now', ?)
                  AND country != ''{buyer_filter}
                """,
                (f'-{days} days', *buyer_params),
            )
            country_count = country_count_row["cnt"] or 0 if country_count_row else 0

        precompute_messages = {}
        if not publisher_status["has_rows"]:
            precompute_messages["publishers"] = "No precompute available for publisher breakdown."
        if not geo_status["has_rows"]:
            precompute_messages["geos"] = "No precompute available for geo breakdown."

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
                "publisher_count": publisher_count,
                "country_count": country_count,
                "period_days": days,
                "buyer_filter_applied": buyer_filter_applied,
                "buyer_filter_message": buyer_filter_message,
                "bidder_id_populated": None,
                "buyer_account_id_populated": None,
                "precompute_messages": precompute_messages,
                "precompute_status": {
                    "rtb_funnel_daily": funnel_status,
                    "rtb_publisher_daily": publisher_status,
                    "rtb_geo_daily": geo_status,
                },
            }
        }
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
        precompute_status = await get_precompute_status("rtb_publisher_daily", days)
        if not precompute_status["has_rows"]:
            return {
                "publishers": [],
                "count": 0,
                "period_days": days,
                "message": "No precompute available for requested date range.",
                "precompute_status": {"rtb_publisher_daily": precompute_status},
            }

        rows = await db_query("""
            SELECT
                publisher_id,
                publisher_name,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids
            FROM rtb_publisher_daily
            WHERE metric_date >= date('now', ?)
              AND publisher_id != ''
            GROUP BY publisher_id, publisher_name
            ORDER BY total_reached DESC
            LIMIT ?
        """, (f'-{days} days', limit))

        count_row = await db_query_one("""
            SELECT COUNT(DISTINCT publisher_id) as total
            FROM rtb_publisher_daily
            WHERE metric_date >= date('now', ?)
              AND publisher_id != ''
        """, (f'-{days} days',))

        publishers = []
        for row in rows:
            reached = row["total_reached"] or 0
            imps = row["total_impressions"] or 0
            bids = row["total_bids"] or 0
            win_rate = (imps / reached * 100) if reached > 0 else 0
            bid_rate = (bids / reached * 100) if reached > 0 else 0
            # Handle NULL, empty string, and whitespace-only for publisher_name
            raw_name = row["publisher_name"]
            pub_name = raw_name.strip() if raw_name and raw_name.strip() else row["publisher_id"]
            publishers.append({
                "publisher_id": row["publisher_id"],
                "publisher_name": pub_name,
                "reached_queries": reached,
                "impressions": imps,
                "bids": bids,
                "win_rate": round(win_rate, 2),
                "bid_rate": round(bid_rate, 2),
                "waste_pct": round(100 - win_rate, 2),
            })

        return {
            "publishers": publishers,
            "count": count_row["total"] if count_row else 0,
            "period_days": days,
            "precompute_status": {"rtb_publisher_daily": precompute_status},
        }
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
        precompute_status = await get_precompute_status("rtb_geo_daily", days)
        if not precompute_status["has_rows"]:
            return {
                "geos": [],
                "count": 0,
                "period_days": days,
                "message": "No precompute available for requested date range.",
                "precompute_status": {"rtb_geo_daily": precompute_status},
            }

        rows = await db_query("""
            SELECT
                country,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids
            FROM rtb_geo_daily
            WHERE metric_date >= date('now', ?)
              AND country != ''
            GROUP BY country
            ORDER BY total_reached DESC
            LIMIT ?
        """, (f'-{days} days', limit))

        count_row = await db_query_one("""
            SELECT COUNT(DISTINCT country) as total
            FROM rtb_geo_daily
            WHERE metric_date >= date('now', ?)
              AND country != ''
        """, (f'-{days} days',))

        geos = []
        for row in rows:
            reached = row["total_reached"] or 0
            imps = row["total_impressions"] or 0
            bids = row["total_bids"] or 0
            win_rate = (imps / reached * 100) if reached > 0 else 0
            bid_rate = (bids / reached * 100) if reached > 0 else 0
            geos.append({
                "country": row["country"],
                "reached_queries": reached,
                "impressions": imps,
                "bids": bids,
                "win_rate": round(win_rate, 2),
                "bid_rate": round(bid_rate, 2),
                "waste_pct": round(100 - win_rate, 2),
            })

        return {
            "geos": geos,
            "count": count_row["total"] if count_row else 0,
            "period_days": days,
            "precompute_status": {"rtb_geo_daily": precompute_status},
        }
    except Exception as e:
        logger.error(f"Failed to get geo performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs", tags=["RTB Analytics"])
async def get_config_performance(
    days: int = Query(7, ge=1, le=30),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Get performance breakdown by pretargeting config (billing_id).

    Reads from precomputed config breakdown tables and aggregates by billing_id to show:
    - Reached queries and impressions per config
    - Size-level performance within each config
    - Win rate vs waste percentages
    - Settings derived from the data (format, geos, platforms)

    Only returns data for billing_ids that belong to the specified buyer seat
    (or current account if not specified).

    Args:
        days: Number of days to analyze (default 7, max 30)
        buyer_id: Optional buyer seat ID to filter results
    """
    try:
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)

        precompute_status = await get_precompute_status(
            "config_size_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        if not precompute_status["has_rows"]:
            message = "No precompute available for requested date range."
            if buyer_id:
                message = "No precompute available for this seat. Run a config refresh after imports."
            return {
                "period_days": days,
                "data_source": "config_precompute",
                "message": message,
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
                "precompute_status": {"config_size_daily": precompute_status},
            }

        valid_billing_ids = None
        if not buyer_id:
            valid_billing_ids = await get_valid_billing_ids_for_buyer(buyer_id)
            if not valid_billing_ids:
                return {
                    "period_days": days,
                    "data_source": "config_precompute",
                    "message": "No precompute available for requested date range.",
                    "configs": [],
                    "total_reached": 0,
                    "total_impressions": 0,
                    "overall_win_rate_pct": 0,
                    "overall_waste_pct": 100,
                    "precompute_status": {"config_size_daily": precompute_status},
                }

        size_params: list = [f'-{days} days']
        size_filters = ["metric_date >= date('now', ?)"]
        if buyer_id:
            size_filters.append("buyer_account_id = ?")
            size_params.append(buyer_id)
        if valid_billing_ids:
            placeholders = ",".join("?" * len(valid_billing_ids))
            size_filters.append(f"billing_id IN ({placeholders})")
            size_params.extend(valid_billing_ids)

        rows = await db_query(
            f"""
            SELECT
                billing_id,
                creative_size,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions
            FROM config_size_daily
            WHERE {" AND ".join(size_filters)}
            GROUP BY billing_id, creative_size
            ORDER BY total_reached DESC
            """,
            tuple(size_params),
        )

        geo_filters = ["metric_date >= date('now', ?)"]
        geo_params: list = [f'-{days} days']
        if buyer_id:
            geo_filters.append("buyer_account_id = ?")
            geo_params.append(buyer_id)
        if valid_billing_ids:
            placeholders = ",".join("?" * len(valid_billing_ids))
            geo_filters.append(f"billing_id IN ({placeholders})")
            geo_params.extend(valid_billing_ids)
        geo_rows = await db_query(
            f"""
            SELECT
                billing_id,
                country
            FROM config_geo_daily
            WHERE {" AND ".join(geo_filters)}
            """,
            tuple(geo_params),
        )

        if not rows:
            return {
                "period_days": days,
                "data_source": "config_precompute",
                "message": "No precompute available for requested date range.",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
                "precompute_status": {"config_size_daily": precompute_status},
            }

        # Aggregate by billing_id
        configs_by_billing: dict = defaultdict(lambda: {
            "reached": 0,
            "impressions": 0,
            "sizes": defaultdict(lambda: {"reached": 0, "impressions": 0}),
            "countries": set(),
        })

        for row in rows:
            billing_id = row["billing_id"]
            config = configs_by_billing[billing_id]
            config["reached"] += row["total_reached"] or 0
            config["impressions"] += row["total_impressions"] or 0

            # Track size breakdown
            size = row["creative_size"] or "unknown"
            config["sizes"][size]["reached"] += row["total_reached"] or 0
            config["sizes"][size]["impressions"] += row["total_impressions"] or 0

        for row in geo_rows:
            billing_id = row["billing_id"]
            if billing_id in configs_by_billing and row["country"]:
                configs_by_billing[billing_id]["countries"].add(row["country"])

        # Convert to response format
        configs = []
        total_reached = 0
        total_impressions = 0

        for billing_id, config in sorted(configs_by_billing.items(), key=lambda x: x[1]["reached"], reverse=True):
            reached = config["reached"]
            impressions = config["impressions"]
            win_rate = (impressions / reached * 100) if reached > 0 else 0
            waste = 100 - win_rate

            total_reached += reached
            total_impressions += impressions

            # Convert sizes dict to list
            sizes_list = []
            for size, size_data in sorted(config["sizes"].items(), key=lambda x: x[1]["reached"], reverse=True):
                size_reached = size_data["reached"]
                size_impressions = size_data["impressions"]
                size_win = (size_impressions / size_reached * 100) if size_reached > 0 else 0
                sizes_list.append({
                    "size": size,
                    "reached": size_reached,
                    "impressions": size_impressions,
                    "win_rate_pct": round(size_win, 1),
                    "waste_pct": round(100 - size_win, 1),
                })

            configs.append({
                "billing_id": billing_id,
                "name": f"Config {billing_id}",
                "reached": reached,
                "bids": 0,
                "impressions": impressions,
                "win_rate_pct": round(win_rate, 1),
                "waste_pct": round(waste, 1),
                "settings": {
                    "format": "BANNER",
                    "geos": sorted(list(config["countries"]))[:10],
                    "platforms": [],
                    "qps_limit": None,
                    "budget_usd": None,
                },
                "sizes": sizes_list[:5],
            })

        overall_win = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        return {
            "period_days": days,
            "data_source": "config_precompute",
            "configs": configs[:20],
            "total_reached": total_reached,
            "total_impressions": total_impressions,
            "overall_win_rate_pct": round(overall_win, 1),
            "overall_waste_pct": round(100 - overall_win, 1),
            "precompute_status": {"config_size_daily": precompute_status},
        }

    except Exception as e:
        logger.error(f"Failed to get config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs/{billing_id}/breakdown", tags=["RTB Analytics"])
async def get_config_breakdown(
    billing_id: str,
    by: str = Query("size", pattern="^(size|geo|publisher|creative)$"),
    days: int = Query(7, ge=1, le=30),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store: SQLiteStore = Depends(get_store),
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
        breakdown = []
        resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        buyer_account_id = resolved_buyer_id or None
        table_map = {
            "size": "config_size_daily",
            "geo": "config_geo_daily",
            "publisher": "config_publisher_daily",
            "creative": "config_creative_daily",
        }
        table_name = table_map.get(by)
        if table_name:
            table_status = await get_precompute_status(
                table_name,
                days,
                filters=["billing_id = ?"] + (["buyer_account_id = ?"] if buyer_account_id else []),
                params=[billing_id] + ([buyer_account_id] if buyer_account_id else []),
            )
            if not table_status["exists"]:
                return {
                    "billing_id": billing_id,
                    "breakdown_by": by,
                    "breakdown": [],
                    "is_aggregate": False,
                    "has_funnel_metrics": False,
                    "no_data_reason": (
                        "Config breakdown tables are missing. Run migration 020 and "
                        "recompute config breakdowns."
                    ),
                }
            if not table_status["has_rows"]:
                return {
                    "billing_id": billing_id,
                    "breakdown_by": by,
                    "breakdown": [],
                    "is_aggregate": False,
                    "has_funnel_metrics": False,
                    "no_data_reason": (
                        "No precompute available for requested date range. Run a config refresh after imports."
                    ),
                    "precompute_status": {table_name: table_status},
                }
        # Note: is_aggregate is always False - we only show per-config data now
        # Account-wide data is shown in the main page sections, not in config breakdown
        target_geo_ids: list[str] = []
        target_country_codes: list[str] = []
        if by == "creative":
            config_row = await db_query_one(
                """
                SELECT included_geos
                FROM pretargeting_configs
                WHERE billing_id = ?
                LIMIT 1
                """,
                (billing_id,),
            )
            if config_row and "included_geos" in config_row.keys() and config_row["included_geos"]:
                try:
                    target_geo_ids = json.loads(config_row["included_geos"]) or []
                except (TypeError, json.JSONDecodeError):
                    target_geo_ids = []
            if target_geo_ids:
                placeholders = ",".join("?" for _ in target_geo_ids)
                try:
                    rows = await db_query(
                        f"""
                        SELECT google_geo_id, country_code
                        FROM geographies
                        WHERE google_geo_id IN ({placeholders})
                        """,
                        tuple(target_geo_ids),
                    )
                    target_country_codes = sorted(
                        {row["country_code"] for row in rows if "country_code" in row.keys() and row["country_code"]}
                    )
                except Exception:
                    target_country_codes = []

        if by in ("geo", "publisher"):
            seat_clause = ""
            seat_params: tuple = ()
            if buyer_account_id:
                seat_clause = " AND buyer_account_id = ?"
                seat_params = (buyer_account_id,)

            if by == "geo":
                rows = await db_query(
                    f"""
                    SELECT
                        country as name,
                        COALESCE(SUM(reached_queries), 0) as total_reached,
                        COALESCE(SUM(impressions), 0) as total_impressions,
                        COALESCE(SUM(spend_micros), 0) as total_spend_micros
                    FROM config_geo_daily
                    WHERE billing_id = ?
                      AND metric_date >= date('now', ?)
                      {seat_clause}
                    GROUP BY country
                    ORDER BY total_reached DESC
                    LIMIT 50
                    """,
                    (billing_id, f'-{days} days', *seat_params),
                )
            else:
                rows = await db_query(
                    f"""
                    SELECT
                        COALESCE(publisher_name, publisher_id) as name,
                        COALESCE(SUM(reached_queries), 0) as total_reached,
                        COALESCE(SUM(impressions), 0) as total_impressions,
                        COALESCE(SUM(spend_micros), 0) as total_spend_micros
                    FROM config_publisher_daily
                    WHERE billing_id = ?
                      AND metric_date >= date('now', ?)
                      {seat_clause}
                    GROUP BY COALESCE(publisher_name, publisher_id)
                    ORDER BY total_reached DESC
                    LIMIT 50
                    """,
                    (billing_id, f'-{days} days', *seat_params),
                )

            if not rows:
                return {
                    "billing_id": billing_id,
                    "breakdown_by": by,
                    "breakdown": [],
                    "is_aggregate": False,
                    "has_funnel_metrics": False,
                    "no_data_reason": (
                        f"No {by} breakdown data. This usually means the catscan-quality report is missing "
                        f"{'Country' if by == 'geo' else 'Publisher'} fields. Add those dimensions if available, "
                        "then re-import and refresh precompute."
                    ),
                }
        elif by == "creative":
            # For creative breakdown, use ONLY quality data (per-billing_id accurate)
            # The bidsinauction CSV doesn't have billing_id, so JOINing would mix
            # bid metrics from ALL configs using the same creative.
            # Using quality-only ensures per-billing_id accuracy.
            # Win rate = impressions/reached (conversion rate, per-config accurate)
            seat_clause = ""
            seat_params: tuple = ()
            if buyer_account_id:
                seat_clause = " AND buyer_account_id = ?"
                seat_params = (buyer_account_id,)
            rows = await db_query(
                f"""
                SELECT
                    d.creative_id as name,
                    COALESCE(SUM(d.reached_queries), 0) as total_reached,
                    COALESCE(SUM(d.impressions), 0) as total_impressions,
                    COALESCE(SUM(d.spend_micros), 0) as total_spend_micros,
                    MAX(c.detected_language) as detected_language,
                    MAX(c.detected_language_code) as detected_language_code
                FROM config_creative_daily d
                LEFT JOIN creatives c
                    ON c.id = d.creative_id
                WHERE d.billing_id = ?
                  AND d.metric_date >= date('now', ?)
                  {seat_clause}
                GROUP BY d.creative_id
                ORDER BY total_reached DESC
                LIMIT 50
                """,
                (billing_id, f'-{days} days', *seat_params),
            )
            has_funnel_data = False  # Never has funnel data for creative breakdown
            if not rows:
                return {
                    "billing_id": billing_id,
                    "breakdown_by": by,
                    "breakdown": [],
                    "is_aggregate": False,
                    "has_funnel_metrics": False,
                    "no_data_reason": (
                        "No creative breakdown data. Run a config precompute refresh after importing "
                        "catscan-quality for this seat."
                    ),
                }

        else:
            seat_clause = ""
            seat_params: tuple = ()
            if buyer_account_id:
                seat_clause = " AND buyer_account_id = ?"
                seat_params = (buyer_account_id,)
            rows = await db_query(
                f"""
                SELECT
                    creative_size as name,
                    SUM(reached_queries) as total_reached,
                    SUM(impressions) as total_impressions,
                    COALESCE(SUM(spend_micros), 0) as total_spend_micros
                FROM config_size_daily
                WHERE billing_id = ?
                  AND metric_date >= date('now', ?)
                  {seat_clause}
                GROUP BY creative_size
                ORDER BY total_reached DESC
                LIMIT 50
                """,
                (billing_id, f'-{days} days', *seat_params),
            )
            has_funnel_data = False
            if not rows:
                return {
                    "billing_id": billing_id,
                    "breakdown_by": by,
                    "breakdown": [],
                    "is_aggregate": False,
                    "has_funnel_metrics": False,
                    "no_data_reason": (
                        "No size breakdown data. Run a config precompute refresh after importing "
                        "catscan-quality for this seat."
                    ),
                }

        for row in rows:
            reached = row["total_reached"] or 0
            impressions = row["total_impressions"] or 0
            bids = row["total_bids"] if "total_bids" in row.keys() else 0
            bids_in_auction = row["total_bids_in_auction"] if "total_bids_in_auction" in row.keys() else 0
            auctions_won = row["total_auctions_won"] if "total_auctions_won" in row.keys() else 0
            spend_micros = row["total_spend_micros"] if "total_spend_micros" in row.keys() else 0

            # Calculate win rate based on best available data
            # Prefer: auctions_won / bids_in_auction (true auction win rate)
            # Fallback: impressions / reached (simplified win rate)
            if bids_in_auction > 0:
                win_rate = (auctions_won / bids_in_auction * 100)
            elif reached > 0:
                win_rate = (impressions / reached * 100)
            else:
                win_rate = 0

            waste_rate = 100 - win_rate

            item = {
                "name": row["name"] or "Unknown",
                "reached": reached,
                "impressions": impressions,
                "win_rate": round(win_rate, 1),
                "waste_rate": round(waste_rate, 1),
                "spend_usd": round(spend_micros / 1_000_000, 2),
            }

            # Include funnel metrics if available
            if bids > 0 or bids_in_auction > 0:
                item["bids"] = bids
                item["bids_in_auction"] = bids_in_auction
                item["auctions_won"] = auctions_won
            if by == "creative":
                language_code = row["detected_language_code"] if "detected_language_code" in row.keys() else None
                language_name = row["detected_language"] if "detected_language" in row.keys() else None
                item["creative_language"] = language_name or language_code
                item["creative_language_code"] = language_code
                if target_country_codes:
                    from utils.language_country_map import check_language_country_match
                    from utils.country_codes import get_country_alpha3

                    match = check_language_country_match(language_code or "", target_country_codes)
                    mismatched = [get_country_alpha3(code) for code in match["mismatched_countries"]]
                    item["target_countries"] = [get_country_alpha3(code) for code in target_country_codes]
                    item["language_mismatch"] = len(mismatched) > 0 and bool(language_code)
                    item["mismatched_countries"] = mismatched
                elif target_geo_ids:
                    item["target_countries"] = target_geo_ids
                    item["language_mismatch"] = False
                else:
                    item["target_countries"] = []
                    item["language_mismatch"] = False

            breakdown.append(item)

        return {
            "billing_id": billing_id,
            "breakdown_by": by,
            "breakdown": breakdown,
            "is_aggregate": False,  # Always per-config, never account-wide
            "has_funnel_metrics": any(item.get("bids_in_auction", 0) > 0 for item in breakdown),
        }

    except Exception as e:
        logger.error(f"Failed to get config breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs/{billing_id}/creatives", tags=["RTB Analytics"])
async def get_config_creatives(
    billing_id: str,
    size: Optional[str] = Query(None, description="Filter by creative size (e.g. 320x50)"),
    days: int = Query(30, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """List creatives for a config (optionally filtered by size)."""
    try:
        resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        buyer_account_id = resolved_buyer_id or None
        precompute_status = await get_precompute_status(
            "config_creative_daily",
            days,
            filters=["billing_id = ?"] + (["buyer_account_id = ?"] if buyer_account_id else []),
            params=[billing_id] + ([buyer_account_id] if buyer_account_id else []),
        )
        if not precompute_status["has_rows"]:
            return {
                "creatives": [],
                "message": "No precompute available for requested date range.",
                "precompute_status": {"config_creative_daily": precompute_status},
            }

        where = ["billing_id = ?", "metric_date >= date('now', ?)"]
        params: list = [billing_id, f'-{days} days']
        if size:
            where.append("creative_size = ?")
            params.append(size)
        if buyer_account_id:
            where.append("buyer_account_id = ?")
            params.append(buyer_account_id)

        rows = await db_query(
            f"""
            SELECT DISTINCT creative_id
            FROM config_creative_daily
            WHERE {" AND ".join(where)}
              AND creative_id IS NOT NULL
              AND creative_id != ''
            LIMIT 200
            """,
            tuple(params),
        )
        creative_ids = [row["creative_id"] for row in rows if row["creative_id"]]
        if not creative_ids:
            return {"creatives": [], "precompute_status": {"config_creative_daily": precompute_status}}

        creative_rows = await db_query(
            f"""
            SELECT id, name, format, width, height
            FROM creatives
            WHERE id IN ({placeholders})
            """,
            tuple(creative_ids),
        )
        creative_map = {row["id"]: row for row in creative_rows}

        creatives = []
        for creative_id in creative_ids:
            row = creative_map.get(creative_id)
            creatives.append({
                "id": creative_id,
                "name": row["name"] if row and row["name"] else creative_id,
                "format": row["format"] if row else None,
                "width": row["width"] if row else None,
                "height": row["height"] if row else None,
                "serving_countries": [],
            })

        return {"creatives": creatives, "precompute_status": {"config_creative_daily": precompute_status}}

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
        app_summary_status = await get_precompute_status(
            "rtb_app_daily",
            days,
            filters=["app_name = ?"] + (["billing_id = ?"] if billing_id else []),
            params=[app_name] + ([billing_id] if billing_id else []),
        )
        app_size_status = await get_precompute_status(
            "rtb_app_size_daily",
            days,
            filters=["app_name = ?"] + (["billing_id = ?"] if billing_id else []),
            params=[app_name] + ([billing_id] if billing_id else []),
        )
        app_country_status = await get_precompute_status(
            "rtb_app_country_daily",
            days,
            filters=["app_name = ?"] + (["billing_id = ?"] if billing_id else []),
            params=[app_name] + ([billing_id] if billing_id else []),
        )
        app_creative_status = await get_precompute_status(
            "rtb_app_creative_daily",
            days,
            filters=["app_name = ?"] + (["billing_id = ?"] if billing_id else []),
            params=[app_name] + ([billing_id] if billing_id else []),
        )

        if not app_summary_status["has_rows"]:
            fallback_message = "No precompute available for requested date range."
            if billing_id:
                app_total_status = await get_precompute_status(
                    "rtb_app_daily",
                    days,
                    filters=["app_name = ?"],
                    params=[app_name],
                )
                if app_total_status["has_rows"]:
                    fallback_message = (
                        f"Data exists for '{app_name}' but not for this specific pretargeting config "
                        f"(billing_id={billing_id}). Run RTB precompute for that config."
                    )
            return {
                "app_name": app_name,
                "has_data": False,
                "message": fallback_message,
                "precompute_status": {
                    "rtb_app_daily": app_summary_status,
                    "rtb_app_size_daily": app_size_status,
                    "rtb_app_country_daily": app_country_status,
                    "rtb_app_creative_daily": app_creative_status,
                },
            }

        billing_clause = ""
        billing_params: list[str] = []
        if billing_id:
            billing_clause = " AND billing_id = ?"
            billing_params.append(billing_id)

        summary_row = await db_query_one(
            f"""
            SELECT
                app_name,
                MAX(app_id) as app_id,
                COUNT(DISTINCT metric_date) as days_with_data,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                SUM(spend_micros) as total_spend_micros
            FROM rtb_app_daily
            WHERE app_name = ?{billing_clause}
              AND metric_date >= date('now', ?)
            """,
            (app_name, *billing_params, f'-{days} days'),
        )

        total_reached = summary_row["total_reached"] or 0
        total_impressions = summary_row["total_impressions"] or 0
        win_rate = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        count_params = (app_name, *billing_params, f'-{days} days')
        creative_count_row = await db_query_one(
            f"""
            SELECT COUNT(DISTINCT creative_id) as creative_count
            FROM rtb_app_creative_daily
            WHERE app_name = ?{billing_clause}
              AND metric_date >= date('now', ?)
            """,
            count_params,
        )
        country_count_row = await db_query_one(
            f"""
            SELECT COUNT(DISTINCT country) as country_count
            FROM rtb_app_country_daily
            WHERE app_name = ?{billing_clause}
              AND metric_date >= date('now', ?)
            """,
            count_params,
        )

        size_rows = await db_query(
            f"""
            SELECT
                creative_size,
                creative_format,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_app_size_daily
            WHERE app_name = ?{billing_clause}
              AND metric_date >= date('now', ?)
            GROUP BY creative_size, creative_format
            ORDER BY reached DESC
            """,
            count_params,
        )
        sizes = []
        for row in size_rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            size_win_rate = (imps / reached * 100) if reached > 0 else 0
            is_wasteful = size_win_rate < (win_rate * 0.5) and reached > 10000
            sizes.append({
                "size": row["creative_size"],
                "format": row["creative_format"],
                "reached": reached,
                "impressions": imps,
                "clicks": row["clicks"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "win_rate": round(size_win_rate, 1),
                "waste_pct": round(100 - size_win_rate, 1),
                "pct_of_traffic": round(reached / total_reached * 100, 1) if total_reached > 0 else 0,
                "is_wasteful": is_wasteful,
            })

        country_rows = await db_query(
            f"""
            SELECT
                country,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_app_country_daily
            WHERE app_name = ?{billing_clause}
              AND metric_date >= date('now', ?)
            GROUP BY country
            ORDER BY reached DESC
            """,
            count_params,
        )

        countries = []
        for row in country_rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            country_win_rate = (imps / reached * 100) if reached > 0 else 0
            countries.append({
                "country": row["country"],
                "reached": reached,
                "impressions": imps,
                "clicks": row["clicks"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "win_rate": round(country_win_rate, 1),
                "pct_of_traffic": round(reached / total_reached * 100, 1) if total_reached > 0 else 0,
            })

        creative_rows = await db_query(
            f"""
            SELECT
                creative_id,
                creative_size,
                creative_format,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_app_creative_daily
            WHERE app_name = ?{billing_clause}
              AND metric_date >= date('now', ?)
            GROUP BY creative_id, creative_size, creative_format
            ORDER BY reached DESC
            LIMIT 10
            """,
            count_params,
        )

        creatives = []
        for row in creative_rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            creative_win_rate = (imps / reached * 100) if reached > 0 else 0
            creatives.append({
                "creative_id": row["creative_id"],
                "size": row["creative_size"],
                "format": row["creative_format"],
                "reached": reached,
                "impressions": imps,
                "clicks": row["clicks"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "win_rate": round(creative_win_rate, 1),
                "pct_of_traffic": round(reached / total_reached * 100, 1) if total_reached > 0 else 0,
            })

        wasteful_sizes = [s for s in sizes if s["is_wasteful"]]
        waste_insight = None
        if wasteful_sizes:
            worst = max(wasteful_sizes, key=lambda x: x["reached"])
            waste_insight = {
                "type": "size",
                "value": worst["size"],
                "message": (
                    f"{worst['size']} has only {worst['win_rate']}% win rate but accounts for "
                    f"{worst['pct_of_traffic']}% of traffic"
                ),
                "wasted_queries": int(worst["reached"] * (1 - worst["win_rate"] / 100)),
                "recommendation": f"Consider removing {worst['size']} from pretargeting for this app",
            }

        bid_filtering = []
        creative_ids = [c["creative_id"] for c in creatives]
        if creative_ids:
            try:
                table_check = await db_query_one("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='rtb_bid_filtering'
                """)

                if table_check:
                    placeholders = ",".join(["?" for _ in creative_ids])
                    filtering_params = creative_ids + [f'-{days} days']

                    filtering_rows = await db_query(f"""
                        SELECT
                            filtering_reason,
                            SUM(bids) as total_bids,
                            SUM(bids_in_auction) as bids_passed,
                            SUM(opportunity_cost_micros) as opportunity_cost_micros
                        FROM rtb_bid_filtering
                        WHERE creative_id IN ({placeholders})
                          AND metric_date >= date('now', ?)
                        GROUP BY filtering_reason
                        ORDER BY total_bids DESC
                        LIMIT 10
                    """, tuple(filtering_params))

                    total_filtered_bids = sum(r["total_bids"] or 0 for r in filtering_rows)

                    for row in filtering_rows:
                        bids = row["total_bids"] or 0
                        passed = row["bids_passed"] or 0
                        bid_filtering.append({
                            "reason": row["filtering_reason"],
                            "bids_filtered": bids,
                            "bids_passed": passed,
                            "pct_of_filtered": (
                                round(bids / total_filtered_bids * 100, 1)
                                if total_filtered_bids > 0
                                else 0
                            ),
                            "opportunity_cost_usd": (row["opportunity_cost_micros"] or 0) / 1_000_000,
                        })
            except Exception as e:
                logger.warning(f"Could not fetch bid filtering data: {e}")

        return {
            "app_name": app_name,
            "app_id": summary_row["app_id"],
            "has_data": True,
            "period_days": days,
            "summary": {
                "total_reached": total_reached,
                "total_impressions": total_impressions,
                "total_clicks": summary_row["total_clicks"] or 0,
                "total_spend_usd": (summary_row["total_spend_micros"] or 0) / 1_000_000,
                "win_rate": round(win_rate, 1),
                "waste_rate": round(100 - win_rate, 1),
                "days_with_data": summary_row["days_with_data"],
                "creative_count": creative_count_row["creative_count"] if creative_count_row else 0,
                "country_count": country_count_row["country_count"] if country_count_row else 0,
            },
            "by_size": sizes,
            "by_country": countries,
            "by_creative": creatives,
            "waste_insight": waste_insight,
            "bid_filtering": bid_filtering,
            "precompute_status": {
                "rtb_app_daily": app_summary_status,
                "rtb_app_size_daily": app_size_status,
                "rtb_app_country_daily": app_country_status,
                "rtb_app_creative_daily": app_creative_status,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get app drilldown: {e}")
        raise HTTPException(status_code=500, detail=str(e))
