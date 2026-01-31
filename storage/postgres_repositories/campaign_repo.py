"""Postgres repository for campaign queries (SQL only)."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


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

    # ==================== Campaign CRUD ====================

    async def create_campaign(
        self,
        name: str,
        seat_id: Optional[int] = None,
        description: Optional[str] = None,
        ai_generated: bool = True,
        ai_confidence: Optional[float] = None,
        clustering_method: Optional[str] = None,
    ) -> str:
        """Create a new AI campaign. Returns campaign ID."""
        campaign_id = str(uuid.uuid4())[:8]
        await pg_execute(
            """
            INSERT INTO ai_campaigns
            (id, seat_id, name, description, ai_generated, ai_confidence,
             clustering_method, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (campaign_id, seat_id, name, description, ai_generated, ai_confidence, clustering_method),
        )
        return campaign_id

    async def get_campaign(self, campaign_id: str) -> Optional[dict[str, Any]]:
        """Get a campaign by ID with creative count."""
        return await pg_query_one(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM creative_campaigns WHERE campaign_id = c.id) as computed_count
            FROM ai_campaigns c
            WHERE c.id = %s
            """,
            (campaign_id,),
        )

    async def list_campaigns(
        self,
        seat_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List campaigns with optional filtering."""
        conditions = []
        params: list[Any] = []

        if seat_id is not None:
            conditions.append("c.seat_id = %s")
            params.append(seat_id)
        if status:
            conditions.append("c.status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        params.extend([limit, offset])

        return await pg_query(
            f"""
            SELECT c.*,
                   (SELECT COUNT(*) FROM creative_campaigns WHERE campaign_id = c.id) as computed_count
            FROM ai_campaigns c
            WHERE {where_clause}
            ORDER BY c.updated_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )

    async def update_campaign(
        self,
        campaign_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bool:
        """Update campaign details. Returns True if updated."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []

        if name is not None:
            updates.append("name = %s")
            params.append(name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if status is not None:
            updates.append("status = %s")
            params.append(status)

        params.append(campaign_id)

        rowcount = await pg_execute(
            f"UPDATE ai_campaigns SET {', '.join(updates)} WHERE id = %s",
            tuple(params),
        )
        return rowcount > 0

    async def delete_campaign(self, campaign_id: str) -> bool:
        """Delete a campaign and its assignments. Returns True if deleted."""
        # Delete mappings first
        await pg_execute(
            "DELETE FROM creative_campaigns WHERE campaign_id = %s",
            (campaign_id,),
        )
        # Delete campaign
        rowcount = await pg_execute(
            "DELETE FROM ai_campaigns WHERE id = %s",
            (campaign_id,),
        )
        return rowcount > 0

    # ==================== Creative Assignment ====================

    async def assign_creative_to_campaign(
        self,
        creative_id: str,
        campaign_id: str,
        assigned_by: str = "ai",
        manually_assigned: bool = False,
    ) -> bool:
        """Assign a creative to a campaign. If already assigned, it will be moved."""
        rowcount = await pg_execute(
            """
            INSERT INTO creative_campaigns
            (creative_id, campaign_id, manually_assigned, assigned_at, assigned_by)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (creative_id) DO UPDATE SET
                campaign_id = EXCLUDED.campaign_id,
                manually_assigned = EXCLUDED.manually_assigned,
                assigned_at = EXCLUDED.assigned_at,
                assigned_by = EXCLUDED.assigned_by
            """,
            (creative_id, campaign_id, manually_assigned, assigned_by),
        )
        return rowcount > 0

    async def assign_creatives_batch(
        self,
        creative_ids: list[str],
        campaign_id: str,
        assigned_by: str = "ai",
        manually_assigned: bool = False,
    ) -> int:
        """Batch assign multiple creatives to a campaign. Returns count."""
        count = 0
        for creative_id in creative_ids:
            await pg_execute(
                """
                INSERT INTO creative_campaigns
                (creative_id, campaign_id, manually_assigned, assigned_at, assigned_by)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
                ON CONFLICT (creative_id) DO UPDATE SET
                    campaign_id = EXCLUDED.campaign_id,
                    manually_assigned = EXCLUDED.manually_assigned,
                    assigned_at = EXCLUDED.assigned_at,
                    assigned_by = EXCLUDED.assigned_by
                """,
                (creative_id, campaign_id, manually_assigned, assigned_by),
            )
            count += 1
        return count

    async def remove_creative_from_campaign(self, creative_id: str) -> bool:
        """Remove a creative from its campaign. Returns True if removed."""
        rowcount = await pg_execute(
            "DELETE FROM creative_campaigns WHERE creative_id = %s",
            (creative_id,),
        )
        return rowcount > 0

    async def get_campaign_creatives(self, campaign_id: str) -> list[str]:
        """Get all creative IDs in a campaign."""
        rows = await pg_query(
            "SELECT creative_id FROM creative_campaigns WHERE campaign_id = %s",
            (campaign_id,),
        )
        return [row["creative_id"] for row in rows]

    # ==================== Performance ====================

    async def get_campaign_country_breakdown(
        self, campaign_id: str, days: int = 7
    ) -> dict[str, dict[str, Any]]:
        """Get country breakdown for a campaign's creatives."""
        rows = await pg_query(
            """
            SELECT pm.creative_id, pm.geography,
                   SUM(pm.spend_micros) as spend_micros,
                   SUM(pm.impressions) as impressions
            FROM creative_campaigns cc
            JOIN performance_metrics pm ON cc.creative_id = pm.creative_id
            WHERE cc.campaign_id = %s
              AND pm.geography IS NOT NULL
              AND pm.metric_date >= CURRENT_DATE - make_interval(days => %s)
            GROUP BY pm.creative_id, pm.geography
            """,
            (campaign_id, days),
        )

        breakdown: dict[str, dict[str, Any]] = {}
        for row in rows:
            country = row["geography"]
            if country not in breakdown:
                breakdown[country] = {"creative_ids": [], "spend_micros": 0, "impressions": 0}
            breakdown[country]["creative_ids"].append(row["creative_id"])
            breakdown[country]["spend_micros"] += row["spend_micros"] or 0
            breakdown[country]["impressions"] += row["impressions"] or 0

        # De-duplicate creative_ids
        for country in breakdown:
            breakdown[country]["creative_ids"] = list(set(breakdown[country]["creative_ids"]))

        return breakdown

    async def get_campaign_performance(self, campaign_id: str, days: int = 7) -> dict[str, Any]:
        """Get aggregated performance for a campaign."""
        row = await pg_query_one(
            """
            SELECT
                SUM(total_impressions) as impressions,
                SUM(total_clicks) as clicks,
                SUM(total_spend) as spend,
                SUM(total_queries) as queries,
                AVG(avg_win_rate) as win_rate,
                AVG(avg_ctr) as ctr,
                AVG(avg_cpm) as cpm
            FROM campaign_daily_summary
            WHERE campaign_id = %s
              AND date >= CURRENT_DATE - make_interval(days => %s)
            """,
            (campaign_id, days),
        )

        if row:
            return {
                "impressions": row["impressions"] or 0,
                "clicks": row["clicks"] or 0,
                "spend": row["spend"] or 0,
                "queries": row["queries"] or 0,
                "win_rate": row["win_rate"],
                "ctr": row["ctr"],
                "cpm": row["cpm"],
            }

        return {
            "impressions": 0,
            "clicks": 0,
            "spend": 0,
            "queries": 0,
            "win_rate": None,
            "ctr": None,
            "cpm": None,
        }

    async def get_campaign_daily_trend(self, campaign_id: str, days: int = 30) -> list[dict[str, Any]]:
        """Get daily performance trend for a campaign."""
        rows = await pg_query(
            """
            SELECT date, total_impressions, total_clicks, total_spend,
                   avg_win_rate, avg_ctr, avg_cpm, unique_geos
            FROM campaign_daily_summary
            WHERE campaign_id = %s
              AND date >= CURRENT_DATE - make_interval(days => %s)
            ORDER BY date DESC
            """,
            (campaign_id, days),
        )
        return [dict(row) for row in rows]

    async def update_campaign_summary(self, campaign_id: str, date: str) -> None:
        """Recalculate and store campaign daily summary from performance_metrics."""
        row = await pg_query_one(
            """
            SELECT
                COUNT(DISTINCT pm.creative_id) as total_creatives,
                COUNT(DISTINCT CASE WHEN pm.impressions > 0 THEN pm.creative_id END) as active_creatives,
                COALESCE(SUM(pm.reached_queries), 0) as total_queries,
                COALESCE(SUM(pm.impressions), 0) as total_impressions,
                COALESCE(SUM(pm.clicks), 0) as total_clicks,
                COALESCE(SUM(pm.spend_micros), 0) / 1000000.0 as total_spend,
                COUNT(DISTINCT pm.geography) as unique_geos
            FROM performance_metrics pm
            JOIN creative_campaigns cc ON pm.creative_id = cc.creative_id
            WHERE cc.campaign_id = %s AND pm.metric_date = %s
            """,
            (campaign_id, date),
        )

        if row:
            total_impressions = row["total_impressions"] or 0
            total_clicks = row["total_clicks"] or 0
            total_queries = row["total_queries"] or 0

            avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else None
            avg_win_rate = (total_impressions / total_queries * 100) if total_queries > 0 else None
            avg_cpm = (row["total_spend"] / total_impressions * 1000) if total_impressions > 0 else None

            await pg_execute(
                """
                INSERT INTO campaign_daily_summary
                (campaign_id, date, total_creatives, active_creatives,
                 total_queries, total_impressions, total_clicks, total_spend,
                 avg_win_rate, avg_ctr, avg_cpm, unique_geos)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (campaign_id, date) DO UPDATE SET
                    total_creatives = EXCLUDED.total_creatives,
                    active_creatives = EXCLUDED.active_creatives,
                    total_queries = EXCLUDED.total_queries,
                    total_impressions = EXCLUDED.total_impressions,
                    total_clicks = EXCLUDED.total_clicks,
                    total_spend = EXCLUDED.total_spend,
                    avg_win_rate = EXCLUDED.avg_win_rate,
                    avg_ctr = EXCLUDED.avg_ctr,
                    avg_cpm = EXCLUDED.avg_cpm,
                    unique_geos = EXCLUDED.unique_geos
                """,
                (
                    campaign_id,
                    date,
                    row["total_creatives"] or 0,
                    row["active_creatives"] or 0,
                    total_queries,
                    total_impressions,
                    total_clicks,
                    row["total_spend"] or 0,
                    avg_win_rate,
                    avg_ctr,
                    avg_cpm,
                    row["unique_geos"] or 0,
                ),
            )

    async def count_disapproved_in_list(self, creative_ids: list[str]) -> int:
        """Count creatives in list that are disapproved or have restrictions."""
        if not creative_ids:
            return 0
        row = await pg_query_one(
            """
            SELECT COUNT(*) as count
            FROM creatives
            WHERE id = ANY(%s)
              AND (approval_status = 'DISAPPROVED'
                   OR disapproval_reasons IS NOT NULL
                   OR serving_restrictions IS NOT NULL)
            """,
            (creative_ids,),
        )
        return row["count"] if row else 0

    async def get_distinct_metric_dates(self, limit: int = 30) -> list[str]:
        """Get distinct metric dates for summary refresh."""
        rows = await pg_query(
            """
            SELECT DISTINCT metric_date FROM performance_metrics
            ORDER BY metric_date DESC LIMIT %s
            """,
            (limit,),
        )
        return [str(row["metric_date"]) for row in rows]

    # ==================== Unclustered Creatives ====================

    async def get_unclustered_creatives(
        self, buyer_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get unclustered creatives with app/URL info for auto-clustering."""
        if buyer_id:
            return await pg_query(
                """
                SELECT c.id as creative_id, c.final_url, c.buyer_id,
                       c.app_id, c.app_name, c.app_store, c.advertiser_name
                FROM creatives c
                LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                WHERE cc.creative_id IS NULL
                  AND c.buyer_id = %s
                ORDER BY c.id
                """,
                (buyer_id,),
            )
        return await pg_query(
            """
            SELECT c.id as creative_id, c.final_url, c.buyer_id,
                   c.app_id, c.app_name, c.app_store, c.advertiser_name
            FROM creatives c
            LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
            WHERE cc.creative_id IS NULL
            ORDER BY c.id
            """
        )

    async def get_unclustered_creative_ids(
        self, buyer_id: Optional[str] = None
    ) -> list[str]:
        """Get IDs of unclustered creatives."""
        if buyer_id:
            rows = await pg_query(
                """
                SELECT c.id as creative_id
                FROM creatives c
                LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                WHERE cc.creative_id IS NULL
                  AND c.buyer_id = %s
                ORDER BY c.id
                """,
                (buyer_id,),
            )
        else:
            rows = await pg_query(
                """
                SELECT c.id as creative_id
                FROM creatives c
                LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                WHERE cc.creative_id IS NULL
                ORDER BY c.id
                """
            )
        return [str(row["creative_id"]) for row in rows]

    async def get_creative_countries(
        self, creative_ids: list[str], days: int = 30
    ) -> dict[str, str]:
        """Get primary country (by spend) for each creative."""
        if not creative_ids:
            return {}

        rows = await pg_query(
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

        return {row["creative_id"]: row["geography"] for row in rows}
