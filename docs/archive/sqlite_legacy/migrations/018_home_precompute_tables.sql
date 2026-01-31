-- Migration: Home page precompute tables
-- Created: 2026-01-14
-- Description: Daily aggregates for Home page performance summaries

CREATE TABLE IF NOT EXISTS home_seat_daily (
    metric_date TEXT NOT NULL,
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
    metric_date TEXT NOT NULL,
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
    metric_date TEXT NOT NULL,
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
    metric_date TEXT NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    bids_in_auction INTEGER DEFAULT 0,
    auctions_won INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id)
);

CREATE TABLE IF NOT EXISTS home_size_daily (
    metric_date TEXT NOT NULL,
    buyer_account_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, creative_size)
);

CREATE INDEX IF NOT EXISTS idx_home_seat_date ON home_seat_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_pub_date ON home_publisher_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_geo_date ON home_geo_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_config_date ON home_config_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_size_date ON home_size_daily(metric_date);
