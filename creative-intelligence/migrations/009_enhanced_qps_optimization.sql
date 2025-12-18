-- Migration: Enhanced QPS Optimization Schema
-- Created: 2025-12-18
-- Description: Adds hourly granularity, platform/environment dimensions, bid filtering analysis,
--              and quality signals to enable AI-driven QPS optimization.
--
-- NEW CAPABILITIES:
--   1. Hourly patterns - correlate traffic patterns with wins
--   2. Platform/Environment - optimize by device type and app-vs-web
--   3. Bid filtering analysis - understand WHY bids fail
--   4. Quality signals - identify fraudulent/low-viewability publishers
--
-- These additions enable JOIN queries across rtb_funnel + rtb_daily + rtb_quality
-- for comprehensive QPS optimization.

-- ============================================================================
-- TASK 1: Enhance rtb_daily table
-- ============================================================================

-- Add hour column for hourly granularity
-- (platform, environment, publisher_domain already exist in initial schema)
ALTER TABLE rtb_daily ADD COLUMN hour INTEGER;

-- Create index for hourly queries
CREATE INDEX IF NOT EXISTS idx_rtb_daily_hour ON rtb_daily(hour);

-- Composite index for hourly pattern analysis
CREATE INDEX IF NOT EXISTS idx_rtb_daily_date_hour ON rtb_daily(metric_date, hour);

-- Index for platform optimization queries
CREATE INDEX IF NOT EXISTS idx_rtb_daily_platform ON rtb_daily(platform);

-- Index for environment optimization queries
CREATE INDEX IF NOT EXISTS idx_rtb_daily_environment ON rtb_daily(environment);

-- Composite index for joining with rtb_funnel
CREATE INDEX IF NOT EXISTS idx_rtb_daily_join ON rtb_daily(metric_date, country, publisher_id);

-- ============================================================================
-- TASK 2: Enhance rtb_funnel table
-- ============================================================================

-- Add platform for device type analysis
ALTER TABLE rtb_funnel ADD COLUMN platform TEXT;

-- Add environment for app-vs-web analysis
ALTER TABLE rtb_funnel ADD COLUMN environment TEXT;

-- Add transaction type for deal analysis (Open auction, Private auction, etc.)
ALTER TABLE rtb_funnel ADD COLUMN transaction_type TEXT;

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_platform ON rtb_funnel(platform);
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_environment ON rtb_funnel(environment);
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_transaction_type ON rtb_funnel(transaction_type);

-- Composite index for platform/environment analysis
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_platform_env ON rtb_funnel(metric_date, platform, environment);

-- ============================================================================
-- TASK 3: Create rtb_bid_filtering table
-- ============================================================================
-- Stores bid filtering reasons from Google AB "Bid filtering reason" report
-- This answers: "WHY are bids being filtered?"

