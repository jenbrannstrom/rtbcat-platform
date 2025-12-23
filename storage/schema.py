"""Database schema and migrations for RTBcat Creative Intelligence.

This module contains the database schema definition and migration scripts
for SQLite storage.
"""

# Base schema - creates core tables and indexes
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
    first_seen_at TIMESTAMP,
    first_import_batch_id TEXT,
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
CREATE INDEX IF NOT EXISTS idx_creatives_first_seen ON creatives(first_seen_at DESC);
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
    seat_id INTEGER,
    reached_queries INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_perf_creative_date ON performance_metrics(creative_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_perf_campaign_date ON performance_metrics(campaign_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_perf_date_geo ON performance_metrics(metric_date, geography);
CREATE INDEX IF NOT EXISTS idx_perf_seat_date ON performance_metrics(seat_id, metric_date);
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

-- Seats table (for CSV import seat extraction)
CREATE TABLE IF NOT EXISTS seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT UNIQUE NOT NULL,
    account_name TEXT,
    account_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_seats_billing ON seats(billing_id);

-- Video metrics table (separate from performance for funnel data)
CREATE TABLE IF NOT EXISTS video_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    performance_id INTEGER UNIQUE REFERENCES performance_metrics(id) ON DELETE CASCADE,
    video_starts INTEGER DEFAULT 0,
    video_q1 INTEGER DEFAULT 0,
    video_q2 INTEGER DEFAULT 0,
    video_q3 INTEGER DEFAULT 0,
    video_completions INTEGER DEFAULT 0,
    vast_errors INTEGER DEFAULT 0,
    engaged_views INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_video_perf ON video_metrics(performance_id);

-- Daily creative summary (for fast queries after aggregation)
CREATE TABLE IF NOT EXISTS daily_creative_summary (
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
);

CREATE INDEX IF NOT EXISTS idx_summary_seat_date ON daily_creative_summary(seat_id, date);
CREATE INDEX IF NOT EXISTS idx_summary_creative ON daily_creative_summary(creative_id);

-- Retention config table
CREATE TABLE IF NOT EXISTS retention_config (
    id INTEGER PRIMARY KEY,
    seat_id INTEGER REFERENCES seats(id),
    raw_retention_days INTEGER DEFAULT 90,
    summary_retention_days INTEGER DEFAULT 365,
    auto_aggregate_after_days INTEGER DEFAULT 30,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Apps table
CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT UNIQUE,
    app_name TEXT,
    platform TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fraud_score REAL DEFAULT 0,
    quality_tier TEXT DEFAULT 'unknown'
);

CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(app_name);

-- Publishers table
CREATE TABLE IF NOT EXISTS publishers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    publisher_id TEXT UNIQUE,
    publisher_name TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI Campaign Clustering tables (Phase 9)
CREATE TABLE IF NOT EXISTS ai_campaigns (
    id TEXT PRIMARY KEY,
    seat_id INTEGER REFERENCES seats(id),
    name TEXT NOT NULL,
    description TEXT,
    ai_generated BOOLEAN DEFAULT TRUE,
    ai_confidence REAL,
    clustering_method TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_campaigns_seat ON ai_campaigns(seat_id);
CREATE INDEX IF NOT EXISTS idx_ai_campaigns_status ON ai_campaigns(status);

-- Creative-Campaign mapping for AI campaigns
CREATE TABLE IF NOT EXISTS creative_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id TEXT NOT NULL REFERENCES creatives(id),
    campaign_id TEXT NOT NULL REFERENCES ai_campaigns(id),
    manually_assigned BOOLEAN DEFAULT FALSE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by TEXT,
    UNIQUE(creative_id)
);

CREATE INDEX IF NOT EXISTS idx_cc_campaign ON creative_campaigns(campaign_id);
CREATE INDEX IF NOT EXISTS idx_cc_creative ON creative_campaigns(creative_id);

-- Campaign daily summary for aggregated performance
CREATE TABLE IF NOT EXISTS campaign_daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL REFERENCES ai_campaigns(id),
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
);

CREATE INDEX IF NOT EXISTS idx_cds_campaign_date ON campaign_daily_summary(campaign_id, date DESC);

-- Import anomalies table for fraud detection
CREATE TABLE IF NOT EXISTS import_anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id TEXT,
    row_number INTEGER,
    anomaly_type TEXT NOT NULL,
    creative_id TEXT,
    app_id TEXT,
    app_name TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_anomalies_type ON import_anomalies(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_anomalies_app ON import_anomalies(app_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_creative ON import_anomalies(creative_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_import ON import_anomalies(import_id);

-- Recommendations table for Cat-Scan analytics (Phase 25)
CREATE TABLE IF NOT EXISTS recommendations (
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
);

CREATE INDEX IF NOT EXISTS idx_rec_type ON recommendations(type);
CREATE INDEX IF NOT EXISTS idx_rec_severity ON recommendations(severity);
CREATE INDEX IF NOT EXISTS idx_rec_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_rec_generated ON recommendations(generated_at DESC);

-- RTB Endpoints table (Phase 23)
CREATE TABLE IF NOT EXISTS rtb_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bidder_id TEXT NOT NULL,
    endpoint_id TEXT NOT NULL,
    url TEXT NOT NULL,
    maximum_qps INTEGER,
    trading_location TEXT,
    bid_protocol TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bidder_id, endpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_rtb_endpoints_bidder ON rtb_endpoints(bidder_id);

-- Pretargeting Configs table (Phase 23)
CREATE TABLE IF NOT EXISTS pretargeting_configs (
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
);

CREATE INDEX IF NOT EXISTS idx_pretargeting_bidder ON pretargeting_configs(bidder_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_billing ON pretargeting_configs(billing_id);

-- Import history table for tracking CSV uploads (Phase 26)
CREATE TABLE IF NOT EXISTS import_history (
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
);

CREATE INDEX IF NOT EXISTS idx_import_history_batch ON import_history(batch_id);
CREATE INDEX IF NOT EXISTS idx_import_history_date ON import_history(imported_at DESC);

-- Daily upload summary table for upload tracking UI (Phase 26)
CREATE TABLE IF NOT EXISTS daily_upload_summary (
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
);

CREATE INDEX IF NOT EXISTS idx_daily_upload_date ON daily_upload_summary(upload_date DESC);

-- Pretargeting settings history table (Phase 26)
CREATE TABLE IF NOT EXISTS pretargeting_history (
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
);

CREATE INDEX IF NOT EXISTS idx_pretargeting_history_config ON pretargeting_history(config_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_date ON pretargeting_history(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_bidder ON pretargeting_history(bidder_id);
"""

# Migrations for existing databases - run in order, silently fail if already applied
MIGRATIONS = [
    # Early migrations (columns that may already exist in older DBs)
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

    # Buyer seats table
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

    # RTB traffic table
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

    # Performance metrics table
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

    # Campaign performance cache columns
    "ALTER TABLE campaigns ADD COLUMN spend_7d_micros INTEGER DEFAULT 0",
    "ALTER TABLE campaigns ADD COLUMN spend_30d_micros INTEGER DEFAULT 0",
    "ALTER TABLE campaigns ADD COLUMN total_impressions INTEGER DEFAULT 0",
    "ALTER TABLE campaigns ADD COLUMN total_clicks INTEGER DEFAULT 0",
    "ALTER TABLE campaigns ADD COLUMN avg_cpm_micros INTEGER",
    "ALTER TABLE campaigns ADD COLUMN avg_cpc_micros INTEGER",
    "ALTER TABLE campaigns ADD COLUMN perf_updated_at TIMESTAMP",

    # Seats table
    """CREATE TABLE IF NOT EXISTS seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        billing_id TEXT UNIQUE NOT NULL,
        account_name TEXT,
        account_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_seats_billing ON seats(billing_id)",

    # Video metrics
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

    # Daily creative summary
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

    # Retention config
    """CREATE TABLE IF NOT EXISTS retention_config (
        id INTEGER PRIMARY KEY,
        seat_id INTEGER REFERENCES seats(id),
        raw_retention_days INTEGER DEFAULT 90,
        summary_retention_days INTEGER DEFAULT 365,
        auto_aggregate_after_days INTEGER DEFAULT 30,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # Performance metrics additional columns
    "ALTER TABLE performance_metrics ADD COLUMN seat_id INTEGER",
    "ALTER TABLE performance_metrics ADD COLUMN reached_queries INTEGER DEFAULT 0",
    "CREATE INDEX IF NOT EXISTS idx_perf_seat_date ON performance_metrics(seat_id, metric_date)",

    # Apps table
    "ALTER TABLE apps ADD COLUMN fraud_score REAL DEFAULT 0",
    "ALTER TABLE apps ADD COLUMN quality_tier TEXT DEFAULT 'unknown'",
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

    # Publishers table
    """CREATE TABLE IF NOT EXISTS publishers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        publisher_id TEXT UNIQUE,
        publisher_name TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # AI Campaign tables (Phase 9)
    """CREATE TABLE IF NOT EXISTS ai_campaigns (
        id TEXT PRIMARY KEY,
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
    "CREATE INDEX IF NOT EXISTS idx_ai_campaigns_seat ON ai_campaigns(seat_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_campaigns_status ON ai_campaigns(status)",

    # Creative-Campaign mapping
    """CREATE TABLE IF NOT EXISTS creative_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creative_id TEXT NOT NULL REFERENCES creatives(id),
        campaign_id TEXT NOT NULL REFERENCES ai_campaigns(id),
        manually_assigned BOOLEAN DEFAULT FALSE,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_by TEXT,
        UNIQUE(creative_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_cc_campaign ON creative_campaigns(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_cc_creative ON creative_campaigns(creative_id)",

    # Campaign daily summary
    """CREATE TABLE IF NOT EXISTS campaign_daily_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT NOT NULL REFERENCES ai_campaigns(id),
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

    # Import anomalies
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

    # Thumbnail status
    """CREATE TABLE IF NOT EXISTS thumbnail_status (
        creative_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        error_reason TEXT,
        video_url TEXT,
        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
    )""",
    "CREATE INDEX IF NOT EXISTS idx_thumbnail_status_status ON thumbnail_status(status)",

    # Recommendations (Phase 25)
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

    # RTB Endpoints (Phase 23)
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

    # Pretargeting Configs (Phase 23)
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

    # Import history (Phase 26)
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

    # Daily upload summary (Phase 26)
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

    # Track when creatives are first seen (Phase 26)
    "ALTER TABLE creatives ADD COLUMN first_seen_at TIMESTAMP",
    "ALTER TABLE creatives ADD COLUMN first_import_batch_id TEXT",
    "CREATE INDEX IF NOT EXISTS idx_creatives_first_seen ON creatives(first_seen_at DESC)",

    # Pretargeting history (Phase 26)
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

    # Service accounts (Phase 27)
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

    # Link buyer_seats to service_accounts (Phase 27)
    "ALTER TABLE buyer_seats ADD COLUMN service_account_id TEXT REFERENCES service_accounts(id)",
    "CREATE INDEX IF NOT EXISTS idx_buyer_seats_service_account ON buyer_seats(service_account_id)",

    # Pretargeting snapshots (Phase 27)
    """CREATE TABLE IF NOT EXISTS pretargeting_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        billing_id TEXT NOT NULL,
        snapshot_name TEXT,
        snapshot_type TEXT DEFAULT 'manual',
        included_formats TEXT,
        included_platforms TEXT,
        included_sizes TEXT,
        included_geos TEXT,
        excluded_geos TEXT,
        state TEXT,
        total_impressions INTEGER DEFAULT 0,
        total_clicks INTEGER DEFAULT 0,
        total_spend_usd REAL DEFAULT 0,
        total_reached_queries INTEGER DEFAULT 0,
        days_tracked INTEGER DEFAULT 0,
        avg_daily_impressions REAL,
        avg_daily_spend_usd REAL,
        ctr_pct REAL,
        cpm_usd REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_billing ON pretargeting_snapshots(billing_id)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_created ON pretargeting_snapshots(created_at DESC)",

    # Snapshot comparisons for A/B testing (Phase 27)
    """CREATE TABLE IF NOT EXISTS snapshot_comparisons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        billing_id TEXT NOT NULL,
        comparison_name TEXT NOT NULL,
        before_snapshot_id INTEGER NOT NULL,
        after_snapshot_id INTEGER,
        before_start_date DATE,
        before_end_date DATE,
        after_start_date DATE,
        after_end_date DATE,
        impressions_delta INTEGER,
        impressions_delta_pct REAL,
        spend_delta_usd REAL,
        spend_delta_pct REAL,
        ctr_delta_pct REAL,
        cpm_delta_pct REAL,
        status TEXT DEFAULT 'in_progress',
        conclusion TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (before_snapshot_id) REFERENCES pretargeting_snapshots(id),
        FOREIGN KEY (after_snapshot_id) REFERENCES pretargeting_snapshots(id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_comparisons_billing ON snapshot_comparisons(billing_id)",
    "CREATE INDEX IF NOT EXISTS idx_comparisons_status ON snapshot_comparisons(status)",

    # Pretargeting pending changes (Phase 28) - local staging for config changes
    """CREATE TABLE IF NOT EXISTS pretargeting_pending_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        billing_id TEXT NOT NULL,
        config_id TEXT NOT NULL,
        change_type TEXT NOT NULL,
        field_name TEXT NOT NULL,
        value TEXT NOT NULL,
        reason TEXT,
        estimated_qps_impact REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT,
        status TEXT DEFAULT 'pending',
        applied_at TIMESTAMP,
        applied_by TEXT,
        FOREIGN KEY (billing_id) REFERENCES pretargeting_configs(billing_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_pending_changes_billing ON pretargeting_pending_changes(billing_id)",
    "CREATE INDEX IF NOT EXISTS idx_pending_changes_status ON pretargeting_pending_changes(status)",
    "CREATE INDEX IF NOT EXISTS idx_pending_changes_created ON pretargeting_pending_changes(created_at DESC)",
]
