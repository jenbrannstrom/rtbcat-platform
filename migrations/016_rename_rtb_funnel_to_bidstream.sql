-- Migration 016: Rename rtb_funnel to rtb_bidstream
--
-- Rationale: "bidstream" better describes what this table contains:
-- the stream of bids through the RTB auction pipeline
-- (bid_requests -> bids -> bids_in_auction -> auctions_won -> impressions)
--
-- This is a non-destructive rename - data is preserved.

-- Rename the main table
ALTER TABLE rtb_funnel RENAME TO rtb_bidstream;

-- Rename indexes (SQLite automatically renames them with ALTER TABLE,
-- but we should create new ones with proper names for clarity)

-- Drop old indexes if they exist (SQLite may have auto-renamed them)
DROP INDEX IF EXISTS idx_rtb_funnel_date_country;
DROP INDEX IF EXISTS idx_rtb_funnel_buyer_account;
DROP INDEX IF EXISTS idx_rtb_funnel_publisher;
DROP INDEX IF EXISTS idx_rtb_funnel_join;
DROP INDEX IF EXISTS idx_rtb_bidstream_date_country;
DROP INDEX IF EXISTS idx_rtb_bidstream_buyer_account;
DROP INDEX IF EXISTS idx_rtb_bidstream_publisher;
DROP INDEX IF EXISTS idx_rtb_bidstream_join;

-- Create new indexes with proper names
CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_date_country
    ON rtb_bidstream(metric_date, country);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_buyer_account
    ON rtb_bidstream(buyer_account_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_publisher
    ON rtb_bidstream(publisher_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_join
    ON rtb_bidstream(metric_date, country, publisher_id);

-- Update any views that reference rtb_funnel
-- First drop them, then recreate with new table name

DROP VIEW IF EXISTS v_publisher_waste;
DROP VIEW IF EXISTS v_platform_efficiency;
DROP VIEW IF EXISTS v_hourly_patterns;

-- Recreate views with rtb_bidstream
CREATE VIEW IF NOT EXISTS v_publisher_waste AS
SELECT
    f.publisher_id,
    f.publisher_name,
    SUM(f.bid_requests) as bid_requests,
    SUM(f.auctions_won) as auctions_won,
    COALESCE(SUM(d.impressions), 0) as impressions,
    COALESCE(SUM(d.spend_micros), 0) as spend_micros,
    CASE
        WHEN SUM(f.bid_requests) > 0
        THEN 100.0 * (SUM(f.bid_requests) - SUM(f.auctions_won)) / SUM(f.bid_requests)
        ELSE 0
    END as waste_pct
FROM rtb_bidstream f
LEFT JOIN rtb_daily d ON f.metric_date = d.metric_date
    AND f.country = d.country
    AND f.publisher_id = d.publisher_id
WHERE f.publisher_id IS NOT NULL
GROUP BY f.publisher_id, f.publisher_name;

CREATE VIEW IF NOT EXISTS v_platform_efficiency AS
SELECT
    COALESCE(f.platform, d.platform, 'Unknown') as platform,
    SUM(f.bid_requests) as bid_requests,
    SUM(f.bids) as bids,
    SUM(f.auctions_won) as auctions_won,
    COALESCE(SUM(d.impressions), 0) as impressions,
    COALESCE(SUM(d.spend_micros), 0) as spend_micros,
    CASE
        WHEN SUM(f.bids) > 0
        THEN 100.0 * SUM(f.auctions_won) / SUM(f.bids)
        ELSE 0
    END as win_rate_pct
FROM rtb_bidstream f
LEFT JOIN rtb_daily d ON f.metric_date = d.metric_date
    AND f.country = d.country
    AND f.platform = d.platform
GROUP BY COALESCE(f.platform, d.platform, 'Unknown');

CREATE VIEW IF NOT EXISTS v_hourly_patterns AS
SELECT
    f.hour,
    SUM(f.bid_requests) as bid_requests,
    SUM(f.bids) as bids,
    SUM(f.auctions_won) as auctions_won,
    CASE
        WHEN SUM(f.bid_requests) > 0
        THEN 100.0 * SUM(f.bids) / SUM(f.bid_requests)
        ELSE 0
    END as bid_rate_pct,
    CASE
        WHEN SUM(f.bids) > 0
        THEN 100.0 * SUM(f.auctions_won) / SUM(f.bids)
        ELSE 0
    END as win_rate_pct
FROM rtb_bidstream f
WHERE f.hour IS NOT NULL
GROUP BY f.hour
ORDER BY f.hour;
