-- Migration 027: Schema alignment with DATA_MODEL.md
-- Adds missing raw fact tables, pretargeting_publishers, and BIGINT upgrades

-- ============================================================
-- 1. Create raw fact tables for QPS optimizer
-- ============================================================

-- rtb_daily: Creative-level performance (from bidsinauction + quality reports)
CREATE TABLE IF NOT EXISTS rtb_daily (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    creative_id TEXT,
    billing_id TEXT,
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
    bidder_id TEXT,
    report_type TEXT,  -- 'quality' or 'bidsinauction'
    hour INTEGER,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    video_starts BIGINT DEFAULT 0,
    video_first_quartile BIGINT DEFAULT 0,
    video_midpoint BIGINT DEFAULT 0,
    video_third_quartile BIGINT DEFAULT 0,
    video_completions BIGINT DEFAULT 0,
    vast_errors BIGINT DEFAULT 0,
    engaged_views BIGINT DEFAULT 0,
    active_view_measurable BIGINT DEFAULT 0,
    active_view_viewable BIGINT DEFAULT 0,
    bids BIGINT DEFAULT 0,
    bids_in_auction BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    gma_sdk INTEGER,
    buyer_sdk INTEGER,
    row_hash TEXT UNIQUE,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_date ON rtb_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_buyer ON rtb_daily(buyer_account_id);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_creative ON rtb_daily(creative_id);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_billing ON rtb_daily(billing_id);

-- rtb_bidstream: Bid funnel metrics (from pipeline/pipeline-geo reports)
CREATE TABLE IF NOT EXISTS rtb_bidstream (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    hour INTEGER,
    country TEXT,
    buyer_account_id TEXT,
    publisher_id TEXT,
    publisher_name TEXT,
    platform TEXT,
    environment TEXT,
    transaction_type TEXT,
    inventory_matches BIGINT DEFAULT 0,
    bid_requests BIGINT DEFAULT 0,
    successful_responses BIGINT DEFAULT 0,
    reached_queries BIGINT DEFAULT 0,
    bids BIGINT DEFAULT 0,
    bids_in_auction BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    bidder_id TEXT,
    report_type TEXT DEFAULT 'funnel',  -- 'funnel_publishers' or 'funnel_geo'
    row_hash TEXT UNIQUE,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_date ON rtb_bidstream(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_buyer ON rtb_bidstream(buyer_account_id);
CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_publisher ON rtb_bidstream(publisher_id);

-- rtb_bid_filtering: Bid rejection reasons
CREATE TABLE IF NOT EXISTS rtb_bid_filtering (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    country TEXT,
    buyer_account_id TEXT,
    filtering_reason TEXT,
    creative_id TEXT,
    bids BIGINT DEFAULT 0,
    bids_in_auction BIGINT DEFAULT 0,
    opportunity_cost_micros BIGINT DEFAULT 0,
    bidder_id TEXT,
    row_hash TEXT UNIQUE,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rtb_bid_filtering_date ON rtb_bid_filtering(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_bid_filtering_reason ON rtb_bid_filtering(filtering_reason);
CREATE INDEX IF NOT EXISTS idx_rtb_bid_filtering_creative ON rtb_bid_filtering(creative_id);

-- rtb_quality: Quality/IVT metrics per publisher
CREATE TABLE IF NOT EXISTS rtb_quality (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    publisher_id TEXT,
    publisher_name TEXT,
    country TEXT,
    buyer_account_id TEXT,
    impressions BIGINT DEFAULT 0,
    pre_filtered_impressions BIGINT DEFAULT 0,
    ivt_credited_impressions BIGINT DEFAULT 0,
    billed_impressions BIGINT DEFAULT 0,
    measurable_impressions BIGINT DEFAULT 0,
    viewable_impressions BIGINT DEFAULT 0,
    ivt_rate_pct REAL,
    viewability_pct REAL,
    bidder_id TEXT,
    row_hash TEXT UNIQUE,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rtb_quality_date ON rtb_quality(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_quality_publisher ON rtb_quality(publisher_id);

-- ============================================================
-- 2. Create pretargeting_publishers table for publisher list UI
-- ============================================================

CREATE TABLE IF NOT EXISTS pretargeting_publishers (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('BLACKLIST', 'WHITELIST')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending_add', 'pending_remove')),
    source TEXT NOT NULL DEFAULT 'api_sync' CHECK (source IN ('api_sync', 'user')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pretargeting_publishers_billing ON pretargeting_publishers(billing_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_publishers_publisher ON pretargeting_publishers(publisher_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_publishers_billing_mode ON pretargeting_publishers(billing_id, mode);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pretargeting_publishers_unique ON pretargeting_publishers(billing_id, publisher_id, mode);

-- ============================================================
-- 3. Upgrade INTEGER columns to BIGINT for aggregate counters
-- ============================================================

-- home_publisher_daily
ALTER TABLE home_publisher_daily ALTER COLUMN reached_queries TYPE BIGINT;
ALTER TABLE home_publisher_daily ALTER COLUMN impressions TYPE BIGINT;
ALTER TABLE home_publisher_daily ALTER COLUMN auctions_won TYPE BIGINT;

-- home_geo_daily
ALTER TABLE home_geo_daily ALTER COLUMN reached_queries TYPE BIGINT;
ALTER TABLE home_geo_daily ALTER COLUMN impressions TYPE BIGINT;
ALTER TABLE home_geo_daily ALTER COLUMN auctions_won TYPE BIGINT;

-- home_seat_daily
ALTER TABLE home_seat_daily ALTER COLUMN reached_queries TYPE BIGINT;
ALTER TABLE home_seat_daily ALTER COLUMN impressions TYPE BIGINT;

-- home_size_daily
ALTER TABLE home_size_daily ALTER COLUMN reached_queries TYPE BIGINT;
ALTER TABLE home_size_daily ALTER COLUMN impressions TYPE BIGINT;

-- home_config_daily
ALTER TABLE home_config_daily ALTER COLUMN reached_queries TYPE BIGINT;
ALTER TABLE home_config_daily ALTER COLUMN impressions TYPE BIGINT;
ALTER TABLE home_config_daily ALTER COLUMN bids_in_auction TYPE BIGINT;
ALTER TABLE home_config_daily ALTER COLUMN auctions_won TYPE BIGINT;

-- rtb_geo_daily
ALTER TABLE rtb_geo_daily ALTER COLUMN reached_queries TYPE BIGINT;
ALTER TABLE rtb_geo_daily ALTER COLUMN impressions TYPE BIGINT;
ALTER TABLE rtb_geo_daily ALTER COLUMN bids TYPE BIGINT;
ALTER TABLE rtb_geo_daily ALTER COLUMN successful_responses TYPE BIGINT;
ALTER TABLE rtb_geo_daily ALTER COLUMN bid_requests TYPE BIGINT;
ALTER TABLE rtb_geo_daily ALTER COLUMN auctions_won TYPE BIGINT;

-- rtb_funnel_daily
ALTER TABLE rtb_funnel_daily ALTER COLUMN reached_queries TYPE BIGINT;
ALTER TABLE rtb_funnel_daily ALTER COLUMN impressions TYPE BIGINT;
ALTER TABLE rtb_funnel_daily ALTER COLUMN bids TYPE BIGINT;
ALTER TABLE rtb_funnel_daily ALTER COLUMN successful_responses TYPE BIGINT;
ALTER TABLE rtb_funnel_daily ALTER COLUMN bid_requests TYPE BIGINT;
ALTER TABLE rtb_funnel_daily ALTER COLUMN auctions_won TYPE BIGINT;

-- ============================================================
-- 4. Record migration
-- ============================================================

INSERT INTO schema_migrations (version, applied_at, description)
VALUES ('027_schema_alignment', CURRENT_TIMESTAMP, 'Schema alignment with DATA_MODEL.md - raw fact tables, pretargeting_publishers, BIGINT upgrades')
ON CONFLICT (version) DO NOTHING;
