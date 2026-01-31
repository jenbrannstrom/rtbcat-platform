CREATE TABLE IF NOT EXISTS rtb_funnel_daily (
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

CREATE TABLE IF NOT EXISTS rtb_publisher_daily (
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

CREATE TABLE IF NOT EXISTS rtb_geo_daily (
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

CREATE TABLE IF NOT EXISTS rtb_app_daily (
    metric_date TEXT NOT NULL,
    buyer_account_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_id TEXT,
    billing_id TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id)
);

CREATE TABLE IF NOT EXISTS rtb_app_size_daily (
    metric_date TEXT NOT NULL,
    buyer_account_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_id TEXT,
    billing_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    creative_format TEXT,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, creative_size, creative_format)
);

CREATE TABLE IF NOT EXISTS rtb_app_country_daily (
    metric_date TEXT NOT NULL,
    buyer_account_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_id TEXT,
    billing_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros INTEGER DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, country)
);

CREATE TABLE IF NOT EXISTS rtb_app_creative_daily (
    metric_date TEXT NOT NULL,
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
    spend_micros INTEGER DEFAULT 0,
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
