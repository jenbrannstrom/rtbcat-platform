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
import re
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

from utils.size_normalization import canonical_size as compute_canonical_size
from utils.size_normalization import get_size_category

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
        buyer_id: Buyer seat ID (for multi-seat accounts).
        approval_status: Network policy compliance status.
        width: Creative width in pixels (for HTML/native image).
        height: Creative height in pixels (for HTML/native image).
        canonical_size: Normalized IAB standard size (e.g., "300x250 (Medium Rectangle)").
        size_category: Size category ("IAB Standard", "Video", "Adaptive", "Non-Standard").
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
    buyer_id: Optional[str] = None
    approval_status: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    canonical_size: Optional[str] = None
    size_category: Optional[str] = None
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


@dataclass
class BuyerSeat:
    """Buyer seat record for multi-seat account support.

    Attributes:
        buyer_id: Unique buyer account ID (e.g., "456" from buyers/456).
        bidder_id: Parent bidder account ID.
        display_name: Human-readable name for the buyer seat.
        active: Whether the seat is active for syncing.
        creative_count: Number of creatives associated with this seat.
        last_synced: Timestamp of last successful sync.
        created_at: Record creation timestamp.
    """

    buyer_id: str
    bidder_id: str
    display_name: Optional[str] = None
    active: bool = True
    creative_count: int = 0
    last_synced: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class PerformanceMetric:
    """Performance metrics record for daily creative/campaign data.

    Attributes:
        id: Auto-increment primary key.
        creative_id: Foreign key to creatives table.
        campaign_id: Optional campaign association.
        metric_date: Date of the metrics (daily granularity).
        impressions: Number of ad impressions.
        clicks: Number of clicks (must be <= impressions).
        spend_micros: Spend in USD micros (1,000,000 = $1.00).
        cpm_micros: Cost per mille in micros.
        cpc_micros: Cost per click in micros.
        geography: ISO 3166-1 alpha-2 country code.
        device_type: Device category (DESKTOP, MOBILE, TABLET, CTV).
        placement: Publisher domain or app bundle.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    creative_id: str
    metric_date: str  # YYYY-MM-DD format
    impressions: int = 0
    clicks: int = 0
    spend_micros: int = 0
    cpm_micros: Optional[int] = None
    cpc_micros: Optional[int] = None
    campaign_id: Optional[str] = None
    geography: Optional[str] = None
    device_type: Optional[str] = None
    placement: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
        buyer_id TEXT,
        approval_status TEXT,
        width INTEGER,
        height INTEGER,
        canonical_size TEXT,
        size_category TEXT,
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
        FOREIGN KEY (cluster_id) REFERENCES clusters(id),
        FOREIGN KEY (buyer_id) REFERENCES buyer_seats(buyer_id)
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

    CREATE TABLE IF NOT EXISTS buyer_seats (
        buyer_id TEXT PRIMARY KEY,
        bidder_id TEXT NOT NULL,
        display_name TEXT,
        active INTEGER DEFAULT 1,
        creative_count INTEGER DEFAULT 0,
        last_synced TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(bidder_id, buyer_id)
    );

    CREATE INDEX IF NOT EXISTS idx_creatives_campaign ON creatives(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_creatives_cluster ON creatives(cluster_id);
    CREATE INDEX IF NOT EXISTS idx_creatives_format ON creatives(format);
    CREATE INDEX IF NOT EXISTS idx_creatives_utm_campaign ON creatives(utm_campaign);
    CREATE INDEX IF NOT EXISTS idx_creatives_account ON creatives(account_id);
    CREATE INDEX IF NOT EXISTS idx_creatives_approval ON creatives(approval_status);
    CREATE INDEX IF NOT EXISTS idx_creatives_canonical_size ON creatives(canonical_size);
    CREATE INDEX IF NOT EXISTS idx_creatives_size_category ON creatives(size_category);
    CREATE INDEX IF NOT EXISTS idx_creatives_buyer ON creatives(buyer_id);
    CREATE INDEX IF NOT EXISTS idx_buyer_seats_bidder ON buyer_seats(bidder_id);

    CREATE TABLE IF NOT EXISTS rtb_traffic (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id TEXT,
        canonical_size TEXT NOT NULL,
        raw_size TEXT NOT NULL,
        request_count INTEGER NOT NULL,
        date DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(buyer_id, canonical_size, raw_size, date)
    );

    CREATE INDEX IF NOT EXISTS idx_rtb_traffic_buyer ON rtb_traffic(buyer_id);
    CREATE INDEX IF NOT EXISTS idx_rtb_traffic_size ON rtb_traffic(canonical_size);
    CREATE INDEX IF NOT EXISTS idx_rtb_traffic_date ON rtb_traffic(date);

    CREATE TABLE IF NOT EXISTS performance_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creative_id TEXT NOT NULL,
        campaign_id TEXT,
        metric_date DATE NOT NULL,
        impressions INTEGER NOT NULL DEFAULT 0,
        clicks INTEGER NOT NULL DEFAULT 0,
        spend_micros INTEGER NOT NULL DEFAULT 0,
        cpm_micros INTEGER,
        cpc_micros INTEGER,
        geography TEXT,
        device_type TEXT,
        placement TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_perf_creative_date ON performance_metrics(creative_id, metric_date DESC);
    CREATE INDEX IF NOT EXISTS idx_perf_campaign_date ON performance_metrics(campaign_id, metric_date DESC);
    CREATE INDEX IF NOT EXISTS idx_perf_date_geo ON performance_metrics(metric_date, geography);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_perf_unique_daily ON performance_metrics(creative_id, metric_date, geography, device_type, placement);
    """

    # Migration for existing databases to add new columns
    MIGRATIONS = [
        "ALTER TABLE creatives ADD COLUMN account_id TEXT",
        "ALTER TABLE creatives ADD COLUMN approval_status TEXT",
        "ALTER TABLE creatives ADD COLUMN advertiser_name TEXT",
        "ALTER TABLE creatives ADD COLUMN canonical_size TEXT",
        "ALTER TABLE creatives ADD COLUMN size_category TEXT",
        "ALTER TABLE creatives ADD COLUMN buyer_id TEXT",
        "CREATE INDEX IF NOT EXISTS idx_creatives_account ON creatives(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_creatives_approval ON creatives(approval_status)",
        "CREATE INDEX IF NOT EXISTS idx_creatives_canonical_size ON creatives(canonical_size)",
        "CREATE INDEX IF NOT EXISTS idx_creatives_size_category ON creatives(size_category)",
        "CREATE INDEX IF NOT EXISTS idx_creatives_buyer ON creatives(buyer_id)",
        """CREATE TABLE IF NOT EXISTS buyer_seats (
            buyer_id TEXT PRIMARY KEY,
            bidder_id TEXT NOT NULL,
            display_name TEXT,
            active INTEGER DEFAULT 1,
            creative_count INTEGER DEFAULT 0,
            last_synced TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(bidder_id, buyer_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_buyer_seats_bidder ON buyer_seats(bidder_id)",
        """CREATE TABLE IF NOT EXISTS rtb_traffic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id TEXT,
            canonical_size TEXT NOT NULL,
            raw_size TEXT NOT NULL,
            request_count INTEGER NOT NULL,
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(buyer_id, canonical_size, raw_size, date)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_rtb_traffic_buyer ON rtb_traffic(buyer_id)",
        "CREATE INDEX IF NOT EXISTS idx_rtb_traffic_size ON rtb_traffic(canonical_size)",
        "CREATE INDEX IF NOT EXISTS idx_rtb_traffic_date ON rtb_traffic(date)",
        # Phase 8.1: Performance metrics table
        """CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creative_id TEXT NOT NULL,
            campaign_id TEXT,
            metric_date DATE NOT NULL,
            impressions INTEGER NOT NULL DEFAULT 0,
            clicks INTEGER NOT NULL DEFAULT 0,
            spend_micros INTEGER NOT NULL DEFAULT 0,
            cpm_micros INTEGER,
            cpc_micros INTEGER,
            geography TEXT,
            device_type TEXT,
            placement TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
        )""",
        "CREATE INDEX IF NOT EXISTS idx_perf_creative_date ON performance_metrics(creative_id, metric_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_perf_campaign_date ON performance_metrics(campaign_id, metric_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_perf_date_geo ON performance_metrics(metric_date, geography)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_perf_unique_daily ON performance_metrics(creative_id, metric_date, geography, device_type, placement)",
        # Phase 8.1: Campaign performance cache columns
        "ALTER TABLE campaigns ADD COLUMN spend_7d_micros INTEGER DEFAULT 0",
        "ALTER TABLE campaigns ADD COLUMN spend_30d_micros INTEGER DEFAULT 0",
        "ALTER TABLE campaigns ADD COLUMN total_impressions INTEGER DEFAULT 0",
        "ALTER TABLE campaigns ADD COLUMN total_clicks INTEGER DEFAULT 0",
        "ALTER TABLE campaigns ADD COLUMN avg_cpm_micros INTEGER",
        "ALTER TABLE campaigns ADD COLUMN avg_cpc_micros INTEGER",
        "ALTER TABLE campaigns ADD COLUMN perf_updated_at TIMESTAMP",
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
            lambda: sqlite3.connect(self.db_path, check_same_thread=False),
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
        # Compute canonical size if not already set
        canonical = creative.canonical_size
        category = creative.size_category
        if canonical is None and creative.width is not None and creative.height is not None:
            canonical = compute_canonical_size(creative.width, creative.height)
            category = get_size_category(canonical)

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO creatives (
                        id, name, format, account_id, buyer_id, approval_status,
                        width, height, canonical_size, size_category,
                        final_url, display_url,
                        utm_source, utm_medium, utm_campaign,
                        utm_content, utm_term, advertiser_name,
                        campaign_id, cluster_id, raw_data,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        creative.id,
                        creative.name,
                        creative.format,
                        creative.account_id,
                        creative.buyer_id,
                        creative.approval_status,
                        creative.width,
                        creative.height,
                        canonical,
                        category,
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

            def _compute_size_fields(c: Creative) -> tuple:
                """Compute canonical size fields for a creative."""
                canonical = c.canonical_size
                category = c.size_category
                if canonical is None and c.width is not None and c.height is not None:
                    canonical = compute_canonical_size(c.width, c.height)
                    category = get_size_category(canonical)
                return canonical, category

            data = [
                (
                    c.id, c.name, c.format, c.account_id, c.buyer_id, c.approval_status,
                    c.width, c.height,
                    *_compute_size_fields(c),
                    c.final_url, c.display_url,
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
                        id, name, format, account_id, buyer_id, approval_status,
                        width, height, canonical_size, size_category,
                        final_url, display_url,
                        utm_source, utm_medium, utm_campaign,
                        utm_content, utm_term, advertiser_name,
                        campaign_id, cluster_id, raw_data,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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

    def _parse_video_dimensions(self, raw_data: dict) -> tuple[Optional[int], Optional[int]]:
        """Extract width and height from video VAST XML.

        Parses the MediaFile tag in VAST XML to extract video dimensions.

        Args:
            raw_data: The raw_data dict containing video information.

        Returns:
            Tuple of (width, height) or (None, None) if not found.
        """
        video_data = raw_data.get("video")
        if not video_data:
            return None, None

        vast_xml = video_data.get("vastXml")
        if not vast_xml:
            return None, None

        # Parse MediaFile tag: <MediaFile width="720" height="1280" ...>
        match = re.search(
            r'<MediaFile[^>]*\s+width=["\'](\d+)["\'][^>]*\s+height=["\'](\d+)["\']',
            vast_xml,
        )
        if match:
            return int(match.group(1)), int(match.group(2))

        # Try alternate attribute order: height before width
        match = re.search(
            r'<MediaFile[^>]*\s+height=["\'](\d+)["\'][^>]*\s+width=["\'](\d+)["\']',
            vast_xml,
        )
        if match:
            return int(match.group(2)), int(match.group(1))

        return None, None

    def _row_to_creative(self, row: sqlite3.Row) -> Creative:
        """Convert a database row to a Creative object."""
        # Handle columns that may not exist in older databases
        row_dict = dict(row)

        # Parse raw_data first - needed for video dimension extraction
        raw_data = json.loads(row_dict["raw_data"]) if row_dict.get("raw_data") else {}

        # Get dimensions from database
        width = row_dict.get("width")
        height = row_dict.get("height")

        # For VIDEO format, try to extract dimensions from VAST XML if not set
        creative_format = row_dict.get("format")
        if creative_format == "VIDEO" and (width is None or height is None):
            video_width, video_height = self._parse_video_dimensions(raw_data)
            if video_width is not None and video_height is not None:
                width = video_width
                height = video_height

        # Compute canonical size on-the-fly if not stored (migration support)
        canonical = row_dict.get("canonical_size")
        category = row_dict.get("size_category")
        if canonical is None and width is not None and height is not None:
            canonical = compute_canonical_size(width, height)
            category = get_size_category(canonical)

        return Creative(
            id=row_dict["id"],
            name=row_dict["name"],
            format=row_dict["format"],
            account_id=row_dict.get("account_id"),
            buyer_id=row_dict.get("buyer_id"),
            approval_status=row_dict.get("approval_status"),
            width=width,
            height=height,
            canonical_size=canonical,
            size_category=category,
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
            raw_data=raw_data,
            created_at=row_dict.get("created_at"),
            updated_at=row_dict.get("updated_at"),
        )

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
        """List creatives with optional filtering.

        Args:
            buyer_id: Filter by buyer seat ID.
            campaign_id: Filter by campaign ID.
            cluster_id: Filter by cluster ID.
            format: Filter by creative format.
            canonical_size: Filter by canonical size (e.g., "300x250 (Medium Rectangle)").
            size_category: Filter by size category ("IAB Standard", "Video", etc.).
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of Creative objects.
        """
        conditions = []
        params = []

        if buyer_id:
            conditions.append("buyer_id = ?")
            params.append(buyer_id)
        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)
        if cluster_id:
            conditions.append("cluster_id = ?")
            params.append(cluster_id)
        if format:
            conditions.append("format = ?")
            params.append(format)
        if canonical_size:
            conditions.append("canonical_size = ?")
            params.append(canonical_size)
        if size_category:
            conditions.append("size_category = ?")
            params.append(size_category)

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

    async def update_creative_campaign(
        self,
        creative_id: str,
        campaign_id: Optional[str],
    ) -> None:
        """Update the campaign assignment for a creative.

        Args:
            creative_id: The creative ID.
            campaign_id: The new campaign ID (or None to remove from campaign).
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    UPDATE creatives
                    SET campaign_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (campaign_id, creative_id),
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

    async def migrate_canonical_sizes(self) -> int:
        """Migrate existing creatives to populate canonical_size fields.

        This method updates all creatives that have width/height but no
        canonical_size, computing the normalized size values. For VIDEO
        creatives, it also parses VAST XML to extract dimensions.

        Returns:
            Number of creatives updated.

        Example:
            >>> store = SQLiteStore()
            >>> await store.initialize()
            >>> updated = await store.migrate_canonical_sizes()
            >>> print(f"Migrated {updated} creatives")
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            # Get all creatives that need migration (have dimensions)
            def _get_unmigrated_with_dims():
                cursor = conn.execute(
                    """
                    SELECT id, width, height FROM creatives
                    WHERE width IS NOT NULL
                      AND height IS NOT NULL
                      AND canonical_size IS NULL
                    """
                )
                return cursor.fetchall()

            # Get VIDEO creatives without dimensions (need VAST parsing)
            def _get_unmigrated_videos():
                cursor = conn.execute(
                    """
                    SELECT id, raw_data FROM creatives
                    WHERE format = 'VIDEO'
                      AND (width IS NULL OR height IS NULL)
                      AND canonical_size IS NULL
                    """
                )
                return cursor.fetchall()

            rows_with_dims = await loop.run_in_executor(None, _get_unmigrated_with_dims)
            rows_videos = await loop.run_in_executor(None, _get_unmigrated_videos)

            updates = []
            updates_with_dims = []

            # Process creatives with existing dimensions
            for row in rows_with_dims:
                creative_id, width, height = row
                canonical = compute_canonical_size(width, height)
                category = get_size_category(canonical)
                updates.append((canonical, category, creative_id))

            # Process VIDEO creatives - parse VAST XML for dimensions
            for row in rows_videos:
                creative_id, raw_data_str = row
                if not raw_data_str:
                    continue

                raw_data = json.loads(raw_data_str)
                width, height = self._parse_video_dimensions(raw_data)

                if width is not None and height is not None:
                    canonical = compute_canonical_size(width, height)
                    category = get_size_category(canonical)
                    updates_with_dims.append((canonical, category, width, height, creative_id))

            if not updates and not updates_with_dims:
                return 0

            # Batch update creatives with existing dimensions
            if updates:
                await loop.run_in_executor(
                    None,
                    lambda: conn.executemany(
                        """
                        UPDATE creatives
                        SET canonical_size = ?, size_category = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        updates,
                    ),
                )

            # Batch update VIDEO creatives (also set width/height)
            if updates_with_dims:
                await loop.run_in_executor(
                    None,
                    lambda: conn.executemany(
                        """
                        UPDATE creatives
                        SET canonical_size = ?, size_category = ?, width = ?, height = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        updates_with_dims,
                    ),
                )

            await loop.run_in_executor(None, conn.commit)

        total = len(updates) + len(updates_with_dims)
        logger.info(f"Migrated canonical sizes for {total} creatives ({len(updates_with_dims)} from VAST XML)")
        return total

    async def migrate_add_buyer_seats(self) -> int:
        """Migrate existing creatives to populate buyer_id from resource name.

        This method:
        1. Creates the buyer_seats table if it doesn't exist
        2. Adds buyer_id column to creatives if it doesn't exist
        3. Extracts buyer_id from the creative name field (format: bidders/{}/creatives/{})
        4. Populates buyer_id for all existing creatives

        Returns:
            Number of creatives updated with buyer_id.

        Example:
            >>> store = SQLiteStore()
            >>> await store.initialize()
            >>> updated = await store.migrate_add_buyer_seats()
            >>> print(f"Migrated {updated} creatives with buyer_id")
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            # Run migrations (will skip if already done)
            for migration in self.MIGRATIONS:
                try:
                    await loop.run_in_executor(
                        None,
                        lambda m=migration: conn.execute(m),
                    )
                    await loop.run_in_executor(None, conn.commit)
                except sqlite3.OperationalError:
                    pass  # Already exists

            # Extract buyer_id from creatives.name field
            # Name format: bidders/{bidder_id}/creatives/{creative_id}
            # We need to extract buyer_id from account_id field or infer from data
            def _get_creatives_needing_buyer_id():
                cursor = conn.execute(
                    """
                    SELECT id, name, account_id FROM creatives
                    WHERE buyer_id IS NULL
                    """
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _get_creatives_needing_buyer_id)

            if not rows:
                logger.info("No creatives need buyer_id migration")
                return 0

            # For now, use account_id as buyer_id since they're often the same
            # In a real multi-seat setup, buyer_id would come from API response
            updates = []
            for row in rows:
                creative_id, name, account_id = row
                # Use account_id as buyer_id if available
                buyer_id = account_id
                if buyer_id:
                    updates.append((buyer_id, creative_id))

            if updates:
                await loop.run_in_executor(
                    None,
                    lambda: conn.executemany(
                        """
                        UPDATE creatives
                        SET buyer_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        updates,
                    ),
                )
                await loop.run_in_executor(None, conn.commit)

            logger.info(f"Migrated buyer_id for {len(updates)} creatives")
            return len(updates)

    # ==================== Buyer Seat Methods ====================

    async def save_buyer_seat(self, seat: BuyerSeat) -> None:
        """Insert or update a buyer seat.

        Args:
            seat: The BuyerSeat to save.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO buyer_seats (
                        buyer_id, bidder_id, display_name, active,
                        creative_count, last_synced, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, COALESCE(
                        (SELECT created_at FROM buyer_seats WHERE buyer_id = ?),
                        CURRENT_TIMESTAMP
                    ))
                    """,
                    (
                        seat.buyer_id,
                        seat.bidder_id,
                        seat.display_name,
                        1 if seat.active else 0,
                        seat.creative_count,
                        seat.last_synced,
                        seat.buyer_id,
                    ),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def get_buyer_seats(
        self,
        bidder_id: Optional[str] = None,
        active_only: bool = False,
    ) -> list[BuyerSeat]:
        """Get all buyer seats, optionally filtered by bidder_id.

        Args:
            bidder_id: Optional filter by bidder account.
            active_only: If True, only return active seats.

        Returns:
            List of BuyerSeat objects.
        """
        conditions = []
        params = []

        if bidder_id:
            conditions.append("bidder_id = ?")
            params.append(bidder_id)
        if active_only:
            conditions.append("active = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT buyer_id, bidder_id, display_name, active,
                           creative_count, last_synced, created_at
                    FROM buyer_seats
                    WHERE {where_clause}
                    ORDER BY display_name, buyer_id
                    """,
                    params,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            BuyerSeat(
                buyer_id=row[0],
                bidder_id=row[1],
                display_name=row[2],
                active=bool(row[3]),
                creative_count=row[4] or 0,
                last_synced=row[5],
                created_at=row[6],
            )
            for row in rows
        ]

    async def get_buyer_seat(self, buyer_id: str) -> Optional[BuyerSeat]:
        """Get a specific buyer seat.

        Args:
            buyer_id: The buyer ID.

        Returns:
            BuyerSeat object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT buyer_id, bidder_id, display_name, active,
                           creative_count, last_synced, created_at
                    FROM buyer_seats
                    WHERE buyer_id = ?
                    """,
                    (buyer_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return BuyerSeat(
                    buyer_id=row[0],
                    bidder_id=row[1],
                    display_name=row[2],
                    active=bool(row[3]),
                    creative_count=row[4] or 0,
                    last_synced=row[5],
                    created_at=row[6],
                )
            return None

    async def update_seat_creative_count(self, buyer_id: str) -> int:
        """Update the creative_count for a buyer seat by counting creatives.

        Args:
            buyer_id: The buyer ID to update.

        Returns:
            The updated creative count.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _count_and_update():
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM creatives WHERE buyer_id = ?",
                    (buyer_id,),
                )
                count = cursor.fetchone()[0]

                conn.execute(
                    """
                    UPDATE buyer_seats
                    SET creative_count = ?
                    WHERE buyer_id = ?
                    """,
                    (count, buyer_id),
                )
                conn.commit()
                return count

            count = await loop.run_in_executor(None, _count_and_update)
            return count

    async def update_seat_sync_time(self, buyer_id: str) -> None:
        """Update last_synced timestamp for a buyer seat.

        Args:
            buyer_id: The buyer ID to update.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    UPDATE buyer_seats
                    SET last_synced = CURRENT_TIMESTAMP
                    WHERE buyer_id = ?
                    """,
                    (buyer_id,),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    # RTB Traffic Data Methods

    async def store_traffic_data(
        self,
        traffic_data: list[dict],
    ) -> int:
        """Store RTB traffic data records.

        Uses INSERT OR REPLACE to handle duplicates (same buyer_id,
        canonical_size, raw_size, date combination).

        Args:
            traffic_data: List of traffic records with keys:
                - canonical_size: Normalized size category
                - raw_size: Original requested size
                - request_count: Number of requests
                - date: Date string (YYYY-MM-DD)
                - buyer_id: Optional buyer seat ID

        Returns:
            Number of records stored.

        Example:
            >>> traffic = [
            ...     {"canonical_size": "300x250 (Medium Rectangle)",
            ...      "raw_size": "300x250", "request_count": 45000,
            ...      "date": "2025-11-29", "buyer_id": "456"}
            ... ]
            >>> count = await store.store_traffic_data(traffic)
        """
        if not traffic_data:
            return 0

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _insert_traffic():
                count = 0
                for record in traffic_data:
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO rtb_traffic
                            (buyer_id, canonical_size, raw_size, request_count, date)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                record.get("buyer_id"),
                                record["canonical_size"],
                                record["raw_size"],
                                record["request_count"],
                                record["date"],
                            ),
                        )
                        count += 1
                    except (KeyError, sqlite3.Error) as e:
                        logger.warning(f"Failed to insert traffic record: {e}")
                conn.commit()
                return count

            return await loop.run_in_executor(None, _insert_traffic)

    async def get_traffic_data(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
    ) -> list[dict]:
        """Get RTB traffic data for analysis.

        Args:
            buyer_id: Optional filter by buyer seat ID.
            days: Number of days of data to retrieve.

        Returns:
            List of traffic records as dictionaries with aggregated
            request counts by canonical_size.

        Example:
            >>> traffic = await store.get_traffic_data(days=7)
            >>> for record in traffic:
            ...     print(f"{record['canonical_size']}: {record['request_count']}")
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_traffic():
                query = """
                    SELECT
                        canonical_size,
                        raw_size,
                        SUM(request_count) as request_count,
                        buyer_id
                    FROM rtb_traffic
                    WHERE date >= date('now', ?)
                """
                params: list = [f"-{days} days"]

                if buyer_id:
                    query += " AND buyer_id = ?"
                    params.append(buyer_id)

                query += " GROUP BY canonical_size, raw_size, buyer_id"

                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

            return await loop.run_in_executor(None, _get_traffic)

    async def get_traffic_summary(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
    ) -> dict:
        """Get summary statistics for RTB traffic.

        Args:
            buyer_id: Optional filter by buyer seat ID.
            days: Number of days of data to summarize.

        Returns:
            Dictionary with summary statistics.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_summary():
                query = """
                    SELECT
                        COUNT(DISTINCT canonical_size) as unique_sizes,
                        SUM(request_count) as total_requests,
                        MIN(date) as earliest_date,
                        MAX(date) as latest_date
                    FROM rtb_traffic
                    WHERE date >= date('now', ?)
                """
                params: list = [f"-{days} days"]

                if buyer_id:
                    query += " AND buyer_id = ?"
                    params.append(buyer_id)

                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return {
                    "unique_sizes": 0,
                    "total_requests": 0,
                    "earliest_date": None,
                    "latest_date": None,
                }

            return await loop.run_in_executor(None, _get_summary)

    async def clear_traffic_data(
        self,
        buyer_id: Optional[str] = None,
        days_to_keep: int = 30,
    ) -> int:
        """Clear old traffic data.

        Args:
            buyer_id: Optional filter to clear only specific buyer's data.
            days_to_keep: Number of days of data to retain.

        Returns:
            Number of records deleted.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _clear_traffic():
                query = "DELETE FROM rtb_traffic WHERE date < date('now', ?)"
                params: list = [f"-{days_to_keep} days"]

                if buyer_id:
                    query += " AND buyer_id = ?"
                    params.append(buyer_id)

                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _clear_traffic)

    # ==================== Performance Metrics Methods ====================

    async def save_performance_metrics(
        self,
        metrics: list[PerformanceMetric],
    ) -> int:
        """Batch save performance metrics with UPSERT semantics.

        Uses INSERT OR REPLACE based on the unique constraint
        (creative_id, metric_date, geography, device_type, placement).

        Args:
            metrics: List of PerformanceMetric objects to save.

        Returns:
            Number of records saved.

        Example:
            >>> metrics = [
            ...     PerformanceMetric(
            ...         creative_id="12345",
            ...         metric_date="2025-11-29",
            ...         impressions=10000,
            ...         clicks=150,
            ...         spend_micros=5000000,  # $5.00
            ...         geography="US",
            ...         device_type="MOBILE",
            ...     )
            ... ]
            >>> count = await store.save_performance_metrics(metrics)
        """
        if not metrics:
            return 0

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _insert_metrics():
                count = 0
                for m in metrics:
                    # Compute CPM/CPC if not provided
                    cpm = m.cpm_micros
                    cpc = m.cpc_micros
                    if cpm is None and m.impressions > 0:
                        cpm = int((m.spend_micros / m.impressions) * 1000)
                    if cpc is None and m.clicks > 0:
                        cpc = int(m.spend_micros / m.clicks)

                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO performance_metrics (
                                creative_id, campaign_id, metric_date,
                                impressions, clicks, spend_micros,
                                cpm_micros, cpc_micros,
                                geography, device_type, placement,
                                updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """,
                            (
                                m.creative_id,
                                m.campaign_id,
                                m.metric_date,
                                m.impressions,
                                m.clicks,
                                m.spend_micros,
                                cpm,
                                cpc,
                                m.geography,
                                m.device_type,
                                m.placement,
                            ),
                        )
                        count += 1
                    except sqlite3.Error as e:
                        logger.warning(f"Failed to insert metric for {m.creative_id}: {e}")
                conn.commit()
                return count

            return await loop.run_in_executor(None, _insert_metrics)

    async def get_performance_metrics(
        self,
        creative_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        geography: Optional[str] = None,
        device_type: Optional[str] = None,
        limit: int = 1000,
    ) -> list[PerformanceMetric]:
        """Query performance metrics with filters.

        Args:
            creative_id: Filter by creative ID.
            campaign_id: Filter by campaign ID.
            start_date: Filter by start date (inclusive, YYYY-MM-DD).
            end_date: Filter by end date (inclusive, YYYY-MM-DD).
            geography: Filter by country code.
            device_type: Filter by device type.
            limit: Maximum number of results.

        Returns:
            List of PerformanceMetric objects.
        """
        conditions = []
        params: list = []

        if creative_id:
            conditions.append("creative_id = ?")
            params.append(creative_id)
        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)
        if start_date:
            conditions.append("metric_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("metric_date <= ?")
            params.append(end_date)
        if geography:
            conditions.append("geography = ?")
            params.append(geography)
        if device_type:
            conditions.append("device_type = ?")
            params.append(device_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT * FROM performance_metrics
                    WHERE {where_clause}
                    ORDER BY metric_date DESC, creative_id
                    LIMIT ?
                    """,
                    params,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            PerformanceMetric(
                id=row["id"],
                creative_id=row["creative_id"],
                campaign_id=row["campaign_id"],
                metric_date=row["metric_date"],
                impressions=row["impressions"],
                clicks=row["clicks"],
                spend_micros=row["spend_micros"],
                cpm_micros=row["cpm_micros"],
                cpc_micros=row["cpc_micros"],
                geography=row["geography"],
                device_type=row["device_type"],
                placement=row["placement"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def get_creative_performance_summary(
        self,
        creative_id: str,
        days: int = 30,
    ) -> dict:
        """Get aggregated performance summary for a creative.

        Args:
            creative_id: The creative ID.
            days: Number of days to aggregate.

        Returns:
            Dictionary with aggregated metrics.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT
                        SUM(impressions) as total_impressions,
                        SUM(clicks) as total_clicks,
                        SUM(spend_micros) as total_spend_micros,
                        CASE WHEN SUM(impressions) > 0
                             THEN CAST(SUM(spend_micros) * 1000.0 / SUM(impressions) AS INTEGER)
                             ELSE NULL END as avg_cpm_micros,
                        CASE WHEN SUM(clicks) > 0
                             THEN CAST(SUM(spend_micros) * 1.0 / SUM(clicks) AS INTEGER)
                             ELSE NULL END as avg_cpc_micros,
                        CASE WHEN SUM(impressions) > 0
                             THEN CAST(SUM(clicks) * 100.0 / SUM(impressions) AS REAL)
                             ELSE NULL END as ctr_percent,
                        COUNT(DISTINCT metric_date) as days_with_data,
                        MIN(metric_date) as earliest_date,
                        MAX(metric_date) as latest_date
                    FROM performance_metrics
                    WHERE creative_id = ?
                      AND metric_date >= date('now', ?)
                    """,
                    (creative_id, f"-{days} days"),
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return {}

            result = await loop.run_in_executor(None, _query)
            return result or {}

    async def update_campaign_performance_cache(
        self,
        campaign_id: str,
    ) -> None:
        """Update cached performance aggregates for a campaign.

        Computes and stores spend_7d, spend_30d, total_impressions,
        total_clicks, avg_cpm, and avg_cpc on the campaigns table.

        Args:
            campaign_id: The campaign ID to update.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _update_cache():
                # Get 7-day spend
                cursor = conn.execute(
                    """
                    SELECT SUM(spend_micros) as spend
                    FROM performance_metrics
                    WHERE campaign_id = ?
                      AND metric_date >= date('now', '-7 days')
                    """,
                    (campaign_id,),
                )
                spend_7d = cursor.fetchone()["spend"] or 0

                # Get 30-day spend
                cursor = conn.execute(
                    """
                    SELECT SUM(spend_micros) as spend
                    FROM performance_metrics
                    WHERE campaign_id = ?
                      AND metric_date >= date('now', '-30 days')
                    """,
                    (campaign_id,),
                )
                spend_30d = cursor.fetchone()["spend"] or 0

                # Get totals and averages
                cursor = conn.execute(
                    """
                    SELECT
                        SUM(impressions) as total_impressions,
                        SUM(clicks) as total_clicks,
                        CASE WHEN SUM(impressions) > 0
                             THEN CAST(SUM(spend_micros) * 1000.0 / SUM(impressions) AS INTEGER)
                             ELSE NULL END as avg_cpm_micros,
                        CASE WHEN SUM(clicks) > 0
                             THEN CAST(SUM(spend_micros) * 1.0 / SUM(clicks) AS INTEGER)
                             ELSE NULL END as avg_cpc_micros
                    FROM performance_metrics
                    WHERE campaign_id = ?
                    """,
                    (campaign_id,),
                )
                row = cursor.fetchone()

                # Update campaign record
                conn.execute(
                    """
                    UPDATE campaigns SET
                        spend_7d_micros = ?,
                        spend_30d_micros = ?,
                        total_impressions = ?,
                        total_clicks = ?,
                        avg_cpm_micros = ?,
                        avg_cpc_micros = ?,
                        perf_updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        spend_7d,
                        spend_30d,
                        row["total_impressions"] or 0,
                        row["total_clicks"] or 0,
                        row["avg_cpm_micros"],
                        row["avg_cpc_micros"],
                        campaign_id,
                    ),
                )
                conn.commit()

            await loop.run_in_executor(None, _update_cache)

    async def clear_old_performance_data(
        self,
        days_to_keep: int = 90,
    ) -> int:
        """Clear old performance data beyond retention period.

        Args:
            days_to_keep: Number of days of data to retain.

        Returns:
            Number of records deleted.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _clear_old():
                cursor = conn.execute(
                    "DELETE FROM performance_metrics WHERE metric_date < date('now', ?)",
                    (f"-{days_to_keep} days",),
                )
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _clear_old)
