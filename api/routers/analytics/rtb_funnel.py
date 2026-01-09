"""RTB Funnel & Drilldowns Router.

Handles RTB funnel analysis, publisher/geo breakdowns, config performance,
creative win performance, and app drill-down endpoints.
"""

import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from storage.database import db_query, db_query_one
from analytics.rtb_funnel_analyzer import RTBFunnelAnalyzer
from .common import get_valid_billing_ids

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Analytics"])


@router.get("/analytics/rtb-funnel", tags=["RTB Analytics"])
async def get_rtb_funnel(days: int = Query(7, ge=1, le=90)):
    """
    Get RTB funnel analysis from database.

    Provides:
    - Funnel summary: Reached Queries -> Impressions
    - Publisher performance with win rates
    - Geographic breakdown
    """
    try:
        # Get funnel summary from database - use rtb_funnel for pipeline metrics
        funnel_row = await db_query_one("""
            SELECT
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids,
                COUNT(DISTINCT publisher_id) as publisher_count,
                COUNT(DISTINCT country) as country_count
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?)
        """, (f'-{days} days',))

        total_reached = funnel_row["total_reached"] or 0
        total_impressions = funnel_row["total_impressions"] or 0
        total_bids = funnel_row["total_bids"] or 0

        win_rate = (total_impressions / total_reached * 100) if total_reached > 0 else 0
        waste_rate = 100 - win_rate

        # Get top publishers
        pub_rows = await db_query("""
            SELECT
                publisher_id,
                publisher_name,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(bids) as total_bids
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?) AND publisher_id IS NOT NULL
            GROUP BY publisher_id
            ORDER BY reached DESC
            LIMIT 10
        """, (f'-{days} days',))

        publishers = []
        for row in pub_rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            pub_win_rate = (imps / reached * 100) if reached > 0 else 0
            # Handle NULL, empty string, and whitespace-only for publisher_name
            raw_name = row["publisher_name"]
            pub_name = raw_name.strip() if raw_name and raw_name.strip() else row["publisher_id"]
            publishers.append({
                "publisher_id": row["publisher_id"],
                "publisher_name": pub_name,
                "reached_queries": reached,
                "bids": bids,
                "impressions": imps,
                "win_rate": round(pub_win_rate, 2),
            })

        # Get top geos
        geo_rows = await db_query("""
            SELECT
                country,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(bids) as total_bids
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?) AND country IS NOT NULL
            GROUP BY country
            ORDER BY reached DESC
            LIMIT 10
        """, (f'-{days} days',))

        geos = []
        for row in geo_rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            geo_win_rate = (imps / reached * 100) if reached > 0 else 0
            geos.append({
                "country": row["country"],
                "reached_queries": reached,
                "bids": bids,
                "impressions": imps,
                "win_rate": round(geo_win_rate, 2),
            })

        return {
            "has_data": total_reached > 0,
            "funnel": {
                "total_reached_queries": total_reached,
                "total_impressions": total_impressions,
                "total_bids": total_bids,
                "win_rate": round(win_rate, 2),
                "waste_rate": round(waste_rate, 2),
            },
            "publishers": publishers,
            "geos": geos,
            "data_sources": {
                "publisher_count": funnel_row["publisher_count"] or 0,
                "country_count": funnel_row["country_count"] or 0,
                "period_days": days,
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
        # Query publisher data from database
        rows = await db_query("""
            SELECT
                publisher_id,
                publisher_name,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?)
            GROUP BY publisher_id, publisher_name
            ORDER BY total_reached DESC
            LIMIT ?
        """, (f'-{days} days', limit))

        # Get total count
        count_row = await db_query_one("""
            SELECT COUNT(DISTINCT publisher_id) as total
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?)
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
        # Query geo data from database
        rows = await db_query("""
            SELECT
                country,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?)
            GROUP BY country
            ORDER BY total_reached DESC
            LIMIT ?
        """, (f'-{days} days', limit))

        # Get total count
        count_row = await db_query_one("""
            SELECT COUNT(DISTINCT country) as total
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?)
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
        }
    except Exception as e:
        logger.error(f"Failed to get geo performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs", tags=["RTB Analytics"])
