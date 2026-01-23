-- PostgreSQL Schema for Cat-Scan Creative Intelligence
-- Mirrors storage/schema.py with PostgreSQL-specific types
-- Generated from SQLite schema - use TIMESTAMPTZ, JSONB, SERIAL

-- ============================================================================
-- CORE TABLES
-- ============================================================================

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
    raw_data JSONB,
    app_id TEXT,
    app_name TEXT,
    app_store TEXT,
    disapproval_reasons JSONB,
    serving_restrictions JSONB,
    detected_language TEXT,
    detected_language_code TEXT,
    language_confidence REAL,
    language_source TEXT,
    language_analyzed_at TIMESTAMPTZ,
    language_analysis_error TEXT,
    first_seen_at TIMESTAMPTZ,
    first_import_batch_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT DEFAULT 'google_ads',
    creative_count INTEGER DEFAULT 0,
    metadata JSONB,
    spend_7d_micros BIGINT DEFAULT 0,
    spend_30d_micros BIGINT DEFAULT 0,
    total_impressions BIGINT DEFAULT 0,
    total_clicks BIGINT DEFAULT 0,
    avg_cpm_micros INTEGER,
    avg_cpc_micros INTEGER,
    perf_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    creative_count INTEGER DEFAULT 0,
    centroid JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS service_accounts (
    id TEXT PRIMARY KEY,
    client_email TEXT UNIQUE NOT NULL,
    project_id TEXT,
    display_name TEXT,
    credentials_path TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS buyer_seats (
    buyer_id TEXT PRIMARY KEY,
    bidder_id TEXT NOT NULL,
    service_account_id TEXT REFERENCES service_accounts(id) ON DELETE SET NULL,
    display_name TEXT,
    active BOOLEAN DEFAULT TRUE,
    creative_count INTEGER DEFAULT 0,
    last_synced TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(bidder_id, buyer_id)
);

-- ============================================================================
-- RTB TRAFFIC AND PERFORMANCE
-- ============================================================================

CREATE TABLE IF NOT EXISTS rtb_traffic (
    id SERIAL PRIMARY KEY,
    buyer_id TEXT,
    canonical_size TEXT NOT NULL,
    raw_size TEXT NOT NULL,
    request_count INTEGER NOT NULL,
    date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(buyer_id, canonical_size, raw_size, date)
);

CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    creative_id TEXT NOT NULL REFERENCES creatives(id) ON DELETE CASCADE,
    campaign_id TEXT,
    metric_date DATE NOT NULL,
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    spend_micros BIGINT NOT NULL DEFAULT 0,
    cpm_micros INTEGER,
    cpc_micros INTEGER,
    geography TEXT,
    device_type TEXT,
    placement TEXT,
    seat_id INTEGER,
    reached_queries INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS video_metrics (
    id SERIAL PRIMARY KEY,
    performance_id INTEGER UNIQUE REFERENCES performance_metrics(id) ON DELETE CASCADE,
    video_starts INTEGER DEFAULT 0,
    video_q1 INTEGER DEFAULT 0,
    video_q2 INTEGER DEFAULT 0,
    video_q3 INTEGER DEFAULT 0,
    video_completions INTEGER DEFAULT 0,
    vast_errors INTEGER DEFAULT 0,
    engaged_views INTEGER DEFAULT 0
);

-- ============================================================================
-- SEATS AND APPS
-- ============================================================================

CREATE TABLE IF NOT EXISTS seats (
    id SERIAL PRIMARY KEY,
    billing_id TEXT UNIQUE NOT NULL,
    account_name TEXT,
    account_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS apps (
    id SERIAL PRIMARY KEY,
    app_id TEXT UNIQUE,
    app_name TEXT,
    platform TEXT,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    fraud_score REAL DEFAULT 0,
    quality_tier TEXT DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS publishers (
    id SERIAL PRIMARY KEY,
    publisher_id TEXT UNIQUE,
    publisher_name TEXT,
    first_seen TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- CAMPAIGN-CREATIVE RELATIONSHIPS
-- ============================================================================

CREATE TABLE IF NOT EXISTS campaign_creatives (
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    creative_id TEXT NOT NULL REFERENCES creatives(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (campaign_id, creative_id)
);

CREATE TABLE IF NOT EXISTS thumbnail_status (
    creative_id TEXT PRIMARY KEY REFERENCES creatives(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    error_reason TEXT,
    video_url TEXT,
    attempted_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- DAILY SUMMARIES (PRECOMPUTED)
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_creative_summary (
    id SERIAL PRIMARY KEY,
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

-- ============================================================================
-- HOME PAGE PRECOMPUTE TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS home_seat_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    bids INTEGER DEFAULT 0,
    successful_responses INTEGER DEFAULT 0,
    bid_requests INTEGER DEFAULT 0,
    auctions_won INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id)
);

CREATE TABLE IF NOT EXISTS home_publisher_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    publisher_name TEXT,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    bids INTEGER DEFAULT 0,
    successful_responses INTEGER DEFAULT 0,
    bid_requests INTEGER DEFAULT 0,
    auctions_won INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, publisher_id)
);

CREATE TABLE IF NOT EXISTS home_geo_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    bids INTEGER DEFAULT 0,
    successful_responses INTEGER DEFAULT 0,
    bid_requests INTEGER DEFAULT 0,
    auctions_won INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, country)
);

CREATE TABLE IF NOT EXISTS home_config_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    bids_in_auction INTEGER DEFAULT 0,
    auctions_won INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id)
);

