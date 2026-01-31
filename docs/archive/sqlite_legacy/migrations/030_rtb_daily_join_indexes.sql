-- Migration: Add indexes for config geo/publisher breakdown joins
-- Created: 2026-01-14
-- Description: Speed up rtb_daily self-join for config breakdowns

CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_creative_buyer
    ON rtb_daily(metric_date, creative_id, buyer_account_id);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_billing_buyer
    ON rtb_daily(billing_id, buyer_account_id);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_country_buyer
    ON rtb_daily(country, buyer_account_id);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_publisher_buyer
    ON rtb_daily(publisher_id, buyer_account_id);