async def get_config_performance(
    days: int = Query(7, ge=1, le=30),
):
    """
    Get performance breakdown by pretargeting config (billing_id).

    Reads from the rtb_daily table (populated by CSV import) and aggregates
    by billing_id to show:
    - Reached queries and impressions per config
    - Size-level performance within each config
    - Win rate vs waste percentages
    - Settings derived from the data (format, geos, platforms)

    Only returns data for billing_ids that belong to the current account
    (those synced in pretargeting_configs table).
    """
    try:
        # Get valid billing IDs for current account to prevent cross-account data mixing
        valid_billing_ids = await get_valid_billing_ids()

        # Query aggregated data by billing_id from rtb_daily
        # Use bids_in_auction/auctions_won as they're populated by bids-in-auction CSV
        # Fall back to reached_queries/impressions if bids data not available
        if valid_billing_ids:
            placeholders = ",".join("?" * len(valid_billing_ids))
            rows = await db_query(f"""
                SELECT
                    billing_id,
                    creative_size,
                    creative_format,
                    country,
                    platform,
                    COALESCE(SUM(bids_in_auction), SUM(reached_queries), 0) as total_reached,
                    COALESCE(SUM(auctions_won), SUM(impressions), 0) as total_impressions
                FROM rtb_daily
                WHERE metric_date >= date('now', ?)
                  AND billing_id IN ({placeholders})
                GROUP BY billing_id, creative_size, creative_format, country, platform
                ORDER BY total_reached DESC
            """, (f'-{days} days', *valid_billing_ids))
        else:
            # No pretargeting configs synced yet - return all data as fallback
            rows = await db_query("""
                SELECT
                    billing_id,
                    creative_size,
                    creative_format,
                    country,
                    platform,
                    COALESCE(SUM(bids_in_auction), SUM(reached_queries), 0) as total_reached,
                    COALESCE(SUM(auctions_won), SUM(impressions), 0) as total_impressions
                FROM rtb_daily
                WHERE metric_date >= date('now', ?)
                GROUP BY billing_id, creative_size, creative_format, country, platform
                ORDER BY total_reached DESC
            """, (f'-{days} days',))

        if not rows:
            # No per-config data in rtb_daily - fall back to aggregate from rtb_funnel
            # This happens when the imported CSVs don't have billing_id breakdown
            funnel_agg = await db_query_one("""
                SELECT
                    SUM(reached_queries) as total_reached,
                    SUM(impressions) as total_impressions
                FROM rtb_funnel
                WHERE metric_date >= date('now', ?)
            """, (f'-{days} days',))

            if funnel_agg and (funnel_agg["total_reached"] or 0) > 0:
                total_reached = funnel_agg["total_reached"] or 0
                total_impressions = funnel_agg["total_impressions"] or 0
                win_rate = (total_impressions / total_reached * 100) if total_reached > 0 else 0

                return {
                    "period_days": days,
                    "data_source": "rtb_funnel_aggregate",
                    "message": "Per-config breakdown not available. Showing aggregate funnel data.",
                    "configs": [],
                    "total_reached": total_reached,
                    "total_impressions": total_impressions,
                    "overall_win_rate_pct": round(win_rate, 1),
                    "overall_waste_pct": round(100 - win_rate, 1),
                }

            # No data at all
            return {
                "period_days": days,
                "data_source": "database",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
            }

        # Aggregate by billing_id
        configs_by_billing: dict = defaultdict(lambda: {
            "reached": 0,
            "impressions": 0,
            "sizes": defaultdict(lambda: {"reached": 0, "impressions": 0}),
            "formats": set(),
            "countries": set(),
            "platforms": set(),
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

            # Track settings
            if row["creative_format"]:
                config["formats"].add(row["creative_format"])
            if row["country"]:
                config["countries"].add(row["country"])
            if row["platform"]:
                config["platforms"].add(row["platform"])

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

            # Determine format from collected formats
            formats = list(config["formats"])
            primary_format = formats[0] if formats else "BANNER"

            configs.append({
                "billing_id": billing_id,
                "name": f"Config {billing_id}",
                "reached": reached,
                "bids": 0,
                "impressions": impressions,
                "win_rate_pct": round(win_rate, 1),
                "waste_pct": round(waste, 1),
                "settings": {
                    "format": primary_format,
                    "geos": sorted(list(config["countries"]))[:10],
                    "platforms": sorted(list(config["platforms"])),
                    "qps_limit": None,
                    "budget_usd": None,
                },
                "sizes": sizes_list[:5],
            })

        overall_win = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        return {
            "period_days": days,
            "data_source": "database",
            "configs": configs[:20],
            "total_reached": total_reached,
            "total_impressions": total_impressions,
            "overall_win_rate_pct": round(overall_win, 1),
            "overall_waste_pct": round(100 - overall_win, 1),
        }

    except Exception as e:
        logger.error(f"Failed to get config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs/{billing_id}/breakdown", tags=["RTB Analytics"])
async def get_config_breakdown(
    billing_id: str,
    by: str = Query("size", pattern="^(size|geo|publisher|creative)$"),
    days: int = Query(7, ge=1, le=30),
):
    """
    Get detailed breakdown for a specific pretargeting config.

    Breakdown types:
    - size: By creative size (300x250, 320x50, etc.)
    - geo: By country/region
    - publisher: By app/publisher
    - creative: By individual creative ID
    """
    # Map breakdown type to column
    column_map = {
        "size": "creative_size",
        "geo": "country",
        "publisher": "app_name",
        "creative": "creative_id",
    }
    group_col = column_map.get(by, "creative_size")

    try:
        # Query aggregated data for this billing_id
        # Use bids_in_auction/auctions_won as primary metrics
        rows = await db_query(f"""
            SELECT
                {group_col} as name,
                COALESCE(SUM(bids_in_auction), SUM(reached_queries), 0) as total_reached,
                COALESCE(SUM(auctions_won), SUM(impressions), 0) as total_impressions
            FROM rtb_daily
            WHERE billing_id = ?
              AND metric_date >= date('now', ?)
              AND {group_col} IS NOT NULL
              AND {group_col} != ''
            GROUP BY {group_col}
            ORDER BY total_reached DESC
            LIMIT 50
        """, (billing_id, f'-{days} days'))

        breakdown = []
        for row in rows:
            reached = row["total_reached"] or 0
            impressions = row["total_impressions"] or 0
            win_rate = (impressions / reached * 100) if reached > 0 else 0
            waste_rate = 100 - win_rate

            breakdown.append({
                "name": row["name"] or "Unknown",
                "reached": reached,
                "win_rate": round(win_rate, 1),
                "waste_rate": round(waste_rate, 1),
            })

        return {
            "billing_id": billing_id,
            "breakdown_by": by,
            "breakdown": breakdown,
        }

    except Exception as e:
        logger.error(f"Failed to get config breakdown: {e}")
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
        # Build base WHERE clause
        where_clauses = ["app_name = ?"]
        params = [app_name]

        if billing_id:
            where_clauses.append("billing_id = ?")
            params.append(billing_id)

        where_clauses.append("metric_date >= date('now', ?)")
        params.append(f'-{days} days')

        where_sql = " AND ".join(where_clauses)

        # Get summary
        summary_row = await db_query_one(f"""
            SELECT
                app_name,
                app_id,
                COUNT(DISTINCT metric_date) as days_with_data,
                COUNT(DISTINCT creative_id) as creative_count,
                COUNT(DISTINCT country) as country_count,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                SUM(spend_micros) as total_spend_micros
            FROM rtb_daily
            WHERE {where_sql}
        """, tuple(params))

        if not summary_row or not summary_row["total_reached"]:
            return {
                "app_name": app_name,
                "has_data": False,
                "message": "No data found for this app"
            }

        total_reached = summary_row["total_reached"] or 0
        total_impressions = summary_row["total_impressions"] or 0
        win_rate = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        # Get breakdown by size/format
        size_rows = await db_query(f"""
            SELECT
                creative_size,
                creative_format,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_daily
            WHERE {where_sql}
            GROUP BY creative_size, creative_format
            ORDER BY reached DESC
        """, tuple(params))

        sizes = []
        for row in size_rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            size_win_rate = (imps / reached * 100) if reached > 0 else 0
            # Flag as wasteful if win rate is less than half of overall
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

        # Get breakdown by country
        country_rows = await db_query(f"""
            SELECT
                country,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_daily
            WHERE {where_sql}
            GROUP BY country
            ORDER BY reached DESC
        """, tuple(params))

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

        # Get breakdown by creative (top 10)
        creative_rows = await db_query(f"""
            SELECT
                creative_id,
                creative_size,
                creative_format,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_daily
            WHERE {where_sql}
            GROUP BY creative_id, creative_size, creative_format
            ORDER BY reached DESC
            LIMIT 10
        """, tuple(params))

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

        # Identify the main waste source
        wasteful_sizes = [s for s in sizes if s["is_wasteful"]]
        waste_insight = None
        if wasteful_sizes:
            worst = max(wasteful_sizes, key=lambda x: x["reached"])
            waste_insight = {
                "type": "size",
                "value": worst["size"],
                "message": f"{worst['size']} has only {worst['win_rate']}% win rate but accounts for {worst['pct_of_traffic']}% of traffic",
                "wasted_queries": int(worst["reached"] * (1 - worst["win_rate"] / 100)),
                "recommendation": f"Consider removing {worst['size']} from pretargeting for this app"
            }

        # Get bid filtering reasons for creatives used in this app
        # First get the creative IDs used in this app
        creative_ids = [c["creative_id"] for c in creatives]
        bid_filtering = []

        if creative_ids:
            # Check if bid_filtering table exists and has data
            try:
                table_check = await db_query_one("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='rtb_bid_filtering'
                """)

                if table_check:
                    # Query bid filtering reasons for these creatives
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
                            "pct_of_filtered": round(bids / total_filtered_bids * 100, 1) if total_filtered_bids > 0 else 0,
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
                "creative_count": summary_row["creative_count"],
                "country_count": summary_row["country_count"],
            },
            "by_size": sizes,
            "by_country": countries,
            "by_creative": creatives,
            "waste_insight": waste_insight,
            "bid_filtering": bid_filtering,
        }
    except Exception as e:
        logger.error(f"Failed to get app drilldown: {e}")
        raise HTTPException(status_code=500, detail=str(e))