CREATE TABLE IF NOT EXISTS home_size_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, creative_size)
);

-- ============================================================================
-- RTB PRECOMPUTE TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS rtb_funnel_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    bids INTEGER DEFAULT 0,
    successful_responses INTEGER DEFAULT 0,
    bid_requests INTEGER DEFAULT 0,
    auctions_won INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id)
);

CREATE TABLE IF NOT EXISTS rtb_publisher_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    publisher_name TEXT,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    bids INTEGER DEFAULT 0,
    successful_responses INTEGER DEFAULT 0,
    bid_requests INTEGER DEFAULT 0,
    auctions_won INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, publisher_id)
);

CREATE TABLE IF NOT EXISTS rtb_geo_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    bids INTEGER DEFAULT 0,
    successful_responses INTEGER DEFAULT 0,
    bid_requests INTEGER DEFAULT 0,
    auctions_won INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, country)
);

CREATE TABLE IF NOT EXISTS rtb_app_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_id TEXT,
    billing_id TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id)
);

CREATE TABLE IF NOT EXISTS rtb_app_size_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_id TEXT,
    billing_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    creative_format TEXT,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, creative_size, creative_format)
);

CREATE TABLE IF NOT EXISTS rtb_app_country_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_id TEXT,
    billing_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, country)
);

CREATE TABLE IF NOT EXISTS rtb_app_creative_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_id TEXT,
    billing_id TEXT NOT NULL,
    creative_id TEXT NOT NULL,
    creative_size TEXT,
    creative_format TEXT,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, creative_id)
);

