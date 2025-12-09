"""
Campaign Repository for AI-generated campaign clustering.

Handles CRUD operations for campaigns, creative_campaigns,
and campaign_daily_summary tables.
"""

import sqlite3
import uuid
from typing import Optional, Union
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AICampaign:
    """AI-generated campaign record."""
    id: Optional[str] = None
    seat_id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    ai_generated: bool = True
    ai_confidence: Optional[float] = None
    clustering_method: Optional[str] = None
    status: str = "active"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    creative_count: int = 0  # Computed field


@dataclass
class CreativeCampaignMapping:
    """Creative to campaign assignment."""
    id: Optional[int] = None
    creative_id: str = ""
    campaign_id: str = ""
    manually_assigned: bool = False
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None


@dataclass
class CampaignPerformance:
    """Campaign daily performance summary."""
    campaign_id: str = ""
    date: str = ""
    total_creatives: int = 0
    active_creatives: int = 0
    total_queries: int = 0
    total_impressions: int = 0
    total_clicks: int = 0
    total_spend: float = 0.0
    total_video_starts: Optional[int] = None
    total_video_completions: Optional[int] = None
    avg_win_rate: Optional[float] = None
    avg_ctr: Optional[float] = None
    avg_cpm: Optional[float] = None
    unique_geos: int = 0
    top_geo_id: Optional[int] = None
    top_geo_spend: Optional[float] = None


