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

    async def get_creative_summaries(
        self,
        creative_ids: list[str],
        days: int = 30,
        buyer_id_filter: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Get performance summaries for multiple creatives from rtb_daily.

        Returns a dict keyed by creative_id with aggregated metrics
        including clicks, impressions, spend, and derived metrics.
        Buyer scoping is applied when buyer_id_filter is provided.
        """
        if not creative_ids:
            return {}

        params: list[Any] = [creative_ids, days]
        buyer_clause = ""
        if buyer_id_filter:
            buyer_clause = "AND buyer_account_id = %s"
            params.append(buyer_id_filter)

        rows = await pg_query(
            f"""
            SELECT
                creative_id,
                COALESCE(SUM(impressions), 0) AS total_impressions,
                COALESCE(SUM(clicks), 0) AS total_clicks,
                COALESCE(SUM(spend_micros), 0) AS total_spend_micros,
                COUNT(DISTINCT metric_date) AS days_with_data,
                MIN(metric_date) AS earliest_date,
                MAX(metric_date) AS latest_date
            FROM rtb_daily
            WHERE creative_id = ANY(%s)
              AND metric_date >= CURRENT_DATE - make_interval(days => %s)
              {buyer_clause}
            GROUP BY creative_id
            """,
            tuple(params),
        )

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            cid = row["creative_id"]
            imps = int(row["total_impressions"])
            clicks = int(row["total_clicks"])
            spend = int(row["total_spend_micros"])

            avg_cpm = int((spend / imps) * 1000) if imps > 0 and spend > 0 else None
            avg_cpc = int(spend / clicks) if clicks > 0 else None
            ctr = round((clicks / imps) * 100, 4) if imps > 0 else None

            result[cid] = {
                "total_impressions": imps,
                "total_clicks": clicks,
                "total_spend_micros": spend,
                "avg_cpm_micros": avg_cpm,
                "avg_cpc_micros": avg_cpc,
                "ctr_percent": ctr,
                "days_with_data": int(row["days_with_data"]),
                "earliest_date": str(row["earliest_date"]) if row["earliest_date"] else None,
                "latest_date": str(row["latest_date"]) if row["latest_date"] else None,
                "metric_source": "rtb_daily",
                "clicks_available": True,
            }
        return result

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
