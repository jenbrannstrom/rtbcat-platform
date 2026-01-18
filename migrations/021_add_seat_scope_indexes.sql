-- Migration: Add seat-scoped query indexes
-- Created: 2026-01-18
-- Description: Improve seat-scoped lookups for rtb_daily and rtb_bidstream

CREATE INDEX IF NOT EXISTS idx_rtb_daily_seat_date
    ON rtb_daily(buyer_account_id, billing_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_seat_creative_date
    ON rtb_daily(buyer_account_id, creative_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_seat_date
    ON rtb_bidstream(buyer_account_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_seat_country_date
    ON rtb_bidstream(buyer_account_id, country, metric_date);
