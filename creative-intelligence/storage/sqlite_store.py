"""SQLite storage backend for creative data.

This module provides local SQLite storage for creative metadata,
campaigns, and clustering results.

Example:
    >>> from storage import SQLiteStore
    >>>
    >>> store = SQLiteStore(db_path="~/.rtbcat/rtbcat.db")
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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

if TYPE_CHECKING:
    from collectors.creatives.schemas import CreativeDict

logger = logging.getLogger(__name__)


@dataclass
class Creative:
    """Creative record for database storage.

    Attributes:
        id: Unique creative identifier (from API creativeId).
        name: Full resource name (bidders/{account}/creatives/{id}).
        format: Creative format (HTML, VIDEO, NATIVE, UNKNOWN).
        account_id: Bidder account ID.
        approval_status: Network policy compliance status.
        width: Creative width in pixels (for HTML/native image).
        height: Creative height in pixels (for HTML/native image).
        final_url: Primary destination URL.
        display_url: Display URL (may differ from final_url).
        utm_source: UTM source parameter.
        utm_medium: UTM medium parameter.
        utm_campaign: UTM campaign parameter.
        utm_content: UTM content parameter.
        utm_term: UTM term parameter.
        advertiser_name: Declared advertiser name.
        campaign_id: Assigned campaign ID (from clustering).
        cluster_id: Assigned cluster ID (from AI clustering).
        raw_data: Full API response and format-specific data as JSON.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    id: str
    name: str
    format: str
    account_id: Optional[str] = None
    approval_status: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    final_url: Optional[str] = None
    display_url: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    advertiser_name: Optional[str] = None
    campaign_id: Optional[str] = None
    cluster_id: Optional[str] = None
    raw_data: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Campaign:
    """Campaign record for database storage."""

    id: str
    name: str
    source: str = "google_ads"
    creative_count: int = 0
    metadata: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Cluster:
    """Cluster record for database storage."""

    id: str
    name: str
    description: Optional[str] = None
    creative_count: int = 0
    centroid: Optional[dict] = None
    created_at: Optional[datetime] = None


