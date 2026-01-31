"""Postgres repository for creative performance queries."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_query


class CreativePerformanceRepository:
    """SQL-only repository for creative performance lookups."""

    async def get_rtb_daily_perf(
        self, creative_ids: list[str], days: int
    ) -> list[dict[str, Any]]:
        if not creative_ids:
            return []
        return await pg_query(
            """
            SELECT creative_id,
                   SUM(impressions) as total_impressions,
                   SUM(clicks) as total_clicks
            FROM rtb_daily
            WHERE creative_id = ANY(%s)
              AND metric_date >= CURRENT_DATE - make_interval(days => %s)
            GROUP BY creative_id
            """,
            (creative_ids, days),
        )

    async def get_active_creative_ids(
        self, creative_ids: list[str], days: int
    ) -> list[str]:
        if not creative_ids:
            return []
        rows = await pg_query(
            """
            SELECT DISTINCT creative_id
            FROM rtb_daily
            WHERE creative_id = ANY(%s)
              AND metric_date >= CURRENT_DATE - make_interval(days => %s)
              AND (impressions > 0 OR clicks > 0 OR spend_micros > 0)
            """,
            (creative_ids, days),
        )
        return [row["creative_id"] for row in rows]

    async def get_primary_countries(
        self, creative_ids: list[str], days: int
    ) -> list[dict[str, Any]]:
        if not creative_ids:
            return []
        return await pg_query(
            """
            WITH ranked AS (
                SELECT creative_id, geography,
                       SUM(spend_micros) as total_spend,
                       ROW_NUMBER() OVER (
                           PARTITION BY creative_id
                           ORDER BY SUM(spend_micros) DESC
                       ) as rn
                FROM performance_metrics
                WHERE creative_id = ANY(%s)
                  AND geography IS NOT NULL
                  AND metric_date >= CURRENT_DATE - make_interval(days => %s)
                GROUP BY creative_id, geography
            )
            SELECT creative_id, geography
            FROM ranked
            WHERE rn = 1
            """,
            (creative_ids, days),
        )

    async def get_country_breakdown(
        self, creative_id: str, days: int
    ) -> list[dict[str, Any]]:
        return await pg_query(
            """
            SELECT
                country as country_code,
                SUM(spend_micros) as spend_micros,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks
            FROM rtb_daily
            WHERE creative_id = %s
              AND country IS NOT NULL
              AND country != ''
              AND metric_date >= CURRENT_DATE - make_interval(days => %s)
            GROUP BY country
            ORDER BY spend_micros DESC
            """,
            (creative_id, days),
        )
