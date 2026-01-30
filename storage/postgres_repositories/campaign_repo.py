"""Postgres repository for campaign queries (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_query, pg_query_one


class CampaignRepository:
    """SQL-only repository for campaign data access."""

    async def get_all_campaigns(self) -> list[dict[str, Any]]:
        """Get all campaigns ordered by updated_at."""
        return await pg_query(
            """
            SELECT c.id, c.name, c.created_at, c.updated_at
            FROM campaigns c
            ORDER BY c.updated_at DESC
            """
        )

    async def get_campaign_by_id(self, campaign_id: str) -> dict[str, Any] | None:
        """Get a single campaign by ID."""
        return await pg_query_one(
            "SELECT id, name, created_at, updated_at FROM campaigns WHERE id = %s",
            (campaign_id,),
        )

    async def get_creative_ids_for_campaign(self, campaign_id: str) -> list[str]:
        """Get creative IDs linked to a campaign."""
        rows = await pg_query(
            "SELECT creative_id FROM creative_campaigns WHERE campaign_id = %s",
            (campaign_id,),
        )
        return [r["creative_id"] for r in rows]

    async def get_campaign_metrics(
        self, creative_ids: list[str], days: int
    ) -> dict[str, Any]:
        """Get aggregated metrics for creatives in timeframe."""
        if not creative_ids:
            return {
                "total_spend": 0,
                "total_impressions": 0,
                "total_clicks": 0,
                "total_reached": 0,
            }

        row = await pg_query_one(
            """
            SELECT
                COALESCE(SUM(spend_micros), 0) as total_spend,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(reached_queries), 0) as total_reached
            FROM rtb_daily
            WHERE creative_id = ANY(%s)
              AND metric_date >= CURRENT_DATE - make_interval(days => %s)
            """,
            (creative_ids, days),
        )
        return row or {
            "total_spend": 0,
            "total_impressions": 0,
            "total_clicks": 0,
            "total_reached": 0,
        }

    async def get_broken_video_count(self, creative_ids: list[str]) -> int:
        """Count broken video creatives."""
        if not creative_ids:
            return 0
        row = await pg_query_one(
            """
            SELECT COUNT(*) as count
            FROM thumbnail_status ts
            JOIN creatives c ON ts.creative_id = c.id
            WHERE c.id = ANY(%s)
              AND ts.status = 'failed'
              AND c.format = 'VIDEO'
            """,
            (creative_ids,),
        )
        return row["count"] if row else 0

    async def get_zero_engagement_count(
        self, creative_ids: list[str], days: int
    ) -> int:
        """Count creatives with zero engagement."""
        if not creative_ids:
            return 0
        row = await pg_query_one(
            """
            SELECT COUNT(DISTINCT creative_id) as count
            FROM (
                SELECT creative_id,
                       SUM(impressions) as total_imps,
                       SUM(clicks) as total_clicks,
                       COUNT(DISTINCT metric_date) as days_active
                FROM rtb_daily
                WHERE creative_id = ANY(%s)
                  AND metric_date >= CURRENT_DATE - make_interval(days => %s)
                GROUP BY creative_id
                HAVING SUM(impressions) > 1000 AND SUM(clicks) = 0 AND COUNT(DISTINCT metric_date) >= 3
            ) sub
            """,
            (creative_ids, days),
        )
        return row["count"] if row else 0

    async def get_high_spend_low_perf_count(
        self, creative_ids: list[str], days: int
    ) -> int:
        """Count high spend low performance creatives."""
        if not creative_ids:
            return 0
        row = await pg_query_one(
            """
            SELECT COUNT(DISTINCT creative_id) as count
            FROM (
                SELECT creative_id,
                       SUM(spend_micros) as total_spend,
                       SUM(impressions) as total_imps,
                       SUM(clicks) as total_clicks
                FROM rtb_daily
                WHERE creative_id = ANY(%s)
                  AND metric_date >= CURRENT_DATE - make_interval(days => %s)
                GROUP BY creative_id
                HAVING SUM(spend_micros) > 10000000
                   AND SUM(impressions) > 0
                   AND (CAST(SUM(clicks) AS FLOAT) / SUM(impressions)) < 0.0001
            ) sub
            """,
            (creative_ids, days),
        )
        return row["count"] if row else 0

    async def get_disapproved_count(self, creative_ids: list[str]) -> int:
        """Count disapproved creatives."""
        if not creative_ids:
            return 0
        row = await pg_query_one(
            """
            SELECT COUNT(*) as count
            FROM creatives
            WHERE id = ANY(%s)
              AND approval_status = 'DISAPPROVED'
            """,
            (creative_ids,),
        )
        return row["count"] if row else 0

    async def get_unclustered_with_activity(self, days: int) -> list[str]:
        """Get unclustered creative IDs that have activity in timeframe."""
        rows = await pg_query(
            """
            SELECT DISTINCT p.creative_id
            FROM rtb_daily p
            LEFT JOIN creative_campaigns cc ON p.creative_id = cc.creative_id
            WHERE cc.creative_id IS NULL
              AND p.metric_date >= CURRENT_DATE - make_interval(days => %s)
              AND (p.impressions > 0 OR p.clicks > 0 OR p.spend_micros > 0)
            ORDER BY p.creative_id
            """,
            (days,),
        )
        return [row["creative_id"] for row in rows]