class CampaignRepository:
    """
    Repository for AI campaign management.

    Handles campaign CRUD, creative assignments, and performance aggregation.
    """

    def __init__(self, db_connection: sqlite3.Connection):
        """
        Initialize repository with database connection.

        Args:
            db_connection: SQLite database connection
        """
        self.db = db_connection
        self.db.row_factory = sqlite3.Row

    # ==================== Campaign CRUD ====================

    def create_campaign(
        self,
        name: str,
        seat_id: Optional[int] = None,
        description: Optional[str] = None,
        ai_generated: bool = True,
        ai_confidence: Optional[float] = None,
        clustering_method: Optional[str] = None,
    ) -> str:
        """
        Create a new AI campaign.

        Args:
            name: Campaign name
            seat_id: Associated seat ID
            description: Campaign description
            ai_generated: Whether AI generated this campaign
            ai_confidence: AI confidence score (0-1)
            clustering_method: Clustering method used (domain, url, ai, manual)

        Returns:
            New campaign ID (string UUID)
        """
        # Generate a unique text ID
        campaign_id = str(uuid.uuid4())[:8]  # Short UUID for readability

        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO campaigns
            (id, seat_id, name, description, ai_generated, ai_confidence,
             clustering_method, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (campaign_id, seat_id, name, description, ai_generated, ai_confidence, clustering_method))

        self.db.commit()
        return campaign_id

    def get_campaign(self, campaign_id: Union[str, int]) -> Optional[AICampaign]:
        """
        Get a campaign by ID with creative count.

        Args:
            campaign_id: Campaign ID (string or int)

        Returns:
            AICampaign object or None
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT c.*,
                   (SELECT COUNT(*) FROM creative_campaigns WHERE campaign_id = c.id) as computed_count
            FROM campaigns c
            WHERE c.id = ?
        """, (str(campaign_id),))
        row = cursor.fetchone()

        if row:
            return self._row_to_campaign(row)
        return None

    def list_campaigns(
        self,
        seat_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AICampaign]:
        """
        List campaigns with optional filtering.

        Args:
            seat_id: Filter by seat
            status: Filter by status (active, paused, archived)
            limit: Max results
            offset: Skip results

        Returns:
            List of AICampaign objects
        """
        conditions = []
        params = []

        if seat_id is not None:
            conditions.append("c.seat_id = ?")
            params.append(seat_id)

        if status:
            conditions.append("c.status = ?")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        cursor = self.db.cursor()
        cursor.execute(f"""
            SELECT c.*,
                   (SELECT COUNT(*) FROM creative_campaigns WHERE campaign_id = c.id) as computed_count
            FROM campaigns c
            WHERE {where_clause}
            ORDER BY c.updated_at DESC
            LIMIT ? OFFSET ?
        """, params)

        return [self._row_to_campaign(row) for row in cursor.fetchall()]

    def update_campaign(
        self,
        campaign_id: Union[str, int],
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bool:
        """
        Update campaign details.

        Args:
            campaign_id: Campaign ID
            name: New name (or None to keep)
            description: New description (or None to keep)
            status: New status (or None to keep)

        Returns:
            True if updated
        """
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        params.append(campaign_id)

        cursor = self.db.cursor()
        cursor.execute(
            f"UPDATE campaigns SET {', '.join(updates)} WHERE id = ?",
            params
        )
        self.db.commit()

        return cursor.rowcount > 0

    def delete_campaign(self, campaign_id: int) -> bool:
        """
        Delete a campaign and its assignments.

        Args:
            campaign_id: Campaign ID

        Returns:
            True if deleted
        """
        cursor = self.db.cursor()

        # Delete mappings first
        cursor.execute(
            "DELETE FROM creative_campaigns WHERE campaign_id = ?",
            (campaign_id,)
        )

        # Delete campaign
        cursor.execute(
            "DELETE FROM campaigns WHERE id = ?",
            (campaign_id,)
        )

        self.db.commit()
        return cursor.rowcount > 0

    # ==================== Creative Assignment ====================

    def assign_creative_to_campaign(
        self,
        creative_id: str,
        campaign_id: Union[str, int],
        assigned_by: str = "ai",
        manually_assigned: bool = False,
    ) -> bool:
        """
        Assign a creative to a campaign.

        If the creative is already assigned, it will be moved.

        Args:
            creative_id: Creative ID
            campaign_id: Target campaign ID
            assigned_by: Who assigned (ai, user, rule)
            manually_assigned: Whether manually assigned

        Returns:
            True if assigned
        """
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO creative_campaigns
            (creative_id, campaign_id, manually_assigned, assigned_at, assigned_by)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (creative_id, campaign_id, manually_assigned, assigned_by))

        self.db.commit()
        return cursor.rowcount > 0

    def assign_creatives_batch(
        self,
        creative_ids: list[str],
        campaign_id: Union[str, int],
        assigned_by: str = "ai",
        manually_assigned: bool = False,
    ) -> int:
        """
        Batch assign multiple creatives to a campaign.

        Args:
            creative_ids: List of creative IDs
            campaign_id: Target campaign ID
            assigned_by: Who assigned
            manually_assigned: Whether manually assigned

        Returns:
            Number of assignments made
        """
        cursor = self.db.cursor()
        count = 0

        for creative_id in creative_ids:
            cursor.execute("""
                INSERT OR REPLACE INTO creative_campaigns
                (creative_id, campaign_id, manually_assigned, assigned_at, assigned_by)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (creative_id, campaign_id, manually_assigned, assigned_by))
            count += 1

        self.db.commit()
        return count

    def remove_creative_from_campaign(self, creative_id: str) -> bool:
        """
        Remove a creative from its campaign.

        Args:
            creative_id: Creative ID

        Returns:
            True if removed
        """
        cursor = self.db.cursor()
        cursor.execute(
            "DELETE FROM creative_campaigns WHERE creative_id = ?",
            (creative_id,)
        )
        self.db.commit()
        return cursor.rowcount > 0

    def get_campaign_creatives(self, campaign_id: int) -> list[str]:
        """
        Get all creative IDs in a campaign.

        Args:
            campaign_id: Campaign ID

        Returns:
            List of creative IDs
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT creative_id FROM creative_campaigns WHERE campaign_id = ?",
            (campaign_id,)
        )
        return [row['creative_id'] for row in cursor.fetchall()]

    def get_campaign_country_breakdown(
        self, campaign_id: Union[str, int], days: int = 7
    ) -> dict[str, dict]:
        """
        Get country breakdown for a campaign's creatives.

        Args:
            campaign_id: Campaign ID
            days: Timeframe for performance data

        Returns:
            Dict mapping country to {creative_ids, spend_micros, impressions}
        """
        cursor = self.db.cursor()

        # Get creatives in this campaign with their performance by country
        cursor.execute("""
            SELECT pm.creative_id, pm.geography,
                   SUM(pm.spend_micros) as spend_micros,
                   SUM(pm.impressions) as impressions
            FROM creative_campaigns cc
            JOIN performance_metrics pm ON cc.creative_id = pm.creative_id
            WHERE cc.campaign_id = ?
              AND pm.geography IS NOT NULL
              AND pm.metric_date >= date('now', ? || ' days')
            GROUP BY pm.creative_id, pm.geography
        """, (campaign_id, f"-{days}"))

        # Build breakdown
        breakdown: dict[str, dict] = {}
        for row in cursor.fetchall():
            country = row['geography']
            if country not in breakdown:
                breakdown[country] = {
                    'creative_ids': [],
                    'spend_micros': 0,
                    'impressions': 0
                }
            breakdown[country]['creative_ids'].append(row['creative_id'])
            breakdown[country]['spend_micros'] += row['spend_micros'] or 0
            breakdown[country]['impressions'] += row['impressions'] or 0

        # De-duplicate creative_ids (a creative may appear multiple times)
        for country in breakdown:
            breakdown[country]['creative_ids'] = list(set(breakdown[country]['creative_ids']))

        return breakdown

    def get_creative_campaign(self, creative_id: str) -> Optional[int]:
        """
        Get the campaign ID for a creative.

        Args:
            creative_id: Creative ID

        Returns:
            Campaign ID or None
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT campaign_id FROM creative_campaigns WHERE creative_id = ?",
            (creative_id,)
        )
        row = cursor.fetchone()
        return row['campaign_id'] if row else None

    def get_uncategorized_creatives(self, seat_id: Optional[int] = None) -> list[dict]:
        """
        Get creatives not assigned to any campaign.

        Args:
            seat_id: Optional seat filter

        Returns:
            List of creative dicts
        """
        cursor = self.db.cursor()

        # Join with creatives table to get full data
        query = """
            SELECT c.id, c.name, c.format, c.final_url, c.display_url,
                   c.advertiser_name, c.created_at
            FROM creatives c
            LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
            WHERE cc.creative_id IS NULL
        """

        cursor.execute(query)

        return [
            {
                'id': row['id'],
                'name': row['name'],
                'format': row['format'],
                'final_url': row['final_url'],
                'detected_url': row['display_url'],
                'advertiser_name': row['advertiser_name'],
                'created_at': row['created_at'],
            }
            for row in cursor.fetchall()
        ]

    # ==================== Performance Summary ====================

    def update_campaign_summary(
        self,
        campaign_id: Union[str, int],
        date: str,
    ) -> None:
        """
        Recalculate and store campaign daily summary from performance_metrics.

        Args:
            campaign_id: Campaign ID
            date: Date string (YYYY-MM-DD)
        """
        cursor = self.db.cursor()

        # Get aggregated metrics for this campaign and date
        cursor.execute("""
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
            WHERE cc.campaign_id = ? AND pm.metric_date = ?
        """, (campaign_id, date))

        row = cursor.fetchone()

        if row:
            total_impressions = row['total_impressions'] or 0
            total_clicks = row['total_clicks'] or 0
            total_queries = row['total_queries'] or 0

            # Calculate rates
            avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else None
            avg_win_rate = (total_impressions / total_queries * 100) if total_queries > 0 else None
            avg_cpm = (row['total_spend'] / total_impressions * 1000) if total_impressions > 0 else None

            # Upsert summary
            cursor.execute("""
                INSERT OR REPLACE INTO campaign_daily_summary
                (campaign_id, date, total_creatives, active_creatives,
                 total_queries, total_impressions, total_clicks, total_spend,
                 avg_win_rate, avg_ctr, avg_cpm, unique_geos)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                campaign_id, date,
                row['total_creatives'] or 0,
                row['active_creatives'] or 0,
                total_queries,
                total_impressions,
                total_clicks,
                row['total_spend'] or 0,
                avg_win_rate,
                avg_ctr,
                avg_cpm,
                row['unique_geos'] or 0,
            ))

            self.db.commit()

    def get_campaign_performance(
        self,
        campaign_id: Union[str, int],
        days: int = 7,
    ) -> dict:
        """
        Get aggregated performance for a campaign.

        Args:
            campaign_id: Campaign ID
            days: Number of days to aggregate

        Returns:
            Performance dict with totals and averages
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT
                SUM(total_impressions) as impressions,
                SUM(total_clicks) as clicks,
                SUM(total_spend) as spend,
                SUM(total_queries) as queries,
                AVG(avg_win_rate) as win_rate,
                AVG(avg_ctr) as ctr,
                AVG(avg_cpm) as cpm
            FROM campaign_daily_summary
            WHERE campaign_id = ? AND date >= date('now', ?)
        """, (campaign_id, f"-{days} days"))

        row = cursor.fetchone()

        if row:
            return {
                'impressions': row['impressions'] or 0,
                'clicks': row['clicks'] or 0,
                'spend': row['spend'] or 0,
                'queries': row['queries'] or 0,
                'win_rate': row['win_rate'],
                'ctr': row['ctr'],
                'cpm': row['cpm'],
            }

        return {
            'impressions': 0,
            'clicks': 0,
            'spend': 0,
            'queries': 0,
            'win_rate': None,
            'ctr': None,
            'cpm': None,
        }

    def get_campaign_daily_trend(
        self,
        campaign_id: Union[str, int],
        days: int = 30,
    ) -> list[dict]:
        """
        Get daily performance trend for a campaign.

        Args:
            campaign_id: Campaign ID
            days: Number of days

        Returns:
            List of daily performance dicts
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT date, total_impressions, total_clicks, total_spend,
                   avg_win_rate, avg_ctr, avg_cpm, unique_geos
            FROM campaign_daily_summary
            WHERE campaign_id = ? AND date >= date('now', ?)
            ORDER BY date DESC
        """, (campaign_id, f"-{days} days"))

        return [dict(row) for row in cursor.fetchall()]

    # ==================== Helper Methods ====================

    def _row_to_campaign(self, row: sqlite3.Row) -> AICampaign:
        """Convert database row to AICampaign object."""
        # Use computed_count to avoid collision with creative_count table column
        count = row['computed_count'] if 'computed_count' in row.keys() else 0
        return AICampaign(
            id=row['id'],
            seat_id=row['seat_id'],
            name=row['name'],
            description=row['description'],
            ai_generated=bool(row['ai_generated']),
            ai_confidence=row['ai_confidence'],
            clustering_method=row['clustering_method'],
            status=row['status'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            creative_count=count,
        )