-- ============================================================================
-- AI CAMPAIGNS AND RECOMMENDATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS ai_campaigns (
    id TEXT PRIMARY KEY,
    seat_id INTEGER REFERENCES seats(id),
    name TEXT NOT NULL,
    description TEXT,
    ai_generated BOOLEAN DEFAULT TRUE,
    ai_confidence REAL,
    clustering_method TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS creative_campaigns (
    id SERIAL PRIMARY KEY,
    creative_id TEXT NOT NULL REFERENCES creatives(id),
    campaign_id TEXT NOT NULL REFERENCES ai_campaigns(id),
    manually_assigned BOOLEAN DEFAULT FALSE,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by TEXT,
    UNIQUE(creative_id)
);

CREATE TABLE IF NOT EXISTS campaign_daily_summary (
    id SERIAL PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    evidence_json JSONB,
    impact_json JSONB,
    actions_json JSONB,
    affected_creatives JSONB,
    affected_campaigns JSONB,
    status TEXT DEFAULT 'new',
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT
);

-- ============================================================================
-- IMPORT AND ANOMALY TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS import_anomalies (
    id SERIAL PRIMARY KEY,
    import_id TEXT,
    row_number INTEGER,
    anomaly_type TEXT NOT NULL,
    creative_id TEXT,
    app_id TEXT,
    app_name TEXT,
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS import_history (
    id SERIAL PRIMARY KEY,
    batch_id TEXT NOT NULL UNIQUE,
    filename TEXT,
    imported_at TIMESTAMPTZ DEFAULT NOW(),
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

CREATE TABLE IF NOT EXISTS daily_upload_summary (
    id SERIAL PRIMARY KEY,
    upload_date DATE NOT NULL UNIQUE,
    total_uploads INTEGER DEFAULT 0,
    successful_uploads INTEGER DEFAULT 0,
    failed_uploads INTEGER DEFAULT 0,
    total_rows_written INTEGER DEFAULT 0,
    total_file_size_bytes BIGINT DEFAULT 0,
    avg_rows_per_upload REAL DEFAULT 0,
    min_rows INTEGER,
    max_rows INTEGER,
    has_anomaly BOOLEAN DEFAULT FALSE,
    anomaly_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- RTB ENDPOINTS AND PRETARGETING
-- ============================================================================

CREATE TABLE IF NOT EXISTS rtb_endpoints (
    id SERIAL PRIMARY KEY,
    bidder_id TEXT NOT NULL,
    endpoint_id TEXT NOT NULL,
    url TEXT NOT NULL,
    maximum_qps INTEGER,
    trading_location TEXT,
    bid_protocol TEXT,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(bidder_id, endpoint_id)
);

CREATE TABLE IF NOT EXISTS pretargeting_configs (
    id SERIAL PRIMARY KEY,
    bidder_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    billing_id TEXT,
    display_name TEXT,
    user_name TEXT,
    state TEXT DEFAULT 'ACTIVE',
    included_formats JSONB,
    included_platforms JSONB,
    included_sizes JSONB,
    included_geos JSONB,
    excluded_geos JSONB,
    included_operating_systems JSONB,
    raw_config JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(bidder_id, config_id)
);

CREATE TABLE IF NOT EXISTS pretargeting_history (
    id SERIAL PRIMARY KEY,
    config_id TEXT NOT NULL,
    bidder_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    changed_by TEXT,
    change_source TEXT DEFAULT 'api_sync',
    raw_config_snapshot JSONB
);

CREATE TABLE IF NOT EXISTS pretargeting_snapshots (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    snapshot_name TEXT,
    snapshot_type TEXT DEFAULT 'manual',
    included_formats JSONB,
    included_platforms JSONB,
    included_sizes JSONB,
    included_geos JSONB,
    excluded_geos JSONB,
    state TEXT,
    total_impressions BIGINT DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_spend_usd REAL DEFAULT 0,
    total_reached_queries BIGINT DEFAULT 0,
    days_tracked INTEGER DEFAULT 0,
    avg_daily_impressions REAL,
    avg_daily_spend_usd REAL,
    ctr_pct REAL,
    cpm_usd REAL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS snapshot_comparisons (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    comparison_name TEXT NOT NULL,
    before_snapshot_id INTEGER NOT NULL REFERENCES pretargeting_snapshots(id),
    after_snapshot_id INTEGER REFERENCES pretargeting_snapshots(id),
    before_start_date DATE,
    before_end_date DATE,
    after_start_date DATE,
    after_end_date DATE,
    impressions_delta BIGINT,
    impressions_delta_pct REAL,
    spend_delta_usd REAL,
    spend_delta_pct REAL,
    ctr_delta_pct REAL,
    cpm_delta_pct REAL,
    status TEXT DEFAULT 'in_progress',
    conclusion TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pretargeting_pending_changes (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value TEXT NOT NULL,
    reason TEXT,
    estimated_qps_impact REAL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT,
    status TEXT DEFAULT 'pending',
    applied_at TIMESTAMPTZ,
    applied_by TEXT
);

-- ============================================================================
-- RETENTION CONFIG
-- ============================================================================

CREATE TABLE IF NOT EXISTS retention_config (
    id SERIAL PRIMARY KEY,
    seat_id INTEGER REFERENCES seats(id),
    raw_retention_days INTEGER DEFAULT 90,
    summary_retention_days INTEGER DEFAULT 365,
    auto_aggregate_after_days INTEGER DEFAULT 30,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Creatives indexes
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
CREATE INDEX IF NOT EXISTS idx_creatives_app_id ON creatives(app_id);
CREATE INDEX IF NOT EXISTS idx_creatives_app_name ON creatives(app_name);

-- Service accounts and buyer seats
CREATE INDEX IF NOT EXISTS idx_service_accounts_email ON service_accounts(client_email);
CREATE INDEX IF NOT EXISTS idx_buyer_seats_service_account ON buyer_seats(service_account_id);
CREATE INDEX IF NOT EXISTS idx_buyer_seats_bidder ON buyer_seats(bidder_id);

-- RTB traffic
CREATE INDEX IF NOT EXISTS idx_rtb_traffic_buyer ON rtb_traffic(buyer_id);
CREATE INDEX IF NOT EXISTS idx_rtb_traffic_size ON rtb_traffic(canonical_size);
CREATE INDEX IF NOT EXISTS idx_rtb_traffic_date ON rtb_traffic(date);

-- Performance metrics
CREATE INDEX IF NOT EXISTS idx_perf_creative_date ON performance_metrics(creative_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_perf_campaign_date ON performance_metrics(campaign_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_perf_date_geo ON performance_metrics(metric_date, geography);
CREATE INDEX IF NOT EXISTS idx_perf_seat_date ON performance_metrics(seat_id, metric_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_perf_unique_daily ON performance_metrics(creative_id, metric_date, geography, device_type, placement);

-- Campaign-creative junctions
CREATE INDEX IF NOT EXISTS idx_campaign_creatives_campaign ON campaign_creatives(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_creatives_creative ON campaign_creatives(creative_id);

-- Thumbnail status
CREATE INDEX IF NOT EXISTS idx_thumbnail_status_status ON thumbnail_status(status);

-- Seats and apps
CREATE INDEX IF NOT EXISTS idx_seats_billing ON seats(billing_id);
CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(app_name);

-- Video metrics
CREATE INDEX IF NOT EXISTS idx_video_perf ON video_metrics(performance_id);

-- Daily summaries
CREATE INDEX IF NOT EXISTS idx_summary_seat_date ON daily_creative_summary(seat_id, date);
CREATE INDEX IF NOT EXISTS idx_summary_creative ON daily_creative_summary(creative_id);

-- Home precompute
CREATE INDEX IF NOT EXISTS idx_home_seat_date ON home_seat_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_pub_date ON home_publisher_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_geo_date ON home_geo_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_config_date ON home_config_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_size_date ON home_size_daily(metric_date);

-- RTB precompute
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_date ON rtb_funnel_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_publisher_date ON rtb_publisher_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_geo_date ON rtb_geo_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_app_date ON rtb_app_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_app_name ON rtb_app_daily(app_name);
CREATE INDEX IF NOT EXISTS idx_rtb_app_billing ON rtb_app_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_rtb_app_size_name ON rtb_app_size_daily(app_name);
CREATE INDEX IF NOT EXISTS idx_rtb_app_country_name ON rtb_app_country_daily(app_name);
CREATE INDEX IF NOT EXISTS idx_rtb_app_creative_name ON rtb_app_creative_daily(app_name);

-- AI campaigns
CREATE INDEX IF NOT EXISTS idx_ai_campaigns_seat ON ai_campaigns(seat_id);
CREATE INDEX IF NOT EXISTS idx_ai_campaigns_status ON ai_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_cc_campaign ON creative_campaigns(campaign_id);
CREATE INDEX IF NOT EXISTS idx_cc_creative ON creative_campaigns(creative_id);
CREATE INDEX IF NOT EXISTS idx_cds_campaign_date ON campaign_daily_summary(campaign_id, date DESC);

-- Recommendations
CREATE INDEX IF NOT EXISTS idx_rec_type ON recommendations(type);
CREATE INDEX IF NOT EXISTS idx_rec_severity ON recommendations(severity);
CREATE INDEX IF NOT EXISTS idx_rec_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_rec_generated ON recommendations(generated_at DESC);

-- Import tracking
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON import_anomalies(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_anomalies_app ON import_anomalies(app_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_creative ON import_anomalies(creative_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_import ON import_anomalies(import_id);
CREATE INDEX IF NOT EXISTS idx_import_history_batch ON import_history(batch_id);
CREATE INDEX IF NOT EXISTS idx_import_history_date ON import_history(imported_at DESC);
CREATE INDEX IF NOT EXISTS idx_daily_upload_date ON daily_upload_summary(upload_date DESC);

-- RTB endpoints and pretargeting
CREATE INDEX IF NOT EXISTS idx_rtb_endpoints_bidder ON rtb_endpoints(bidder_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_bidder ON pretargeting_configs(bidder_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_billing ON pretargeting_configs(billing_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_config ON pretargeting_history(config_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_date ON pretargeting_history(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_bidder ON pretargeting_history(bidder_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_billing ON pretargeting_snapshots(billing_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_created ON pretargeting_snapshots(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comparisons_billing ON snapshot_comparisons(billing_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_status ON snapshot_comparisons(status);
CREATE INDEX IF NOT EXISTS idx_pending_changes_billing ON pretargeting_pending_changes(billing_id);
CREATE INDEX IF NOT EXISTS idx_pending_changes_status ON pretargeting_pending_changes(status);
CREATE INDEX IF NOT EXISTS idx_pending_changes_created ON pretargeting_pending_changes(created_at DESC);
