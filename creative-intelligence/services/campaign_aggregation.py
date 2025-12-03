"""Campaign Aggregation Service for Phase 11.1.

Provides timeframe-aware campaign metrics and waste detection.
Joins campaigns → creatives → rtb_daily to calculate:
- Aggregated spend, impressions, clicks
- Waste score: (reached_queries - impressions) / reached_queries * 100
- Warning counts: broken videos, zero engagement, etc.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class CampaignMetrics:
    """Aggregated metrics for a campaign within a timeframe."""
    total_spend_micros: int = 0
    total_impressions: int = 0
    total_clicks: int = 0
    total_reached_queries: int = 0
    avg_cpm: Optional[float] = None
    avg_ctr: Optional[float] = None
    waste_score: Optional[float] = None  # (reached - imps) / reached * 100


@dataclass
class CampaignWarnings:
    """Warning counts for a campaign."""
    broken_video_count: int = 0
    zero_engagement_count: int = 0
    high_spend_low_performance: int = 0
    disapproved_count: int = 0


@dataclass
class CampaignWithMetrics:
    """Campaign data with metrics and warnings."""
    id: str
    name: str
    creative_ids: list[str] = field(default_factory=list)
    creative_count: int = 0
    timeframe_days: int = 7
    metrics: Optional[CampaignMetrics] = None
    warnings: Optional[CampaignWarnings] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CampaignAggregationService:
    """
    Service for aggregating campaign performance with timeframe context.

    Implements Phase 11.1: Decision Context Foundation
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize with database path."""
        self.db_path = db_path or Path.home() / ".catscan" / "catscan.db"

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_campaigns_with_metrics(
        self,
        days: int = 7,
        include_empty: bool = True,
    ) -> list[CampaignWithMetrics]:
        """
        Get all campaigns with aggregated metrics for the given timeframe.

        Args:
            days: Number of days to aggregate (default 7)
            include_empty: Include campaigns with no activity in timeframe

        Returns:
            List of CampaignWithMetrics objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get all campaigns with their creative IDs
        cursor.execute("""
            SELECT c.id, c.name, c.created_at, c.updated_at
            FROM campaigns c
            ORDER BY c.updated_at DESC
        """)
        campaigns_raw = cursor.fetchall()

        results = []
        for camp_row in campaigns_raw:
            campaign_id = camp_row["id"]

            # Get creative IDs for this campaign
            cursor.execute(
                "SELECT creative_id FROM creative_campaigns WHERE campaign_id = ?",
                (campaign_id,)
            )
            creative_ids = [r["creative_id"] for r in cursor.fetchall()]

            # Get aggregated metrics from rtb_daily
            metrics = self._get_campaign_metrics(cursor, creative_ids, days)

            # Get warnings
            warnings = self._get_campaign_warnings(cursor, creative_ids, days)

            # Skip empty campaigns if requested
            if not include_empty and metrics.total_impressions == 0 and metrics.total_spend_micros == 0:
                continue

            results.append(CampaignWithMetrics(
                id=campaign_id,
                name=camp_row["name"],
                creative_ids=creative_ids,
                creative_count=len(creative_ids),
                timeframe_days=days,
                metrics=metrics,
                warnings=warnings,
                created_at=str(camp_row["created_at"]) if camp_row["created_at"] else None,
                updated_at=str(camp_row["updated_at"]) if camp_row["updated_at"] else None,
            ))

        conn.close()
        return results

    def get_campaign_with_metrics(
        self,
        campaign_id: str,
        days: int = 7,
    ) -> Optional[CampaignWithMetrics]:
        """
        Get a single campaign with metrics.

        Args:
            campaign_id: Campaign ID
            days: Number of days to aggregate

        Returns:
            CampaignWithMetrics or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, created_at, updated_at FROM campaigns WHERE id = ?",
            (campaign_id,)
        )
        camp_row = cursor.fetchone()

        if not camp_row:
            conn.close()
            return None

        # Get creative IDs
        cursor.execute(
            "SELECT creative_id FROM creative_campaigns WHERE campaign_id = ?",
            (campaign_id,)
        )
        creative_ids = [r["creative_id"] for r in cursor.fetchall()]

        # Get metrics and warnings
        metrics = self._get_campaign_metrics(cursor, creative_ids, days)
        warnings = self._get_campaign_warnings(cursor, creative_ids, days)

        conn.close()

        return CampaignWithMetrics(
            id=campaign_id,
            name=camp_row["name"],
            creative_ids=creative_ids,
            creative_count=len(creative_ids),
            timeframe_days=days,
            metrics=metrics,
            warnings=warnings,
            created_at=str(camp_row["created_at"]) if camp_row["created_at"] else None,
            updated_at=str(camp_row["updated_at"]) if camp_row["updated_at"] else None,
        )

    def _get_campaign_metrics(
        self,
        cursor: sqlite3.Cursor,
        creative_ids: list[str],
        days: int,
    ) -> CampaignMetrics:
        """Get aggregated metrics for creatives in timeframe."""
        if not creative_ids:
            return CampaignMetrics()

        placeholders = ",".join("?" * len(creative_ids))
        cursor.execute(f"""
            SELECT
                COALESCE(SUM(spend_micros), 0) as total_spend,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(reached_queries), 0) as total_reached
            FROM rtb_daily
            WHERE creative_id IN ({placeholders})
              AND metric_date >= date('now', '-{days} days')
        """, creative_ids)

        row = cursor.fetchone()

        total_spend = row["total_spend"] or 0
        total_impressions = row["total_impressions"] or 0
        total_clicks = row["total_clicks"] or 0
        total_reached = row["total_reached"] or 0

        # Calculate derived metrics
        avg_cpm = None
        if total_impressions > 0:
            avg_cpm = (total_spend / 1_000_000) / total_impressions * 1000

        avg_ctr = None
        if total_impressions > 0:
            avg_ctr = total_clicks / total_impressions * 100

        waste_score = None
        if total_reached > 0:
            waste_score = (total_reached - total_impressions) / total_reached * 100

        return CampaignMetrics(
            total_spend_micros=total_spend,
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_reached_queries=total_reached,
            avg_cpm=round(avg_cpm, 2) if avg_cpm else None,
            avg_ctr=round(avg_ctr, 4) if avg_ctr else None,
            waste_score=round(waste_score, 2) if waste_score else None,
        )

    def _get_campaign_warnings(
        self,
        cursor: sqlite3.Cursor,
        creative_ids: list[str],
        days: int,
    ) -> CampaignWarnings:
        """Get warning counts for creatives in campaign."""
        if not creative_ids:
            return CampaignWarnings()

        placeholders = ",".join("?" * len(creative_ids))

        # Broken video count (from thumbnail_status)
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM thumbnail_status ts
            JOIN creatives c ON ts.creative_id = c.id
            WHERE c.id IN ({placeholders})
              AND ts.status = 'failed'
              AND c.format = 'VIDEO'
        """, creative_ids)
        broken_video_count = cursor.fetchone()["count"] or 0

        # Zero engagement count (impressions > threshold but clicks = 0 over days)
        cursor.execute(f"""
            SELECT COUNT(DISTINCT creative_id) as count
            FROM (
                SELECT creative_id,
                       SUM(impressions) as total_imps,
                       SUM(clicks) as total_clicks,
                       COUNT(DISTINCT metric_date) as days_active
                FROM rtb_daily
                WHERE creative_id IN ({placeholders})
                  AND metric_date >= date('now', '-{days} days')
                GROUP BY creative_id
                HAVING total_imps > 1000 AND total_clicks = 0 AND days_active >= 3
            )
        """, creative_ids)
        zero_engagement_count = cursor.fetchone()["count"] or 0

        # High spend low performance (spend > $10 but CTR < 0.01%)
        cursor.execute(f"""
            SELECT COUNT(DISTINCT creative_id) as count
            FROM (
                SELECT creative_id,
                       SUM(spend_micros) as total_spend,
                       SUM(impressions) as total_imps,
                       SUM(clicks) as total_clicks
                FROM rtb_daily
                WHERE creative_id IN ({placeholders})
                  AND metric_date >= date('now', '-{days} days')
                GROUP BY creative_id
                HAVING total_spend > 10000000  -- $10
                   AND total_imps > 0
                   AND (CAST(total_clicks AS FLOAT) / total_imps) < 0.0001
            )
        """, creative_ids)
        high_spend_low_perf = cursor.fetchone()["count"] or 0

        # Disapproved creatives
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM creatives
            WHERE id IN ({placeholders})
              AND approval_status = 'DISAPPROVED'
        """, creative_ids)
        disapproved_count = cursor.fetchone()["count"] or 0

        return CampaignWarnings(
            broken_video_count=broken_video_count,
            zero_engagement_count=zero_engagement_count,
            high_spend_low_performance=high_spend_low_perf,
            disapproved_count=disapproved_count,
        )

    def get_unclustered_with_activity(
        self,
        days: int = 7,
    ) -> list[str]:
        """
        Get unclustered creative IDs that have activity in timeframe.

        Args:
            days: Number of days to check for activity

        Returns:
            List of creative IDs with recent activity
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT DISTINCT p.creative_id
            FROM rtb_daily p
            LEFT JOIN creative_campaigns cc ON p.creative_id = cc.creative_id
            WHERE cc.creative_id IS NULL
              AND p.metric_date >= date('now', '-{days} days')
              AND (p.impressions > 0 OR p.clicks > 0 OR p.spend_micros > 0)
            ORDER BY p.creative_id
        """)

        result = [row["creative_id"] for row in cursor.fetchall()]
        conn.close()
        return result