CREATE TABLE IF NOT EXISTS rtb_bid_filtering (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,
    country TEXT,
    buyer_account_id TEXT,
    filtering_reason TEXT NOT NULL,      -- The filtering reason from Google AB
    creative_id TEXT,                     -- Optional - may not be available due to incompatibilities

    -- Metrics
    bids INTEGER DEFAULT 0,              -- Total bids filtered for this reason
    bids_in_auction INTEGER DEFAULT 0,   -- Bids that made it to auction
    opportunity_cost_micros INTEGER DEFAULT 0,  -- Estimated lost spend

    -- Tracking
    bidder_id TEXT,
    row_hash TEXT UNIQUE,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for bid filtering queries
CREATE INDEX IF NOT EXISTS idx_bid_filtering_date ON rtb_bid_filtering(metric_date);
CREATE INDEX IF NOT EXISTS idx_bid_filtering_reason ON rtb_bid_filtering(filtering_reason);
CREATE INDEX IF NOT EXISTS idx_bid_filtering_country ON rtb_bid_filtering(country);
CREATE INDEX IF NOT EXISTS idx_bid_filtering_date_reason ON rtb_bid_filtering(metric_date, filtering_reason);
CREATE INDEX IF NOT EXISTS idx_bid_filtering_batch ON rtb_bid_filtering(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_bid_filtering_bidder ON rtb_bid_filtering(bidder_id);

-- ============================================================================
-- TASK 4: Create rtb_quality table
-- ============================================================================
-- Stores fraud/viewability signals from Google AB "Quality" reports
-- This answers: "Which publishers have fraud or low viewability?"

CREATE TABLE IF NOT EXISTS rtb_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,
    publisher_id TEXT NOT NULL,
    publisher_name TEXT,
    country TEXT,

    -- Core metrics
    impressions INTEGER DEFAULT 0,

    -- Fraud/Quality metrics
    pre_filtered_impressions INTEGER DEFAULT 0,   -- Filtered before billing
    ivt_credited_impressions INTEGER DEFAULT 0,   -- Invalid traffic credited back
    billed_impressions INTEGER DEFAULT 0,         -- Actually billed

    -- Viewability metrics
    measurable_impressions INTEGER DEFAULT 0,     -- Active View could measure
    viewable_impressions INTEGER DEFAULT 0,       -- Actually viewable (MRC standard)

    -- Calculated during import or query
    ivt_rate_pct REAL,         -- ivt_credited / impressions * 100
    viewability_pct REAL,      -- viewable / measurable * 100

    -- Tracking
    bidder_id TEXT,
    row_hash TEXT UNIQUE,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for quality queries
CREATE INDEX IF NOT EXISTS idx_quality_date ON rtb_quality(metric_date);
CREATE INDEX IF NOT EXISTS idx_quality_publisher ON rtb_quality(publisher_id);
CREATE INDEX IF NOT EXISTS idx_quality_country ON rtb_quality(country);
CREATE INDEX IF NOT EXISTS idx_quality_date_publisher ON rtb_quality(metric_date, publisher_id);
CREATE INDEX IF NOT EXISTS idx_quality_ivt_rate ON rtb_quality(ivt_rate_pct);
CREATE INDEX IF NOT EXISTS idx_quality_viewability ON rtb_quality(viewability_pct);
CREATE INDEX IF NOT EXISTS idx_quality_batch ON rtb_quality(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_quality_bidder ON rtb_quality(bidder_id);

-- Composite index for joining with rtb_daily
CREATE INDEX IF NOT EXISTS idx_quality_join ON rtb_quality(metric_date, country, publisher_id);

-- ============================================================================
-- VIEWS FOR COMMON JOIN QUERIES
-- ============================================================================

-- View: Publisher waste ranking (JOIN funnel + daily)
CREATE VIEW IF NOT EXISTS v_publisher_waste AS
SELECT
    f.publisher_id,
    f.publisher_name,
    SUM(f.bid_requests) as bid_requests,
    SUM(f.auctions_won) as auctions_won,
    COALESCE(SUM(d.impressions), 0) as impressions,
    COALESCE(SUM(d.spend_micros), 0) as spend_micros,
    CASE
        WHEN SUM(f.bid_requests) > 0
        THEN 100.0 * (SUM(f.bid_requests) - SUM(f.auctions_won)) / SUM(f.bid_requests)
        ELSE 0
    END as waste_pct
FROM rtb_funnel f
LEFT JOIN rtb_daily d ON f.metric_date = d.metric_date
    AND f.country = d.country
    AND f.publisher_id = d.publisher_id
WHERE f.publisher_id IS NOT NULL
GROUP BY f.publisher_id, f.publisher_name;

-- View: Platform efficiency
CREATE VIEW IF NOT EXISTS v_platform_efficiency AS
SELECT
    COALESCE(f.platform, d.platform, 'Unknown') as platform,
    SUM(f.bid_requests) as bid_requests,
    SUM(f.bids) as bids,
    SUM(f.auctions_won) as auctions_won,
    COALESCE(SUM(d.impressions), 0) as impressions,
    COALESCE(SUM(d.spend_micros), 0) as spend_micros,
    CASE
        WHEN SUM(f.bids) > 0
        THEN 100.0 * SUM(f.auctions_won) / SUM(f.bids)
        ELSE 0
    END as win_rate_pct
FROM rtb_funnel f
LEFT JOIN rtb_daily d ON f.metric_date = d.metric_date
    AND f.country = d.country
    AND f.platform = d.platform
GROUP BY COALESCE(f.platform, d.platform, 'Unknown');

-- View: Hourly patterns
CREATE VIEW IF NOT EXISTS v_hourly_patterns AS
SELECT
    f.hour,
    SUM(f.bid_requests) as bid_requests,
    SUM(f.bids) as bids,
    SUM(f.auctions_won) as auctions_won,
    CASE
        WHEN SUM(f.bid_requests) > 0
        THEN 100.0 * SUM(f.bids) / SUM(f.bid_requests)
        ELSE 0
    END as bid_rate_pct,
    CASE
        WHEN SUM(f.bids) > 0
        THEN 100.0 * SUM(f.auctions_won) / SUM(f.bids)
        ELSE 0
    END as win_rate_pct
FROM rtb_funnel f
WHERE f.hour IS NOT NULL
GROUP BY f.hour
ORDER BY f.hour;
