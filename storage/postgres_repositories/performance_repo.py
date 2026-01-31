"""Postgres repository for performance aggregates (SQL only)."""

from __future__ import annotations

from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


class PerformanceRepository:
    """SQL-only repository for performance aggregates."""

    async def upsert_performance_metric(
        self,
        creative_id: str,
        metric_date: str,
        impressions: int,
        clicks: int,
        spend_micros: int,
        reached_queries: int = 0,
        campaign_id: Optional[str] = None,
        geography: Optional[str] = None,
        device_type: Optional[str] = None,
        placement: Optional[str] = None,
    ) -> None:
        """Upsert a single performance metric row."""
        await pg_execute("""
            INSERT INTO performance_metrics (
                creative_id, campaign_id, metric_date,
                impressions, clicks, spend_micros,
                geography, device_type, placement, reached_queries
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (creative_id, metric_date, geography, device_type, placement)
            DO UPDATE SET
                impressions = performance_metrics.impressions + EXCLUDED.impressions,
                clicks = performance_metrics.clicks + EXCLUDED.clicks,
                spend_micros = performance_metrics.spend_micros + EXCLUDED.spend_micros,
                reached_queries = performance_metrics.reached_queries + EXCLUDED.reached_queries
        """, (
            creative_id,
            campaign_id,
            metric_date,
            impressions,
            clicks,
            spend_micros,
            geography,
            device_type,
            placement,
            reached_queries,
        ))

    async def get_performance_aggregates(self, billing_id: str) -> dict:
        """Get performance aggregates for a billing ID from rtb_daily.

        Returns zeros if no data found (fallback to performance_metrics removed
        as that table lacks billing_id column).
        """
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

        return {
            "days_tracked": perf["days_tracked"] if perf else 0,
            "total_impressions": perf["total_impressions"] if perf else 0,
            "total_clicks": perf["total_clicks"] if perf else 0,
            "total_spend_usd": perf["total_spend_usd"] if perf else 0,
        }

    async def get_creative_buyer_ids(
        self, creative_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Get creative IDs and their buyer_ids for access validation."""
        if not creative_ids:
            return []
        return await pg_query(
            "SELECT id, buyer_id FROM creatives WHERE id = ANY(%s)",
            (creative_ids,),
        )
