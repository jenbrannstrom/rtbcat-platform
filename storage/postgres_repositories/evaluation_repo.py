"""Postgres repository for evaluation queries (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_query, pg_query_one


class EvaluationRepository:
    """SQL-only repository for evaluation data access."""

    async def get_rtb_daily_count(self, days: int) -> int:
        """Count rtb_daily rows in timeframe."""
        row = await pg_query_one(
            """
            SELECT COUNT(*) as cnt FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - make_interval(days => %s)
            """,
            (days,),
        )
        return row["cnt"] if row else 0

    async def get_troubleshooting_count(self, days: int) -> int:
        """Count troubleshooting_data rows in timeframe."""
        row = await pg_query_one(
            """
            SELECT COUNT(*) as cnt FROM troubleshooting_data
            WHERE collection_date >= CURRENT_DATE - make_interval(days => %s)
            """,
            (days,),
        )
        return row["cnt"] if row else 0

    async def get_creatives_count(self) -> int:
        """Count total creatives."""
        row = await pg_query_one("SELECT COUNT(*) as cnt FROM creatives")
        return row["cnt"] if row else 0

    async def get_filtered_bids_summary(self, days: int) -> list[dict[str, Any]]:
        """Get filtered bids grouped by status."""
        return await pg_query(
            """
            SELECT
                status_name,
                SUM(bid_count) as total_bids,
                SUM(impression_count) as total_impressions,
                ROUND(100.0 * SUM(bid_count) /
                    NULLIF((SELECT SUM(bid_count) FROM troubleshooting_data
                     WHERE metric_type = 'filtered_bids'
                     AND collection_date >= CURRENT_DATE - make_interval(days => %s)), 0), 2) as pct_of_filtered
            FROM troubleshooting_data
            WHERE metric_type = 'filtered_bids'
              AND collection_date >= CURRENT_DATE - make_interval(days => %s)
            GROUP BY status_name
            ORDER BY total_bids DESC
            """,
            (days, days),
        )

    async def get_size_traffic(self, days: int) -> list[dict[str, Any]]:
        """Get traffic by creative size."""
        return await pg_query(
            """
            SELECT creative_size,
                   SUM(reached_queries) as reached_queries,
                   SUM(impressions) as impressions
            FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - make_interval(days => %s)
              AND creative_size IS NOT NULL
            GROUP BY creative_size
            HAVING SUM(reached_queries) > 1000
            ORDER BY SUM(reached_queries) DESC
            """,
            (days,),
        )

    async def get_creative_sizes(self) -> set[str]:
        """Get all distinct creative sizes."""
        rows = await pg_query(
            "SELECT DISTINCT canonical_size FROM creatives WHERE canonical_size IS NOT NULL"
        )
        return {row["canonical_size"] for row in rows}

    async def get_geo_waste(self, days: int) -> list[dict[str, Any]]:
        """Get geographic waste data."""
        return await pg_query(
            """
            SELECT country,
                   SUM(reached_queries) as reached_queries,
                   SUM(impressions) as impressions,
                   ROUND(100.0 * (SUM(reached_queries) - SUM(impressions)) /
                         NULLIF(SUM(reached_queries), 0), 2) as waste_pct
            FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - make_interval(days => %s)
              AND country IS NOT NULL
            GROUP BY country
            HAVING SUM(reached_queries) > 10000
            ORDER BY waste_pct DESC
            """,
            (days,),
        )

    async def get_suspicious_publishers(self, days: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get publishers with high impressions but zero clicks."""
        return await pg_query(
            """
            SELECT publisher_id, publisher_name,
                   SUM(impressions) as impressions,
                   SUM(clicks) as clicks,
                   'high_traffic_zero_clicks' as signal_type
            FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - make_interval(days => %s)
              AND publisher_id IS NOT NULL
            GROUP BY publisher_id, publisher_name
            HAVING SUM(impressions) > 10000 AND SUM(clicks) = 0
            ORDER BY SUM(impressions) DESC
            LIMIT %s
            """,
            (days, limit),
        )

    async def get_high_win_rate_sizes(self, days: int, limit: int = 5) -> list[dict[str, Any]]:
        """Get sizes with high win rate but low volume."""
        return await pg_query(
            """
            SELECT creative_size,
                   SUM(reached_queries) as queries,
                   SUM(impressions) as impressions,
                   ROUND(100.0 * SUM(impressions) / NULLIF(SUM(reached_queries), 0), 2) as win_rate
            FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - make_interval(days => %s)
              AND creative_size IS NOT NULL
            GROUP BY creative_size
            HAVING SUM(reached_queries) > 1000 AND
                   ROUND(100.0 * SUM(impressions) / NULLIF(SUM(reached_queries), 0), 2) > 20
            ORDER BY win_rate DESC
            LIMIT %s
            """,
            (days, limit),
        )

    async def get_bid_metrics_raw(self, days: int) -> list[dict[str, Any]]:
        """Get raw bid metrics data for funnel calculation."""
        return await pg_query(
            """
            SELECT raw_data
            FROM troubleshooting_data
            WHERE metric_type = 'bid_metrics'
              AND collection_date >= CURRENT_DATE - make_interval(days => %s)
            """,
            (days,),
        )
