CREATE TABLE IF NOT EXISTS config_size_daily (
    metric_date TEXT NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, creative_size)
);

CREATE TABLE IF NOT EXISTS config_geo_daily (
    metric_date TEXT NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, country)
);

CREATE TABLE IF NOT EXISTS config_publisher_daily (
    metric_date TEXT NOT NULL,
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
    metric_date TEXT NOT NULL,
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
