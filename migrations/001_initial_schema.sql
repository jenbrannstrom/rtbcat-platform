-- Migration: Initial Schema
-- Created: 2025-12-10
-- Description: Baseline schema for RTBcat Creative Intelligence
-- Note: Uses IF NOT EXISTS to be idempotent for existing databases

-- Core tables
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT DEFAULT 'google_ads',
    creative_count INTEGER DEFAULT 0,
    metadata TEXT,
    spend_7d_micros INTEGER,
    spend_30d_micros INTEGER,
    total_impressions INTEGER,
    total_clicks INTEGER,
    avg_cpm_micros INTEGER,
    avg_cpc_micros INTEGER,
    perf_updated_at TIMESTAMP,
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
    UNIQUE(bidder_id, buyer_id)
);

-- Junction tables
CREATE TABLE IF NOT EXISTS campaign_creatives (
    campaign_id TEXT NOT NULL,
    creative_id TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (campaign_id, creative_id)
);

CREATE TABLE IF NOT EXISTS creative_campaigns (
    creative_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    PRIMARY KEY (creative_id, campaign_id)
);

-- Performance data
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RTB daily data (from CSV imports)
CREATE TABLE IF NOT EXISTS rtb_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,
    creative_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    creative_size TEXT,
    creative_format TEXT,
    country TEXT,
    platform TEXT,
    environment TEXT,
    app_id TEXT,
    app_name TEXT,
    publisher_id TEXT,
    publisher_name TEXT,
    publisher_domain TEXT,
    deal_id TEXT,
    deal_name TEXT,
    transaction_type TEXT,
    advertiser TEXT,
    buyer_account_id TEXT,
    buyer_account_name TEXT,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros INTEGER DEFAULT 0,
    video_starts INTEGER,
    video_first_quartile INTEGER,
    video_midpoint INTEGER,
    video_third_quartile INTEGER,
    video_completions INTEGER,
    vast_errors INTEGER,
    engaged_views INTEGER,
    active_view_measurable INTEGER,
    active_view_viewable INTEGER,
    gma_sdk INTEGER DEFAULT 0,
    buyer_sdk INTEGER DEFAULT 0,
    row_hash TEXT UNIQUE,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RTB traffic analysis
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

-- Thumbnail tracking
CREATE TABLE IF NOT EXISTS thumbnail_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL,
    thumbnail_url TEXT,
    video_url TEXT,
    error_reason TEXT,
    attempted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Core indexes
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

CREATE INDEX IF NOT EXISTS idx_service_accounts_email ON service_accounts(client_email);
CREATE INDEX IF NOT EXISTS idx_buyer_seats_service_account ON buyer_seats(service_account_id);
CREATE INDEX IF NOT EXISTS idx_buyer_seats_bidder ON buyer_seats(bidder_id);

CREATE INDEX IF NOT EXISTS idx_perf_creative_date ON performance_metrics(creative_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_perf_campaign_date ON performance_metrics(campaign_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_perf_date_geo ON performance_metrics(metric_date, geography);
CREATE INDEX IF NOT EXISTS idx_perf_seat_date ON performance_metrics(seat_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_date ON rtb_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_creative ON rtb_daily(creative_id);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_billing ON rtb_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_batch ON rtb_daily(import_batch_id);

CREATE INDEX IF NOT EXISTS idx_rtb_traffic_buyer ON rtb_traffic(buyer_id);
CREATE INDEX IF NOT EXISTS idx_rtb_traffic_size ON rtb_traffic(canonical_size);
CREATE INDEX IF NOT EXISTS idx_rtb_traffic_date ON rtb_traffic(date);

CREATE INDEX IF NOT EXISTS idx_thumbnail_creative ON thumbnail_status(creative_id);
CREATE INDEX IF NOT EXISTS idx_thumbnail_status ON thumbnail_status(status);
