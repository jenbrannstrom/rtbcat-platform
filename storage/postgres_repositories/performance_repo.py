"""Postgres repository for performance aggregates (SQL only)."""

from __future__ import annotations

from storage.postgres_database import pg_query_one


class PerformanceRepository:
    """SQL-only repository for performance aggregates."""

    async def get_performance_aggregates(self, billing_id: str) -> dict:
        perf = await pg_query_one(
            """
            SELECT
                COUNT(DISTINCT metric_date) as days_tracked,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(spend_micros), 0) / 1000000.0 as total_spend_usd
            FROM rtb_daily
            WHERE billing_id = %s
            """,
            (billing_id,),
        )

        if perf and perf["days_tracked"] > 0:
            return {
                "days_tracked": perf["days_tracked"],
                "total_impressions": perf["total_impressions"],
                "total_clicks": perf["total_clicks"],
                "total_spend_usd": perf["total_spend_usd"],
            }

        perf = await pg_query_one(
            """
            SELECT
                COUNT(DISTINCT metric_date) as days_tracked,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(spend_micros), 0) / 1000000.0 as total_spend_usd
            FROM performance_metrics
            WHERE billing_id = %s
            """,
            (billing_id,),
        )

        return {
            "days_tracked": perf["days_tracked"] if perf else 0,
            "total_impressions": perf["total_impressions"] if perf else 0,
            "total_clicks": perf["total_clicks"] if perf else 0,
            "total_spend_usd": perf["total_spend_usd"] if perf else 0,
        }