class SQLiteStore:
    """Async SQLite storage for creative intelligence data.

    Provides CRUD operations for creatives, campaigns, and clusters
    with support for search and filtering.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS creatives (
        id TEXT PRIMARY KEY,
        name TEXT,
        format TEXT,
        account_id TEXT,
        approval_status TEXT,
        width INTEGER,
        height INTEGER,
        final_url TEXT,
        display_url TEXT,
        utm_source TEXT,
        utm_medium TEXT,
        utm_campaign TEXT,
        utm_content TEXT,
        utm_term TEXT,
        advertiser_name TEXT,
        campaign_id TEXT,
        cluster_id TEXT,
        raw_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
        FOREIGN KEY (cluster_id) REFERENCES clusters(id)
    );

    CREATE TABLE IF NOT EXISTS campaigns (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        source TEXT DEFAULT 'google_ads',
        creative_count INTEGER DEFAULT 0,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS clusters (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        creative_count INTEGER DEFAULT 0,
        centroid TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_creatives_campaign ON creatives(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_creatives_cluster ON creatives(cluster_id);
    CREATE INDEX IF NOT EXISTS idx_creatives_format ON creatives(format);
    CREATE INDEX IF NOT EXISTS idx_creatives_utm_campaign ON creatives(utm_campaign);
    CREATE INDEX IF NOT EXISTS idx_creatives_account ON creatives(account_id);
    CREATE INDEX IF NOT EXISTS idx_creatives_approval ON creatives(approval_status);
    """

    # Migration for existing databases to add new columns
    MIGRATIONS = [
        "ALTER TABLE creatives ADD COLUMN account_id TEXT",
        "ALTER TABLE creatives ADD COLUMN approval_status TEXT",
        "ALTER TABLE creatives ADD COLUMN advertiser_name TEXT",
        "CREATE INDEX IF NOT EXISTS idx_creatives_account ON creatives(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_creatives_approval ON creatives(approval_status)",
    ]

    def __init__(self, db_path: str | Path = "~/.rtbcat/rtbcat.db") -> None:
        """Initialize the SQLite store.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path).expanduser()
        self._initialized = False

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
            conn.executescript(self.SCHEMA)
            conn.commit()

            # Run migrations for existing databases
            for migration in self.MIGRATIONS:
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
            lambda: sqlite3.connect(self.db_path),
        )
        conn.row_factory = sqlite3.Row

        try:
            yield conn
        finally:
            await loop.run_in_executor(None, conn.close)

    async def save_creative(self, creative: Creative) -> None:
        """Save or update a creative record.

        Args:
            creative: The Creative to save.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO creatives (
                        id, name, format, account_id, approval_status,
                        width, height, final_url, display_url,
                        utm_source, utm_medium, utm_campaign,
                        utm_content, utm_term, advertiser_name,
                        campaign_id, cluster_id, raw_data,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        creative.id,
                        creative.name,
                        creative.format,
                        creative.account_id,
                        creative.approval_status,
                        creative.width,
                        creative.height,
                        creative.final_url,
                        creative.display_url,
                        creative.utm_source,
                        creative.utm_medium,
                        creative.utm_campaign,
                        creative.utm_content,
                        creative.utm_term,
                        creative.advertiser_name,
                        creative.campaign_id,
                        creative.cluster_id,
                        json.dumps(creative.raw_data),
                    ),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def save_creatives(self, creatives: list[Creative]) -> int:
        """Batch save multiple creatives.

        Args:
            creatives: List of Creative objects to save.

        Returns:
            Number of creatives saved.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            data = [
                (
                    c.id, c.name, c.format, c.account_id, c.approval_status,
                    c.width, c.height, c.final_url, c.display_url,
                    c.utm_source, c.utm_medium, c.utm_campaign,
                    c.utm_content, c.utm_term, c.advertiser_name,
                    c.campaign_id, c.cluster_id, json.dumps(c.raw_data),
                )
                for c in creatives
            ]

            await loop.run_in_executor(
                None,
                lambda: conn.executemany(
                    """
                    INSERT OR REPLACE INTO creatives (
                        id, name, format, account_id, approval_status,
                        width, height, final_url, display_url,
                        utm_source, utm_medium, utm_campaign,
                        utm_content, utm_term, advertiser_name,
                        campaign_id, cluster_id, raw_data,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    data,
                ),
            )
            await loop.run_in_executor(None, conn.commit)

        return len(creatives)

    async def get_creative(self, creative_id: str) -> Optional[Creative]:
        """Get a creative by ID.

        Args:
            creative_id: The creative ID.

        Returns:
            Creative object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    "SELECT * FROM creatives WHERE id = ?",
                    (creative_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return self._row_to_creative(row)
            return None

    def _row_to_creative(self, row: sqlite3.Row) -> Creative:
        """Convert a database row to a Creative object."""
        # Handle columns that may not exist in older databases
        row_dict = dict(row)

        return Creative(
            id=row_dict["id"],
            name=row_dict["name"],
            format=row_dict["format"],
            account_id=row_dict.get("account_id"),
            approval_status=row_dict.get("approval_status"),
            width=row_dict.get("width"),
            height=row_dict.get("height"),
            final_url=row_dict.get("final_url"),
            display_url=row_dict.get("display_url"),
            utm_source=row_dict.get("utm_source"),
            utm_medium=row_dict.get("utm_medium"),
            utm_campaign=row_dict.get("utm_campaign"),
            utm_content=row_dict.get("utm_content"),
            utm_term=row_dict.get("utm_term"),
            advertiser_name=row_dict.get("advertiser_name"),
            campaign_id=row_dict.get("campaign_id"),
            cluster_id=row_dict.get("cluster_id"),
            raw_data=json.loads(row_dict["raw_data"]) if row_dict.get("raw_data") else {},
            created_at=row_dict.get("created_at"),
            updated_at=row_dict.get("updated_at"),
        )

    async def list_creatives(
        self,
        campaign_id: Optional[str] = None,
        cluster_id: Optional[str] = None,
        format: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Creative]:
        """List creatives with optional filtering.

        Args:
            campaign_id: Filter by campaign ID.
            cluster_id: Filter by cluster ID.
            format: Filter by creative format.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of Creative objects.
        """
        conditions = []
        params = []

        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)
        if cluster_id:
            conditions.append("cluster_id = ?")
            params.append(cluster_id)
        if format:
            conditions.append("format = ?")
            params.append(format)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT * FROM creatives
                    WHERE {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    params,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [self._row_to_creative(row) for row in rows]

    async def save_campaign(self, campaign: Campaign) -> None:
        """Save or update a campaign record.

        Args:
            campaign: The Campaign to save.
        """
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
        """Get a campaign by ID.

        Args:
            campaign_id: The campaign ID.

        Returns:
            Campaign object or None if not found.
        """
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
        source: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Campaign]:
        """List campaigns with optional filtering.

        Args:
            source: Filter by data source.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of Campaign objects.
        """
        conditions = []
        params = []

        if source:
            conditions.append("source = ?")
            params.append(source)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT * FROM campaigns
                    WHERE {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    params,
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
        """Save or update a cluster record.

        Args:
            cluster: The Cluster to save.
        """
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

    async def update_creative_cluster(
        self,
        creative_id: str,
        cluster_id: str,
    ) -> None:
        """Update the cluster assignment for a creative.

        Args:
            creative_id: The creative ID.
            cluster_id: The new cluster ID.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    UPDATE creatives
                    SET cluster_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (cluster_id, creative_id),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with counts and metadata.
        """
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

        return {
            "creative_count": creative_count,
            "campaign_count": campaign_count,
            "cluster_count": cluster_count,
            "formats": {row[0]: row[1] for row in format_counts},
            "db_path": str(self.db_path),
        }

    async def delete_creative(self, creative_id: str) -> bool:
        """Delete a creative by ID.

        Args:
            creative_id: The creative ID.

        Returns:
            True if deleted, False if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "DELETE FROM creatives WHERE id = ?",
                    (creative_id,),
                ),
            )
            await loop.run_in_executor(None, conn.commit)
            return cursor.rowcount > 0

    async def get_available_sizes(self) -> list[str]:
        """Get distinct creative sizes from the database.

        Returns:
            List of size strings in 'WIDTHxHEIGHT' format, sorted.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT DISTINCT width, height FROM creatives
                    WHERE width IS NOT NULL AND height IS NOT NULL
                    ORDER BY width, height
                    """
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [f"{row[0]}x{row[1]}" for row in rows]
