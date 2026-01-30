-- Migration 028: Add creative_size to config_creative_daily for size drilldown

ALTER TABLE config_creative_daily
    ADD COLUMN IF NOT EXISTS creative_size TEXT;

CREATE INDEX IF NOT EXISTS idx_cfg_creative_date_buyer_billing_size
    ON config_creative_daily(metric_date, buyer_account_id, billing_id, creative_size);
