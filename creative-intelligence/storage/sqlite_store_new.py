"""SQLite storage backend for creative data.

This module provides the main SQLiteStore class which acts as a facade
for underlying repository classes. It maintains backward compatibility
while delegating to specialized repositories for better code organization.

Example:
    >>> from storage import SQLiteStore
    >>>
    >>> store = SQLiteStore(db_path="~/.catscan/catscan.db")
    >>> await store.initialize()
    >>>
    >>> # Save creatives
    >>> await store.save_creatives(creatives)
    >>>
    >>> # Query
    >>> html_creatives = await store.list_creatives(format="HTML")
    >>> stats = await store.get_stats()
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

# Import models from centralized location
from .models import (
    Creative, Campaign, Cluster, ServiceAccount, BuyerSeat, PerformanceMetric,
)

# Import schema for initialization
from .schema import SCHEMA, MIGRATIONS

# Import repositories
from .repositories import (
    CreativeRepository, AccountRepository, TrafficRepository, ThumbnailRepository,
)

if TYPE_CHECKING:
    from collectors.creatives.schemas import CreativeDict

logger = logging.getLogger(__name__)


# Re-export models for backward compatibility
__all__ = [
    "SQLiteStore",
    "Creative",
    "Campaign",
    "Cluster",
    "ServiceAccount",
    "BuyerSeat",
    "PerformanceMetric",
]


class SQLiteStore:
    """Async SQLite storage for creative intelligence data.

    Provides CRUD operations for creatives, campaigns, and clusters
    with support for search and filtering.

    This class acts as a facade, delegating to specialized repositories
    for better code organization while maintaining the existing API.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str | Path = "~/.catscan/catscan.db") -> None:
        """Initialize the SQLite store.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path).expanduser()
        self._initialized = False

        # Initialize repositories
        self._creative_repo = CreativeRepository(self.db_path)
        self._account_repo = AccountRepository(self.db_path)
        self._traffic_repo = TrafficRepository(self.db_path)
        self._thumbnail_repo = ThumbnailRepository(self.db_path)

    async def initialize(self) -> None:
        """Initialize the database schema.

        Creates the database file and tables if they don't exist.
        """
        if self._initialized:
            return

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._init_schema)
        self._initialized = True
        logger.info(f"Database initialized at {self.db_path}")

    def _init_schema(self) -> None:
        """Synchronously initialize the database schema and run migrations."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()

            # Run migrations for existing databases
            for migration in MIGRATIONS:
                try:
                    conn.execute(migration)
                    conn.commit()
                except sqlite3.OperationalError:
                    # Column/index already exists, skip
                    pass
        finally:
            conn.close()

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[sqlite3.Connection]:
        """Context manager for database connections.

        Yields:
            SQLite connection with row factory set to sqlite3.Row.
        """
        await self.initialize()

        loop = asyncio.get_event_loop()
        conn = await loop.run_in_executor(
            None,
            lambda: sqlite3.connect(self.db_path, check_same_thread=False),
        )
        conn.row_factory = sqlite3.Row

        try:
            yield conn
        finally:
            await loop.run_in_executor(None, conn.close)

    # =========================================================================
    # Creative Methods - Delegate to CreativeRepository
    # =========================================================================

    async def save_creative(self, creative: Creative) -> None:
        """Save or update a creative record."""
        await self._creative_repo.save(creative)

    async def save_creatives(self, creatives: list[Creative]) -> int:
        """Batch save multiple creatives."""
        return await self._creative_repo.save_batch(creatives)

    async def get_creative(self, creative_id: str) -> Optional[Creative]:
        """Get a creative by ID."""
        return await self._creative_repo.get(creative_id)

    async def list_creatives(
        self,
        buyer_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        cluster_id: Optional[str] = None,
        format: Optional[str] = None,
        canonical_size: Optional[str] = None,
        size_category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Creative]:
        """List creatives with optional filtering."""
        return await self._creative_repo.list(
            buyer_id=buyer_id,
            campaign_id=campaign_id,
            cluster_id=cluster_id,
            format=format,
            canonical_size=canonical_size,
            size_category=size_category,
            limit=limit,
            offset=offset,
        )

    async def delete_creative(self, creative_id: str) -> bool:
        """Delete a creative by ID."""
        return await self._creative_repo.delete(creative_id)

    async def update_creative_cluster(
        self,
        creative_id: str,
        cluster_id: Optional[str],
    ) -> bool:
        """Update the cluster assignment for a creative."""
        return await self._creative_repo.update_cluster(creative_id, cluster_id)

    async def update_creative_campaign(
        self,
        creative_id: str,
        campaign_id: Optional[str],
    ) -> bool:
        """Update the campaign assignment for a creative."""
        return await self._creative_repo.update_campaign(creative_id, campaign_id)

    async def get_available_sizes(self) -> list[str]:
        """Get all unique canonical sizes in the database."""
        return await self._creative_repo.get_available_sizes()

    async def get_unclustered_creative_ids(
        self, buyer_id: Optional[str] = None
    ) -> list[str]:
        """Get IDs of creatives not assigned to any campaign."""
        return await self._creative_repo.get_unclustered_ids(buyer_id)

    # =========================================================================
    # Service Account Methods - Delegate to AccountRepository
    # =========================================================================

    async def save_service_account(self, account: ServiceAccount) -> None:
        """Insert or update a service account."""
        await self._account_repo.save_service_account(account)

    async def get_service_accounts(
        self, active_only: bool = False
    ) -> list[ServiceAccount]:
        """Get all service accounts."""
        return await self._account_repo.get_service_accounts(active_only)

    async def get_service_account(self, account_id: str) -> Optional[ServiceAccount]:
        """Get a specific service account."""
        return await self._account_repo.get_service_account(account_id)

    async def get_service_account_by_email(
        self, client_email: str
    ) -> Optional[ServiceAccount]:
        """Get a service account by its client email."""
        return await self._account_repo.get_service_account_by_email(client_email)

    async def delete_service_account(self, account_id: str) -> bool:
        """Delete a service account."""
        return await self._account_repo.delete_service_account(account_id)

    async def update_service_account_last_used(self, account_id: str) -> None:
        """Update last_used timestamp for a service account."""
        await self._account_repo.update_service_account_last_used(account_id)

    # =========================================================================
    # Buyer Seat Methods - Delegate to AccountRepository
    # =========================================================================

    async def save_buyer_seat(self, seat: BuyerSeat) -> None:
        """Insert or update a buyer seat."""
        await self._account_repo.save_buyer_seat(seat)

    async def get_buyer_seats(
        self,
        bidder_id: Optional[str] = None,
        active_only: bool = False,
    ) -> list[BuyerSeat]:
        """Get all buyer seats, optionally filtered."""
        return await self._account_repo.get_buyer_seats(bidder_id, active_only)

    async def get_buyer_seat(self, buyer_id: str) -> Optional[BuyerSeat]:
        """Get a specific buyer seat."""
        return await self._account_repo.get_buyer_seat(buyer_id)

    async def update_seat_creative_count(self, buyer_id: str) -> int:
        """Update the creative_count for a buyer seat."""
        return await self._account_repo.update_seat_creative_count(buyer_id)

    async def update_seat_sync_time(self, buyer_id: str) -> None:
        """Update last_synced timestamp for a buyer seat."""
        await self._account_repo.update_seat_sync_time(buyer_id)

    async def populate_buyer_seats_from_creatives(self) -> int:
        """Populate buyer_seats table from existing creatives."""
        return await self._account_repo.populate_buyer_seats_from_creatives()

    async def update_buyer_seat_display_name(
        self, buyer_id: str, display_name: str
    ) -> bool:
        """Update the display name for a buyer seat."""
        return await self._account_repo.update_buyer_seat_display_name(
            buyer_id, display_name
        )

    async def link_buyer_seat_to_service_account(
        self,
        buyer_id: str,
        service_account_id: str,
    ) -> None:
        """Link a buyer seat to a service account."""
        await self._account_repo.link_buyer_seat_to_service_account(
            buyer_id, service_account_id
        )

    # =========================================================================
    # Traffic Data Methods - Delegate to TrafficRepository
    # =========================================================================

    async def store_traffic_data(self, traffic_data: list[dict]) -> int:
        """Store RTB traffic data records."""
        return await self._traffic_repo.store_traffic_data(traffic_data)

    async def get_traffic_data(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
    ) -> list[dict]:
        """Get RTB traffic data for analysis."""
        return await self._traffic_repo.get_traffic_data(buyer_id, days)

    async def get_traffic_summary(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
    ) -> dict:
        """Get summary statistics for RTB traffic."""
        return await self._traffic_repo.get_traffic_summary(buyer_id, days)

    async def clear_traffic_data(
        self,
        buyer_id: Optional[str] = None,
        days_to_keep: int = 30,
    ) -> int:
        """Clear old traffic data."""
        return await self._traffic_repo.clear_traffic_data(buyer_id, days_to_keep)

    async def clear_old_rtb_daily(self, days_to_keep: int = 90) -> int:
        """Clear old RTB daily data beyond retention period."""
        return await self._traffic_repo.clear_old_rtb_daily(days_to_keep)

    # =========================================================================
    # Thumbnail Status Methods - Delegate to ThumbnailRepository
    # =========================================================================

    async def record_thumbnail_status(
        self,
        creative_id: str,
        status: str,
        error_reason: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> None:
        """Record the thumbnail generation status for a creative."""
        await self._thumbnail_repo.record_status(
            creative_id, status, error_reason, video_url
        )

    async def get_thumbnail_status(self, creative_id: str) -> Optional[dict]:
        """Get the thumbnail status for a single creative."""
        return await self._thumbnail_repo.get_status(creative_id)

    async def get_thumbnail_statuses(
        self, creative_ids: Optional[list[str]] = None
    ) -> dict[str, dict]:
        """Get thumbnail statuses for multiple creatives."""
        return await self._thumbnail_repo.get_statuses(creative_ids)

    async def get_video_creatives_needing_thumbnails(
        self, limit: int = 100, force_retry_failed: bool = False
    ) -> list[dict]:
        """Get video creatives that need thumbnail generation."""
        return await self._thumbnail_repo.get_video_creatives_needing_thumbnails(
            limit, force_retry_failed
        )

    async def get_html_creatives_pending_thumbnails(
        self, limit: int = 100, force_retry_failed: bool = False
    ) -> list[dict]:
        """Get HTML creatives that need thumbnail extraction."""
        return await self._thumbnail_repo.get_html_creatives_pending_thumbnails(
            limit, force_retry_failed
        )

    async def get_thumbnail_stats(self) -> dict:
        """Get summary statistics for thumbnail generation."""
        return await self._thumbnail_repo.get_stats()

    # =========================================================================
    # Campaign Methods - Keep in SQLiteStore for now
    # (These are simpler and used less frequently)
    # =========================================================================

    async def save_campaign(self, campaign: Campaign) -> None:
        """Save or update a campaign record."""
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO campaigns (
                        id, name, source, creative_count, metadata, updated_at
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        campaign.id,
                        campaign.name,
                        campaign.source,
                        campaign.creative_count,
                        json.dumps(campaign.metadata),
                    ),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get a campaign by ID."""
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    "SELECT * FROM campaigns WHERE id = ?",
                    (campaign_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return Campaign(
                    id=row["id"],
                    name=row["name"],
                    source=row["source"],
                    creative_count=row["creative_count"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            return None

    async def list_campaigns(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Campaign]:
        """List campaigns."""
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT * FROM campaigns
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            Campaign(
                id=row["id"],
                name=row["name"],
                source=row["source"],
                creative_count=row["creative_count"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def save_cluster(self, cluster: Cluster) -> None:
        """Save or update a cluster record."""
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO clusters (
                        id, name, description, creative_count, centroid
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        cluster.id,
                        cluster.name,
                        cluster.description,
                        cluster.creative_count,
                        json.dumps(cluster.centroid) if cluster.centroid else None,
                    ),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    # =========================================================================
    # Statistics and Utility Methods
    # =========================================================================

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            creative_count = await loop.run_in_executor(
                None,
                lambda: conn.execute("SELECT COUNT(*) FROM creatives").fetchone()[0],
            )

            campaign_count = await loop.run_in_executor(
                None,
                lambda: conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
            )

            cluster_count = await loop.run_in_executor(
                None,
                lambda: conn.execute("SELECT COUNT(*) FROM clusters").fetchone()[0],
            )

            format_counts = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT format, COUNT(*) as count FROM creatives GROUP BY format"
                ).fetchall(),
            )

            size_category_counts = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT size_category, COUNT(*) as count FROM creatives "
                    "WHERE size_category IS NOT NULL GROUP BY size_category"
                ).fetchall(),
            )

            canonical_size_counts = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "SELECT canonical_size, COUNT(*) as count FROM creatives "
                    "WHERE canonical_size IS NOT NULL GROUP BY canonical_size "
                    "ORDER BY count DESC"
                ).fetchall(),
            )

        return {
            "creative_count": creative_count,
            "campaign_count": campaign_count,
            "cluster_count": cluster_count,
            "formats": {row[0]: row[1] for row in format_counts},
            "size_categories": {row[0]: row[1] for row in size_category_counts},
            "canonical_sizes": {row[0]: row[1] for row in canonical_size_counts},
            "db_path": str(self.db_path),
        }

    # =========================================================================
    # Performance Metrics Methods
    # (Keep in SQLiteStore - these interact with external PerformanceRepository)
    # =========================================================================

    async def save_performance_metrics(
        self,
        metrics: list[PerformanceMetric],
    ) -> int:
        """Batch save performance metrics with UPSERT semantics."""
        if not metrics:
            return 0

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _insert_metrics():
                count = 0
                for m in metrics:
                    try:
                        conn.execute(
                            """
                            INSERT INTO performance_metrics
                            (creative_id, campaign_id, metric_date, impressions, clicks,
                             spend_micros, cpm_micros, cpc_micros, geography,
                             device_type, placement, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(creative_id, metric_date, geography, device_type, placement)
                            DO UPDATE SET
                                impressions = impressions + excluded.impressions,
                                clicks = clicks + excluded.clicks,
                                spend_micros = spend_micros + excluded.spend_micros,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (
                                m.creative_id,
                                m.campaign_id,
                                m.metric_date,
                                m.impressions,
                                m.clicks,
                                m.spend_micros,
                                m.cpm_micros,
                                m.cpc_micros,
                                m.geography,
                                m.device_type,
                                m.placement,
                            ),
                        )
                        count += 1
                    except Exception as e:
                        logger.warning(f"Failed to insert metric: {e}")
                conn.commit()
                return count

            return await loop.run_in_executor(None, _insert_metrics)

    async def get_performance_metrics(
        self,
        creative_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        days: int = 30,
        geography: Optional[str] = None,
    ) -> list[dict]:
        """Get performance metrics with optional filtering."""
        conditions = ["metric_date >= date('now', ?)"]
        params: list[Any] = [f"-{days} days"]

        if creative_id:
            conditions.append("creative_id = ?")
            params.append(creative_id)
        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)
        if geography:
            conditions.append("geography = ?")
            params.append(geography)

        where_clause = " AND ".join(conditions)

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT
                        creative_id,
                        metric_date,
                        SUM(impressions) as impressions,
                        SUM(clicks) as clicks,
                        SUM(spend_micros) as spend_micros,
                        geography
                    FROM performance_metrics
                    WHERE {where_clause}
                    GROUP BY creative_id, metric_date, geography
                    ORDER BY metric_date DESC
                    """,
                    params,
                )
                return [dict(row) for row in cursor.fetchall()]

            return await loop.run_in_executor(None, _query)

    async def get_creative_performance_summary(
        self,
        creative_ids: list[str],
        days: int = 30,
    ) -> dict[str, dict]:
        """Get aggregated performance summary for multiple creatives."""
        if not creative_ids:
            return {}

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                placeholders = ",".join("?" * len(creative_ids))
                cursor = conn.execute(
                    f"""
                    SELECT
                        creative_id,
                        SUM(impressions) as total_impressions,
                        SUM(clicks) as total_clicks,
                        SUM(spend_micros) as total_spend_micros,
                        COUNT(DISTINCT geography) as unique_geos,
                        MIN(metric_date) as first_date,
                        MAX(metric_date) as last_date
                    FROM performance_metrics
                    WHERE creative_id IN ({placeholders})
                    AND metric_date >= date('now', ?)
                    GROUP BY creative_id
                    """,
                    (*creative_ids, f"-{days} days"),
                )

                result = {}
                for row in cursor.fetchall():
                    impressions = row["total_impressions"] or 0
                    clicks = row["total_clicks"] or 0
                    result[row["creative_id"]] = {
                        "total_impressions": impressions,
                        "total_clicks": clicks,
                        "total_spend_micros": row["total_spend_micros"] or 0,
                        "unique_geos": row["unique_geos"] or 0,
                        "ctr_percent": (clicks / impressions * 100) if impressions > 0 else 0,
                        "first_date": row["first_date"],
                        "last_date": row["last_date"],
                        "has_data": True,
                    }
                return result

            return await loop.run_in_executor(None, _query)
