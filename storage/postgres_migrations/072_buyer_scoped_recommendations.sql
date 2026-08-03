-- Migration 072: restore recommendations behind an explicit buyer boundary.
--
-- Legacy rows have no ownership provenance and cannot be assigned safely, so
-- remove them before making ownership mandatory. Recommendation generation is
-- deterministic and will recreate buyer-owned rows on the next request.

CREATE TABLE IF NOT EXISTS rtb_buyer_spend_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id)
);

CREATE TABLE IF NOT EXISTS rtb_platform_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_rtb_platform_date_buyer
    ON rtb_platform_daily(metric_date, buyer_account_id);

ALTER TABLE recommendations
    ADD COLUMN IF NOT EXISTS buyer_account_id TEXT;

DELETE FROM recommendations
WHERE buyer_account_id IS NULL OR buyer_account_id = '';

ALTER TABLE recommendations
    ALTER COLUMN buyer_account_id SET NOT NULL;

ALTER TABLE recommendations
    DROP CONSTRAINT IF EXISTS recommendations_pkey;

ALTER TABLE recommendations
    ADD PRIMARY KEY (buyer_account_id, id);

CREATE INDEX IF NOT EXISTS idx_recommendations_buyer_status
    ON recommendations(buyer_account_id, status);
