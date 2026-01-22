-- Postgres schema for precomputed daily aggregates
-- Mirrors SQLite precompute tables with equivalent indexes

CREATE TABLE IF NOT EXISTS home_seat_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    bids BIGINT DEFAULT 0,
    successful_responses BIGINT DEFAULT 0,
    bid_requests BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id)
);

CREATE TABLE IF NOT EXISTS home_publisher_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    publisher_name TEXT,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    bids BIGINT DEFAULT 0,
    successful_responses BIGINT DEFAULT 0,
    bid_requests BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, publisher_id)
);

CREATE TABLE IF NOT EXISTS home_geo_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    bids BIGINT DEFAULT 0,
    successful_responses BIGINT DEFAULT 0,
    bid_requests BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, country)
);

CREATE TABLE IF NOT EXISTS home_config_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    bids_in_auction BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id)
);

CREATE TABLE IF NOT EXISTS home_size_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, creative_size)
);

CREATE INDEX IF NOT EXISTS idx_home_seat_date ON home_seat_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_pub_date ON home_publisher_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_geo_date ON home_geo_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_config_date ON home_config_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_home_size_date ON home_size_daily(metric_date);

CREATE TABLE IF NOT EXISTS rtb_funnel_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    bids BIGINT DEFAULT 0,
    successful_responses BIGINT DEFAULT 0,
    bid_requests BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id)
);

CREATE TABLE IF NOT EXISTS rtb_publisher_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    publisher_name TEXT,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    bids BIGINT DEFAULT 0,
    successful_responses BIGINT DEFAULT 0,
    bid_requests BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, publisher_id)
);

CREATE TABLE IF NOT EXISTS rtb_geo_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    bids BIGINT DEFAULT 0,
    successful_responses BIGINT DEFAULT 0,
    bid_requests BIGINT DEFAULT 0,
    auctions_won BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, country)
);

CREATE TABLE IF NOT EXISTS rtb_app_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_id TEXT,
    billing_id TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
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
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
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
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
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
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, creative_id)
);

CREATE INDEX IF NOT EXISTS idx_rtb_funnel_date ON rtb_funnel_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_publisher_date ON rtb_publisher_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_geo_date ON rtb_geo_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_app_date ON rtb_app_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_app_name ON rtb_app_daily(app_name);
CREATE INDEX IF NOT EXISTS idx_rtb_app_billing ON rtb_app_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_rtb_app_size_name ON rtb_app_size_daily(app_name);
CREATE INDEX IF NOT EXISTS idx_rtb_app_country_name ON rtb_app_country_daily(app_name);
CREATE INDEX IF NOT EXISTS idx_rtb_app_creative_name ON rtb_app_creative_daily(app_name);

CREATE TABLE IF NOT EXISTS config_size_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, creative_size)
);

CREATE TABLE IF NOT EXISTS config_geo_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, country)
);

CREATE TABLE IF NOT EXISTS config_publisher_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    publisher_name TEXT,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, publisher_id)
);

CREATE TABLE IF NOT EXISTS config_creative_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    creative_id TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, creative_id)
);

CREATE INDEX IF NOT EXISTS idx_cfg_size_date ON config_size_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_cfg_size_billing ON config_size_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_cfg_geo_date ON config_geo_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_cfg_geo_billing ON config_geo_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_cfg_pub_date ON config_publisher_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_cfg_pub_billing ON config_publisher_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_cfg_creative_date ON config_creative_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_cfg_creative_billing ON config_creative_daily(billing_id);
