"""SQLite storage backend for creative data.

This module provides local SQLite storage for creative metadata,
campaigns, and clustering results.

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
    seat_name: Optional[str] = None
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
class ServiceAccount:
    """Service account record for multi-account support.

    Attributes:
        id: UUID for the service account.
        client_email: Service account email (unique identifier from Google).
        project_id: Google Cloud project ID.
        display_name: User-friendly name for the account.
        credentials_path: Path to the JSON credentials file.
        is_active: Whether the account is active.
        created_at: Record creation timestamp.
        last_used: Timestamp of last API call using this account.
    """

    id: str
    client_email: str
    project_id: Optional[str] = None
    display_name: Optional[str] = None
    credentials_path: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None


@dataclass
class BuyerSeat:
    """Buyer seat record for multi-seat account support.

    Attributes:
        buyer_id: Unique buyer account ID (e.g., "456" from buyers/456).
        bidder_id: Parent bidder account ID.
        service_account_id: Foreign key to service_accounts table.
        display_name: Human-readable name for the buyer seat.
        active: Whether the seat is active for syncing.
        creative_count: Number of creatives associated with this seat.
        last_synced: Timestamp of last successful sync.
        created_at: Record creation timestamp.
    """

    buyer_id: str
    bidder_id: str
    service_account_id: Optional[str] = None
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

    CREATE TABLE IF NOT EXISTS service_accounts (
        id TEXT PRIMARY KEY,
        client_email TEXT UNIQUE NOT NULL,
        project_id TEXT,
        display_name TEXT,
        credentials_path TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS buyer_seats (
        buyer_id TEXT PRIMARY KEY,
        bidder_id TEXT NOT NULL,
        service_account_id TEXT,
        display_name TEXT,
        active INTEGER DEFAULT 1,
        creative_count INTEGER DEFAULT 0,
        last_synced TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(bidder_id, buyer_id),
        FOREIGN KEY (service_account_id) REFERENCES service_accounts(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_service_accounts_email ON service_accounts(client_email);
    CREATE INDEX IF NOT EXISTS idx_buyer_seats_service_account ON buyer_seats(service_account_id);
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

    -- Campaign-Creative junction table for manual clustering
    CREATE TABLE IF NOT EXISTS campaign_creatives (
        campaign_id TEXT NOT NULL,
        creative_id TEXT NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (campaign_id, creative_id),
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
        FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_campaign_creatives_campaign ON campaign_creatives(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_campaign_creatives_creative ON campaign_creatives(creative_id);

    -- Thumbnail generation status tracking
    CREATE TABLE IF NOT EXISTS thumbnail_status (
        creative_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        error_reason TEXT,
        video_url TEXT,
        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_thumbnail_status_status ON thumbnail_status(status);
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
        # Phase 8.4: Seats table (for CSV import seat extraction)
        """CREATE TABLE IF NOT EXISTS seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            billing_id TEXT UNIQUE NOT NULL,
            account_name TEXT,
            account_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_seats_billing ON seats(billing_id)",
        # Phase 8.4: Video metrics table (separate from performance for funnel data)
        """CREATE TABLE IF NOT EXISTS video_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            performance_id INTEGER UNIQUE REFERENCES performance_metrics(id) ON DELETE CASCADE,
            video_starts INTEGER DEFAULT 0,
            video_q1 INTEGER DEFAULT 0,
            video_q2 INTEGER DEFAULT 0,
            video_q3 INTEGER DEFAULT 0,
            video_completions INTEGER DEFAULT 0,
            vast_errors INTEGER DEFAULT 0,
            engaged_views INTEGER DEFAULT 0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_video_perf ON video_metrics(performance_id)",
        # Phase 8.4: Daily creative summary (for fast queries after aggregation)
        """CREATE TABLE IF NOT EXISTS daily_creative_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seat_id INTEGER,
            creative_id TEXT NOT NULL,
            date DATE NOT NULL,
            total_queries INTEGER DEFAULT 0,
            total_impressions INTEGER DEFAULT 0,
            total_clicks INTEGER DEFAULT 0,
            total_spend REAL DEFAULT 0,
            total_video_starts INTEGER,
            total_video_completions INTEGER,
            win_rate REAL,
            ctr REAL,
            cpm REAL,
            completion_rate REAL,
            unique_geos INTEGER,
            unique_apps INTEGER,
            UNIQUE(seat_id, creative_id, date)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_summary_seat_date ON daily_creative_summary(seat_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_summary_creative ON daily_creative_summary(creative_id)",
        # Phase 8.4: Retention config table
        """CREATE TABLE IF NOT EXISTS retention_config (
            id INTEGER PRIMARY KEY,
            seat_id INTEGER REFERENCES seats(id),
            raw_retention_days INTEGER DEFAULT 90,
            summary_retention_days INTEGER DEFAULT 365,
            auto_aggregate_after_days INTEGER DEFAULT 30,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        # Phase 8.4: Add seat_id and reached_queries to performance_metrics
        "ALTER TABLE performance_metrics ADD COLUMN seat_id INTEGER",
        "ALTER TABLE performance_metrics ADD COLUMN reached_queries INTEGER DEFAULT 0",
        "CREATE INDEX IF NOT EXISTS idx_perf_seat_date ON performance_metrics(seat_id, metric_date)",
        # Phase 8.4: Update apps table with quality fields
        "ALTER TABLE apps ADD COLUMN fraud_score REAL DEFAULT 0",
        "ALTER TABLE apps ADD COLUMN quality_tier TEXT DEFAULT 'unknown'",
        # Phase 8.4: Create apps table if not exists (from earlier migration)
        """CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id TEXT UNIQUE,
            app_name TEXT,
            platform TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fraud_score REAL DEFAULT 0,
            quality_tier TEXT DEFAULT 'unknown'
        )""",
        "CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(app_name)",
        # Phase 8.4: Create publishers table if not exists
        """CREATE TABLE IF NOT EXISTS publishers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            publisher_id TEXT UNIQUE,
            publisher_name TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        # Phase 9: AI Campaign Clustering tables
        """CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seat_id INTEGER REFERENCES seats(id),
            name TEXT NOT NULL,
            description TEXT,
            ai_generated BOOLEAN DEFAULT TRUE,
            ai_confidence REAL,
            clustering_method TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_campaigns_seat ON campaigns(seat_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)",
        # Phase 9: Creative-Campaign mapping
        """CREATE TABLE IF NOT EXISTS creative_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creative_id TEXT NOT NULL REFERENCES creatives(id),
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
            manually_assigned BOOLEAN DEFAULT FALSE,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_by TEXT,
            UNIQUE(creative_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_cc_campaign ON creative_campaigns(campaign_id)",
        "CREATE INDEX IF NOT EXISTS idx_cc_creative ON creative_campaigns(creative_id)",
        # Phase 9: Campaign daily summary for aggregated performance
        """CREATE TABLE IF NOT EXISTS campaign_daily_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
            date DATE NOT NULL,
            total_creatives INTEGER DEFAULT 0,
            active_creatives INTEGER DEFAULT 0,
            total_queries INTEGER DEFAULT 0,
            total_impressions INTEGER DEFAULT 0,
            total_clicks INTEGER DEFAULT 0,
            total_spend REAL DEFAULT 0,
            total_video_starts INTEGER,
            total_video_completions INTEGER,
            avg_win_rate REAL,
            avg_ctr REAL,
            avg_cpm REAL,
            unique_geos INTEGER,
            top_geo_id INTEGER,
            top_geo_spend REAL,
            UNIQUE(campaign_id, date)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_cds_campaign_date ON campaign_daily_summary(campaign_id, date DESC)",
        # Import anomalies table for fraud detection
        """CREATE TABLE IF NOT EXISTS import_anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id TEXT,
            row_number INTEGER,
            anomaly_type TEXT NOT NULL,
            creative_id TEXT,
            app_id TEXT,
            app_name TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_type ON import_anomalies(anomaly_type)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_app ON import_anomalies(app_id)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_creative ON import_anomalies(creative_id)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_import ON import_anomalies(import_id)",
        # Phase 10.4: Thumbnail generation status tracking
        """CREATE TABLE IF NOT EXISTS thumbnail_status (
            creative_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            error_reason TEXT,
            video_url TEXT,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
        )""",
        "CREATE INDEX IF NOT EXISTS idx_thumbnail_status_status ON thumbnail_status(status)",
        # Phase 25: Recommendations table for Cat-Scan analytics
        """CREATE TABLE IF NOT EXISTS recommendations (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            severity TEXT NOT NULL,
            confidence TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            evidence_json TEXT,
            impact_json TEXT,
            actions_json TEXT,
            affected_creatives TEXT,
            affected_campaigns TEXT,
            status TEXT DEFAULT 'new',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            resolved_at TIMESTAMP,
            resolution_notes TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_rec_type ON recommendations(type)",
        "CREATE INDEX IF NOT EXISTS idx_rec_severity ON recommendations(severity)",
        "CREATE INDEX IF NOT EXISTS idx_rec_status ON recommendations(status)",
        "CREATE INDEX IF NOT EXISTS idx_rec_generated ON recommendations(generated_at DESC)",
        # Phase 23: RTB Endpoints table (from bidders.endpoints API)
        """CREATE TABLE IF NOT EXISTS rtb_endpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bidder_id TEXT NOT NULL,
            endpoint_id TEXT NOT NULL,
            url TEXT NOT NULL,
            maximum_qps INTEGER,
            trading_location TEXT,
            bid_protocol TEXT,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(bidder_id, endpoint_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_rtb_endpoints_bidder ON rtb_endpoints(bidder_id)",
        # Phase 23: Pretargeting Configs table (from bidders.pretargetingConfigs API)
        """CREATE TABLE IF NOT EXISTS pretargeting_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bidder_id TEXT NOT NULL,
            config_id TEXT NOT NULL,
            billing_id TEXT,
            display_name TEXT,
            user_name TEXT,
            state TEXT DEFAULT 'ACTIVE',
            included_formats TEXT,
            included_platforms TEXT,
            included_sizes TEXT,
            included_geos TEXT,
            excluded_geos TEXT,
            raw_config TEXT,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(bidder_id, config_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_pretargeting_bidder ON pretargeting_configs(bidder_id)",
        "CREATE INDEX IF NOT EXISTS idx_pretargeting_billing ON pretargeting_configs(billing_id)",
        # Phase 26: Import history table for tracking CSV uploads
        """CREATE TABLE IF NOT EXISTS import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL UNIQUE,
            filename TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            rows_read INTEGER DEFAULT 0,
            rows_imported INTEGER DEFAULT 0,
            rows_skipped INTEGER DEFAULT 0,
            rows_duplicate INTEGER DEFAULT 0,
            date_range_start DATE,
            date_range_end DATE,
            columns_found TEXT,
            columns_missing TEXT,
            total_reached INTEGER DEFAULT 0,
            total_impressions INTEGER DEFAULT 0,
            total_spend_usd REAL DEFAULT 0,
            status TEXT DEFAULT 'complete',
            error_message TEXT,
            file_size_bytes INTEGER DEFAULT 0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_import_history_batch ON import_history(batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_import_history_date ON import_history(imported_at DESC)",
        # Phase 26: Daily upload summary table for upload tracking UI
        """CREATE TABLE IF NOT EXISTS daily_upload_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_date DATE NOT NULL UNIQUE,
            total_uploads INTEGER DEFAULT 0,
            successful_uploads INTEGER DEFAULT 0,
            failed_uploads INTEGER DEFAULT 0,
            total_rows_written INTEGER DEFAULT 0,
            total_file_size_bytes INTEGER DEFAULT 0,
            avg_rows_per_upload REAL DEFAULT 0,
            min_rows INTEGER,
            max_rows INTEGER,
            has_anomaly INTEGER DEFAULT 0,
            anomaly_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_daily_upload_date ON daily_upload_summary(upload_date DESC)",
        # Phase 26: Track when creatives are first seen (for "newly uploaded" feature)
        "ALTER TABLE creatives ADD COLUMN first_seen_at TIMESTAMP",
        "ALTER TABLE creatives ADD COLUMN first_import_batch_id TEXT",
        "CREATE INDEX IF NOT EXISTS idx_creatives_first_seen ON creatives(first_seen_at DESC)",
        # Phase 26: Pretargeting settings history table for tracking changes
        """CREATE TABLE IF NOT EXISTS pretargeting_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id TEXT NOT NULL,
            bidder_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            field_changed TEXT,
            old_value TEXT,
            new_value TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            changed_by TEXT,
            change_source TEXT DEFAULT 'api_sync',
            raw_config_snapshot TEXT,
            FOREIGN KEY (config_id) REFERENCES pretargeting_configs(config_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_pretargeting_history_config ON pretargeting_history(config_id)",
        "CREATE INDEX IF NOT EXISTS idx_pretargeting_history_date ON pretargeting_history(changed_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_pretargeting_history_bidder ON pretargeting_history(bidder_id)",
        # Phase 27: Multi-account support - service accounts table
        """CREATE TABLE IF NOT EXISTS service_accounts (
            id TEXT PRIMARY KEY,
            client_email TEXT UNIQUE NOT NULL,
            project_id TEXT,
            display_name TEXT,
            credentials_path TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_service_accounts_email ON service_accounts(client_email)",
        # Phase 27: Add service_account_id to buyer_seats
        "ALTER TABLE buyer_seats ADD COLUMN service_account_id TEXT REFERENCES service_accounts(id)",
        "CREATE INDEX IF NOT EXISTS idx_buyer_seats_service_account ON buyer_seats(service_account_id)",
    ]

    def __init__(self, db_path: str | Path = "~/.catscan/catscan.db") -> None:
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
                    """
                    SELECT c.*, bs.display_name as seat_name
                    FROM creatives c
                    LEFT JOIN buyer_seats bs ON c.account_id = bs.buyer_id
                    WHERE c.id = ?
                    """,
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
            seat_name=row_dict.get("seat_name"),
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
            conditions.append("c.account_id = ?")
            params.append(buyer_id)
        if campaign_id:
            conditions.append("c.campaign_id = ?")
            params.append(campaign_id)
        if cluster_id:
            conditions.append("c.cluster_id = ?")
            params.append(cluster_id)
        if format:
            conditions.append("c.format = ?")
            params.append(format)
        if canonical_size:
            conditions.append("c.canonical_size = ?")
            params.append(canonical_size)
        if size_category:
            conditions.append("c.size_category = ?")
            params.append(size_category)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT c.*, bs.display_name as seat_name
                    FROM creatives c
                    LEFT JOIN buyer_seats bs ON c.account_id = bs.buyer_id
                    WHERE {where_clause}
                    ORDER BY c.updated_at DESC
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
                        buyer_id, bidder_id, service_account_id, display_name, active,
                        creative_count, last_synced, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                        (SELECT created_at FROM buyer_seats WHERE buyer_id = ?),
                        CURRENT_TIMESTAMP
                    ))
                    """,
                    (
                        seat.buyer_id,
                        seat.bidder_id,
                        seat.service_account_id,
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
            conditions.append("bs.bidder_id = ?")
            params.append(bidder_id)
        if active_only:
            conditions.append("bs.active = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Use LEFT JOIN to get dynamic creative count from creatives.account_id
                cursor = conn.execute(
                    f"""
                    SELECT bs.buyer_id, bs.bidder_id, bs.service_account_id, bs.display_name, bs.active,
                           COALESCE(c.cnt, 0) as creative_count,
                           bs.last_synced, bs.created_at
                    FROM buyer_seats bs
                    LEFT JOIN (
                        SELECT account_id, COUNT(*) as cnt
                        FROM creatives
                        GROUP BY account_id
                    ) c ON c.account_id = bs.buyer_id
                    WHERE {where_clause}
                    ORDER BY bs.display_name, bs.buyer_id
                    """,
                    params,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            BuyerSeat(
                buyer_id=row[0],
                bidder_id=row[1],
                service_account_id=row[2],
                display_name=row[3],
                active=bool(row[4]),
                creative_count=row[5] or 0,
                last_synced=row[6],
                created_at=row[7],
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
                    SELECT buyer_id, bidder_id, service_account_id, display_name, active,
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
                    service_account_id=row[2],
                    display_name=row[3],
                    active=bool(row[4]),
                    creative_count=row[5] or 0,
                    last_synced=row[6],
                    created_at=row[7],
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

    async def populate_buyer_seats_from_creatives(self) -> int:
        """Populate buyer_seats table from existing creatives.

        Creates buyer_seat records for each unique account_id found in creatives
        that doesn't already exist in buyer_seats.

        Returns:
            Number of buyer seats created.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _populate():
                # Get unique account_ids from creatives that aren't already in buyer_seats
                cursor = conn.execute("""
                    SELECT DISTINCT c.account_id, c.advertiser_name
                    FROM creatives c
                    WHERE c.account_id IS NOT NULL
                    AND c.account_id NOT IN (SELECT buyer_id FROM buyer_seats)
                """)
                accounts = cursor.fetchall()

                created = 0
                for account_id, advertiser_name in accounts:
                    # Use advertiser_name as display_name if available
                    display_name = advertiser_name or f"Account {account_id}"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO buyer_seats
                        (buyer_id, bidder_id, display_name, active, creative_count, created_at)
                        VALUES (?, ?, ?, 1, 0, CURRENT_TIMESTAMP)
                        """,
                        (account_id, account_id, display_name),
                    )
                    created += 1

                conn.commit()
                return created

            return await loop.run_in_executor(None, _populate)

    async def update_buyer_seat_display_name(
        self, buyer_id: str, display_name: str
    ) -> bool:
        """Update the display name for a buyer seat.

        Args:
            buyer_id: The buyer ID to update.
            display_name: The new display name.

        Returns:
            True if updated, False if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _update():
                cursor = conn.execute(
                    """
                    UPDATE buyer_seats
                    SET display_name = ?
                    WHERE buyer_id = ?
                    """,
                    (display_name, buyer_id),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _update)

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

    # ==================== Service Account Methods ====================

    async def save_service_account(self, account: ServiceAccount) -> None:
        """Insert or update a service account.

        Args:
            account: The ServiceAccount to save.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO service_accounts (
                        id, client_email, project_id, display_name,
                        credentials_path, is_active, created_at, last_used
                    ) VALUES (?, ?, ?, ?, ?, ?, COALESCE(
                        (SELECT created_at FROM service_accounts WHERE id = ?),
                        CURRENT_TIMESTAMP
                    ), ?)
                    """,
                    (
                        account.id,
                        account.client_email,
                        account.project_id,
                        account.display_name,
                        account.credentials_path,
                        1 if account.is_active else 0,
                        account.id,
                        account.last_used,
                    ),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def get_service_accounts(
        self,
        active_only: bool = False,
    ) -> list[ServiceAccount]:
        """Get all service accounts.

        Args:
            active_only: If True, only return active accounts.

        Returns:
            List of ServiceAccount objects.
        """
        conditions = []
        if active_only:
            conditions.append("is_active = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT id, client_email, project_id, display_name,
                           credentials_path, is_active, created_at, last_used
                    FROM service_accounts
                    WHERE {where_clause}
                    ORDER BY display_name, client_email
                    """,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            ServiceAccount(
                id=row[0],
                client_email=row[1],
                project_id=row[2],
                display_name=row[3],
                credentials_path=row[4],
                is_active=bool(row[5]),
                created_at=row[6],
                last_used=row[7],
            )
            for row in rows
        ]

    async def get_service_account(self, account_id: str) -> Optional[ServiceAccount]:
        """Get a specific service account.

        Args:
            account_id: The service account ID (UUID).

        Returns:
            ServiceAccount object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT id, client_email, project_id, display_name,
                           credentials_path, is_active, created_at, last_used
                    FROM service_accounts
                    WHERE id = ?
                    """,
                    (account_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return ServiceAccount(
                    id=row[0],
                    client_email=row[1],
                    project_id=row[2],
                    display_name=row[3],
                    credentials_path=row[4],
                    is_active=bool(row[5]),
                    created_at=row[6],
                    last_used=row[7],
                )
            return None

    async def get_service_account_by_email(self, client_email: str) -> Optional[ServiceAccount]:
        """Get a service account by its client email.

        Args:
            client_email: The service account email address.

        Returns:
            ServiceAccount object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT id, client_email, project_id, display_name,
                           credentials_path, is_active, created_at, last_used
                    FROM service_accounts
                    WHERE client_email = ?
                    """,
                    (client_email,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return ServiceAccount(
                    id=row[0],
                    client_email=row[1],
                    project_id=row[2],
                    display_name=row[3],
                    credentials_path=row[4],
                    is_active=bool(row[5]),
                    created_at=row[6],
                    last_used=row[7],
                )
            return None

    async def delete_service_account(self, account_id: str) -> bool:
        """Delete a service account and its credentials file.

        Note: This also sets service_account_id to NULL for any buyer_seats
        that referenced this account (due to ON DELETE SET NULL).

        Args:
            account_id: The service account ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _delete():
                cursor = conn.execute(
                    "DELETE FROM service_accounts WHERE id = ?",
                    (account_id,),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _delete)

    async def update_service_account_last_used(self, account_id: str) -> None:
        """Update last_used timestamp for a service account.

        Args:
            account_id: The service account ID.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    UPDATE service_accounts
                    SET last_used = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (account_id,),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def link_buyer_seat_to_service_account(
        self,
        buyer_id: str,
        service_account_id: str,
    ) -> None:
        """Link a buyer seat to a service account.

        Args:
            buyer_id: The buyer seat ID.
            service_account_id: The service account ID to link.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    UPDATE buyer_seats
                    SET service_account_id = ?
                    WHERE buyer_id = ?
                    """,
                    (service_account_id, buyer_id),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

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

                    # IMPORTANT: Convert NULLs to 'UNKNOWN' for unique constraint columns
                    # SQLite treats NULL != NULL, so NULLs cause duplicate rows
                    geography = m.geography or "UNKNOWN"
                    device_type = m.device_type or "UNKNOWN"
                    placement = m.placement or "UNKNOWN"

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
                                geography,
                                device_type,
                                placement,
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

    async def save_import_anomalies(
        self,
        import_id: str,
        anomalies: list[dict],
    ) -> int:
        """Store anomalies from import for later analysis.

        Args:
            import_id: Unique identifier for the import batch.
            anomalies: List of anomaly dictionaries with type, row, details.

        Returns:
            Number of anomalies saved.
        """
        if not anomalies:
            return 0

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _insert_anomalies():
                count = 0
                for a in anomalies:
                    try:
                        details = a.get("details", {})
                        conn.execute(
                            """
                            INSERT INTO import_anomalies
                            (import_id, row_number, anomaly_type, creative_id, app_id, app_name, details)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                import_id,
                                a.get("row"),
                                a.get("type"),
                                str(details.get("creative_id")) if details.get("creative_id") else None,
                                details.get("app_id"),
                                details.get("app_name"),
                                json.dumps(details),
                            ),
                        )
                        count += 1
                    except sqlite3.Error as e:
                        logger.warning(f"Failed to insert anomaly: {e}")
                conn.commit()
                return count

            return await loop.run_in_executor(None, _insert_anomalies)

    async def get_fraud_apps(self, limit: int = 50) -> list[dict]:
        """Get apps with most fraud signals.

        Args:
            limit: Maximum number of apps to return.

        Returns:
            List of app dictionaries with anomaly counts.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT
                        app_id,
                        app_name,
                        COUNT(*) as anomaly_count,
                        COUNT(DISTINCT anomaly_type) as anomaly_types,
                        GROUP_CONCAT(DISTINCT anomaly_type) as types_list
                    FROM import_anomalies
                    WHERE anomaly_type IN ('clicks_exceed_impressions', 'extremely_high_ctr', 'zero_impressions_with_spend')
                    AND app_id IS NOT NULL
                    GROUP BY app_id
                    ORDER BY anomaly_count DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            {
                "app_id": row["app_id"],
                "app_name": row["app_name"],
                "anomaly_count": row["anomaly_count"],
                "anomaly_types": row["anomaly_types"],
                "types_list": row["types_list"].split(",") if row["types_list"] else [],
            }
            for row in rows
        ]

    async def get_anomaly_summary(self) -> dict:
        """Get summary of all import anomalies.

        Returns:
            Dictionary with anomaly type counts.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT
                        anomaly_type,
                        COUNT(*) as count
                    FROM import_anomalies
                    GROUP BY anomaly_type
                    ORDER BY count DESC
                    """
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return {row["anomaly_type"]: row["count"] for row in rows}

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
                    FROM rtb_daily
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

    async def clear_old_rtb_daily(
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

    # =========================================================================
    # Campaign Clustering Methods
    # =========================================================================

    async def create_campaign(self, name: str, creative_ids: list[str] | None = None) -> dict:
        """Create a new campaign with optional creatives.

        Args:
            name: Campaign name
            creative_ids: Optional list of creative IDs to assign

        Returns:
            Created campaign dict with id, name, creative_ids
        """
        import uuid

        campaign_id = str(uuid.uuid4())[:8]

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _create():
                conn.execute(
                    """
                    INSERT INTO campaigns (id, name, created_at, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (campaign_id, name),
                )

                if creative_ids:
                    for cid in creative_ids:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO creative_campaigns (creative_id, campaign_id)
                            VALUES (?, ?)
                            """,
                            (cid, campaign_id),
                        )

                conn.commit()
                return {
                    "id": campaign_id,
                    "name": name,
                    "creative_ids": creative_ids or [],
                }

            return await loop.run_in_executor(None, _create)

    async def list_campaigns(self) -> list[dict]:
        """List all campaigns with their creative IDs.

        Returns:
            List of campaign dicts with id, name, creative_ids, created_at
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _list():
                cursor = conn.execute(
                    """
                    SELECT c.id, c.name, c.created_at, c.updated_at
                    FROM campaigns c
                    ORDER BY c.updated_at DESC
                    """
                )
                campaigns = []
                for row in cursor.fetchall():
                    # Get creative IDs for this campaign
                    cid_cursor = conn.execute(
                        "SELECT creative_id FROM creative_campaigns WHERE campaign_id = ?",
                        (row["id"],),
                    )
                    creative_ids = [r["creative_id"] for r in cid_cursor.fetchall()]

                    campaigns.append({
                        "id": row["id"],
                        "name": row["name"],
                        "creative_ids": creative_ids,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    })
                return campaigns

            return await loop.run_in_executor(None, _list)

    async def get_campaign(self, campaign_id: str) -> dict | None:
        """Get a single campaign by ID.

        Args:
            campaign_id: Campaign ID

        Returns:
            Campaign dict or None if not found
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get():
                cursor = conn.execute(
                    "SELECT id, name, created_at, updated_at FROM campaigns WHERE id = ?",
                    (campaign_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                # Get creative IDs
                cid_cursor = conn.execute(
                    "SELECT creative_id FROM creative_campaigns WHERE campaign_id = ?",
                    (campaign_id,),
                )
                creative_ids = [r["creative_id"] for r in cid_cursor.fetchall()]

                return {
                    "id": row["id"],
                    "name": row["name"],
                    "creative_ids": creative_ids,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }

            return await loop.run_in_executor(None, _get)

    async def update_campaign(
        self,
        campaign_id: str,
        name: str | None = None,
        creative_ids: list[str] | None = None,
    ) -> dict | None:
        """Update a campaign's name and/or creative assignments.

        Args:
            campaign_id: Campaign ID
            name: New name (optional)
            creative_ids: New list of creative IDs (replaces existing)

        Returns:
            Updated campaign dict or None if not found
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _update():
                # Check if campaign exists
                cursor = conn.execute(
                    "SELECT id FROM campaigns WHERE id = ?", (campaign_id,)
                )
                if not cursor.fetchone():
                    return None

                # Update name if provided
                if name is not None:
                    conn.execute(
                        "UPDATE campaigns SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (name, campaign_id),
                    )

                # Update creative assignments if provided
                if creative_ids is not None:
                    # Remove existing assignments
                    conn.execute(
                        "DELETE FROM creative_campaigns WHERE campaign_id = ?",
                        (campaign_id,),
                    )
                    # Add new assignments
                    for cid in creative_ids:
                        conn.execute(
                            "INSERT OR REPLACE INTO creative_campaigns (creative_id, campaign_id) VALUES (?, ?)",
                            (cid, campaign_id),
                        )
                    # Update timestamp
                    conn.execute(
                        "UPDATE campaigns SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (campaign_id,),
                    )

                conn.commit()

                # Fetch updated campaign
                cursor = conn.execute(
                    "SELECT id, name, created_at, updated_at FROM campaigns WHERE id = ?",
                    (campaign_id,),
                )
                row = cursor.fetchone()
                cid_cursor = conn.execute(
                    "SELECT creative_id FROM creative_campaigns WHERE campaign_id = ?",
                    (campaign_id,),
                )
                current_creative_ids = [r["creative_id"] for r in cid_cursor.fetchall()]

                return {
                    "id": row["id"],
                    "name": row["name"],
                    "creative_ids": current_creative_ids,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }

            return await loop.run_in_executor(None, _update)

    async def delete_campaign(self, campaign_id: str) -> bool:
        """Delete a campaign (creatives become unclustered).

        Args:
            campaign_id: Campaign ID

        Returns:
            True if deleted, False if not found
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _delete():
                cursor = conn.execute(
                    "DELETE FROM campaigns WHERE id = ?", (campaign_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _delete)

    async def get_unclustered_creative_ids(self, buyer_id: str | None = None) -> list[str]:
        """Get IDs of creatives not assigned to any campaign.

        Args:
            buyer_id: Optional buyer ID to filter by

        Returns:
            List of creative IDs
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_unclustered():
                if buyer_id:
                    cursor = conn.execute(
                        """
                        SELECT c.id
                        FROM creatives c
                        LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                        WHERE cc.campaign_id IS NULL
                          AND c.buyer_id = ?
                        ORDER BY c.updated_at DESC
                        """,
                        (buyer_id,)
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT c.id
                        FROM creatives c
                        LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                        WHERE cc.campaign_id IS NULL
                        ORDER BY c.updated_at DESC
                        """
                    )
                return [row["id"] for row in cursor.fetchall()]

            return await loop.run_in_executor(None, _get_unclustered)

    # =========================================================================
    # Thumbnail Status Methods (Phase 10.4)
    # =========================================================================

    async def record_thumbnail_status(
        self,
        creative_id: str,
        status: str,
        error_reason: str | None = None,
        video_url: str | None = None,
    ) -> None:
        """Record the thumbnail generation status for a creative.

        Args:
            creative_id: The creative ID
            status: Status value ('success', 'failed', 'pending')
            error_reason: Optional error reason ('url_expired', 'no_url', 'timeout', 'network_error', 'invalid_format')
            video_url: Optional video URL that was attempted (for debugging)
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _record():
                conn.execute(
                    """
                    INSERT INTO thumbnail_status (creative_id, status, error_reason, video_url, attempted_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(creative_id) DO UPDATE SET
                        status = excluded.status,
                        error_reason = excluded.error_reason,
                        video_url = excluded.video_url,
                        attempted_at = CURRENT_TIMESTAMP
                    """,
                    (creative_id, status, error_reason, video_url),
                )
                conn.commit()

            await loop.run_in_executor(None, _record)

    async def get_thumbnail_status(
        self, creative_id: str
    ) -> dict | None:
        """Get the thumbnail status for a single creative.

        Args:
            creative_id: The creative ID

        Returns:
            Dict with status info or None if not found
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get():
                cursor = conn.execute(
                    """
                    SELECT creative_id, status, error_reason, video_url, attempted_at
                    FROM thumbnail_status
                    WHERE creative_id = ?
                    """,
                    (creative_id,),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "creative_id": row["creative_id"],
                        "status": row["status"],
                        "error_reason": row["error_reason"],
                        "video_url": row["video_url"],
                        "attempted_at": row["attempted_at"],
                    }
                return None

            return await loop.run_in_executor(None, _get)

    async def get_thumbnail_statuses(
        self, creative_ids: list[str] | None = None
    ) -> dict[str, dict]:
        """Get thumbnail statuses for multiple creatives.

        Args:
            creative_ids: Optional list of creative IDs. If None, returns all.

        Returns:
            Dict mapping creative_id to status info
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_all():
                if creative_ids:
                    placeholders = ",".join("?" * len(creative_ids))
                    cursor = conn.execute(
                        f"""
                        SELECT creative_id, status, error_reason, video_url, thumbnail_url, attempted_at
                        FROM thumbnail_status
                        WHERE creative_id IN ({placeholders})
                        """,
                        creative_ids,
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT creative_id, status, error_reason, video_url, thumbnail_url, attempted_at
                        FROM thumbnail_status
                        """
                    )

                result = {}
                for row in cursor.fetchall():
                    result[row["creative_id"]] = {
                        "status": row["status"],
                        "error_reason": row["error_reason"],
                        "video_url": row["video_url"],
                        "thumbnail_url": row["thumbnail_url"],  # Phase 22: HTML thumbnails
                        "attempted_at": row["attempted_at"],
                    }
                return result

            return await loop.run_in_executor(None, _get_all)

    async def get_video_creatives_needing_thumbnails(
        self, limit: int = 100, force_retry_failed: bool = False
    ) -> list[dict]:
        """Get video creatives that need thumbnail generation.

        Args:
            limit: Maximum number of creatives to return
            force_retry_failed: If True, include failed status for retry

        Returns:
            List of creative dicts with id, raw_data
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get():
                if force_retry_failed:
                    # Retry failed ones, skip successful
                    query = """
                        SELECT c.id, c.raw_data
                        FROM creatives c
                        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                        WHERE c.format = 'VIDEO'
                        AND (ts.status IS NULL OR ts.status = 'failed')
                        LIMIT ?
                    """
                else:
                    # Skip any that already have a status
                    query = """
                        SELECT c.id, c.raw_data
                        FROM creatives c
                        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                        WHERE c.format = 'VIDEO'
                        AND ts.status IS NULL
                        LIMIT ?
                    """

                cursor = conn.execute(query, (limit,))
                results = []
                for row in cursor.fetchall():
                    raw_data = row["raw_data"]
                    if raw_data:
                        try:
                            raw_data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            raw_data = {}
                    else:
                        raw_data = {}
                    results.append({
                        "id": row["id"],
                        "raw_data": raw_data,
                    })
                return results

            return await loop.run_in_executor(None, _get)

    async def get_thumbnail_stats(self) -> dict:
        """Get summary statistics for thumbnail generation.

        Returns:
            Dict with counts by status and error_reason
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_stats():
                # Count by status
                cursor = conn.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM thumbnail_status
                    GROUP BY status
                    """
                )
                status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

                # Count by error_reason (for failed)
                cursor = conn.execute(
                    """
                    SELECT error_reason, COUNT(*) as count
                    FROM thumbnail_status
                    WHERE status = 'failed'
                    GROUP BY error_reason
                    """
                )
                error_counts = {row["error_reason"] or "unknown": row["count"] for row in cursor.fetchall()}

                # Total video creatives
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM creatives WHERE format = 'VIDEO'"
                )
                total_videos = cursor.fetchone()["count"]

                return {
                    "total_videos": total_videos,
                    "status_counts": status_counts,
                    "error_counts": error_counts,
                    "success_count": status_counts.get("success", 0),
                    "failed_count": status_counts.get("failed", 0),
                    "pending_count": status_counts.get("pending", 0),
                    "unprocessed_count": total_videos - sum(status_counts.values()),
                }

            return await loop.run_in_executor(None, _get_stats)

    async def get_html_creatives_pending_thumbnails(
        self, limit: int = 100, force_retry_failed: bool = False
    ) -> list[dict]:
        """Get HTML creatives that need thumbnail extraction.

        Phase 22: HTML thumbnail extraction support.

        Args:
            limit: Maximum number of creatives to return.
            force_retry_failed: If True, include previously failed extractions.

        Returns:
            List of creatives with id, raw_data containing HTML snippet.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_pending():
                if force_retry_failed:
                    # Get HTML creatives without thumbnails or with failed status
                    query = """
                        SELECT c.id, c.raw_data
                        FROM creatives c
                        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                        WHERE c.format = 'HTML'
                        AND (ts.creative_id IS NULL OR ts.status = 'failed')
                        AND c.raw_data IS NOT NULL
                        AND c.raw_data != ''
                        LIMIT ?
                    """
                else:
                    # Only get HTML creatives that haven't been processed yet
                    query = """
                        SELECT c.id, c.raw_data
                        FROM creatives c
                        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                        WHERE c.format = 'HTML'
                        AND ts.creative_id IS NULL
                        AND c.raw_data IS NOT NULL
                        AND c.raw_data != ''
                        LIMIT ?
                    """
                cursor = conn.execute(query, (limit,))
                return [dict(row) for row in cursor.fetchall()]

            return await loop.run_in_executor(None, _get_pending)

    async def process_html_thumbnails(
        self, limit: int = 100, force_retry: bool = False
    ) -> dict:
        """Process HTML creatives to extract thumbnail URLs.

        Phase 22: HTML thumbnail extraction.

        Parses HTML snippets to find embedded image URLs and populates
        the thumbnail_status table with the extracted URLs.

        Args:
            limit: Maximum number of creatives to process.
            force_retry: If True, retry previously failed extractions.

        Returns:
            Dict with processing statistics.
        """
        from utils.html_thumbnail import extract_primary_image_url

        # Get pending HTML creatives
        pending = await self.get_html_creatives_pending_thumbnails(
            limit=limit, force_retry_failed=force_retry
        )

        if not pending:
            return {
                "processed": 0,
                "success": 0,
                "failed": 0,
                "no_image_found": 0,
                "message": "No HTML creatives pending thumbnail extraction"
            }

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _process_batch():
                import json
                from datetime import datetime

                success = 0
                failed = 0
                no_image = 0

                for creative in pending:
                    creative_id = creative["id"]
                    raw_data = creative["raw_data"]

                    try:
                        # Parse raw_data JSON to get HTML snippet
                        if isinstance(raw_data, str):
                            try:
                                data = json.loads(raw_data)
                                # Try nested html.snippet first, then fallback to other keys
                                html_data = data.get("html", {})
                                if isinstance(html_data, dict):
                                    html_snippet = html_data.get("snippet", "")
                                else:
                                    html_snippet = ""
                                # Fallback to top-level keys
                                if not html_snippet:
                                    html_snippet = data.get("html_snippet", "") or data.get("snippet", "") or ""
                            except json.JSONDecodeError:
                                # raw_data might be the HTML itself
                                html_snippet = raw_data
                        else:
                            html_snippet = str(raw_data) if raw_data else ""

                        # Extract image URL from HTML
                        image_url = extract_primary_image_url(html_snippet)

                        if image_url:
                            # Success - insert/update thumbnail_status
                            conn.execute("""
                                INSERT INTO thumbnail_status
                                (creative_id, status, thumbnail_url, created_at, updated_at)
                                VALUES (?, 'success', ?, ?, ?)
                                ON CONFLICT(creative_id) DO UPDATE SET
                                    status = 'success',
                                    thumbnail_url = excluded.thumbnail_url,
                                    updated_at = excluded.updated_at
                            """, (
                                creative_id,
                                image_url,
                                datetime.utcnow().isoformat(),
                                datetime.utcnow().isoformat()
                            ))
                            success += 1
                        else:
                            # No image found in HTML
                            conn.execute("""
                                INSERT INTO thumbnail_status
                                (creative_id, status, error_reason, created_at, updated_at)
                                VALUES (?, 'no_image', 'No image URL found in HTML snippet', ?, ?)
                                ON CONFLICT(creative_id) DO UPDATE SET
                                    status = 'no_image',
                                    error_reason = 'No image URL found in HTML snippet',
                                    updated_at = excluded.updated_at
                            """, (
                                creative_id,
                                datetime.utcnow().isoformat(),
                                datetime.utcnow().isoformat()
                            ))
                            no_image += 1

                    except Exception as e:
                        # Error processing
                        conn.execute("""
                            INSERT INTO thumbnail_status
                            (creative_id, status, error_reason, created_at, updated_at)
                            VALUES (?, 'failed', ?, ?, ?)
                            ON CONFLICT(creative_id) DO UPDATE SET
                                status = 'failed',
                                error_reason = excluded.error_reason,
                                updated_at = excluded.updated_at
                        """, (
                            creative_id,
                            str(e)[:500],
                            datetime.utcnow().isoformat(),
                            datetime.utcnow().isoformat()
                        ))
                        failed += 1

                conn.commit()

                return {
                    "processed": len(pending),
                    "success": success,
                    "failed": failed,
                    "no_image_found": no_image
                }

            return await loop.run_in_executor(None, _process_batch)
