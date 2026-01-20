-- Migration: Add date + dimension indexes for RTB tables
-- Created: 2026-02-10
-- Description: Speed up common date-scoped filters on rtb_daily and rtb_bidstream

CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_buyer
    ON rtb_daily(metric_date, buyer_account_id);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_billing
    ON rtb_daily(metric_date, billing_id);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_app
    ON rtb_daily(metric_date, app_id);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_creative
    ON rtb_daily(metric_date, creative_id);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_metric_country
    ON rtb_daily(metric_date, country);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_metric_buyer
    ON rtb_bidstream(metric_date, buyer_account_id);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_metric_publisher
    ON rtb_bidstream(metric_date, publisher_id);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_date_country
    ON rtb_bidstream(metric_date, country);
