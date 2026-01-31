-- Migration: Add composite indexes for precompute tables
-- Created: 2026-02-10
-- Description: Add composite indexes matching query predicates for home/config summaries

CREATE INDEX IF NOT EXISTS idx_home_seat_date_buyer
    ON home_seat_daily(metric_date, buyer_account_id);

CREATE INDEX IF NOT EXISTS idx_home_pub_date_buyer_pub
    ON home_publisher_daily(metric_date, buyer_account_id, publisher_id);

CREATE INDEX IF NOT EXISTS idx_home_geo_date_buyer_country
    ON home_geo_daily(metric_date, buyer_account_id, country);

CREATE INDEX IF NOT EXISTS idx_home_config_date_buyer_billing
    ON home_config_daily(metric_date, buyer_account_id, billing_id);

CREATE INDEX IF NOT EXISTS idx_home_size_date_buyer_size
    ON home_size_daily(metric_date, buyer_account_id, creative_size);

CREATE INDEX IF NOT EXISTS idx_cfg_size_date_buyer_billing_size
    ON config_size_daily(metric_date, buyer_account_id, billing_id, creative_size);

CREATE INDEX IF NOT EXISTS idx_cfg_geo_date_buyer_billing_country
    ON config_geo_daily(metric_date, buyer_account_id, billing_id, country);

CREATE INDEX IF NOT EXISTS idx_cfg_pub_date_buyer_billing_pub
    ON config_publisher_daily(metric_date, buyer_account_id, billing_id, publisher_id);

CREATE INDEX IF NOT EXISTS idx_cfg_creative_date_buyer_billing_creative
    ON config_creative_daily(metric_date, buyer_account_id, billing_id, creative_id);
