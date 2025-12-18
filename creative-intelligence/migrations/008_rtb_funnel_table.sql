-- Migration: RTB Funnel Table
-- Created: 2025-12-17
-- Description: New table for RTB funnel metrics (bid_requests, bids, auctions_won)
--              This data comes from a SEPARATE CSV due to Google AB field incompatibilities.
--
-- Google AB Limitation:
--   When you include "Bid requests", "Bids", "Bids in auction", etc., you CANNOT include:
--   - Mobile app ID
--   - Mobile app name
--   - Creative ID
--   - Creative size
--
--   This means users need MULTIPLE CSV exports to get full optimization data.

-- RTB Funnel data - aggregated by geo/hour (NO creative/app detail)
CREATE TABLE IF NOT EXISTS rtb_funnel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,
    hour INTEGER,  -- 0-23, optional
    country TEXT NOT NULL,
    buyer_account_id TEXT,

    -- Publisher fields (optional - depends on report variant)
    publisher_id TEXT,
    publisher_name TEXT,

    -- THE FUNNEL METRICS (the whole point of this table)
    inventory_matches INTEGER DEFAULT 0,      -- Matched pretargeting rules
    bid_requests INTEGER DEFAULT 0,           -- Total requests from Google
    successful_responses INTEGER DEFAULT 0,   -- Your bidder responded in time
    reached_queries INTEGER DEFAULT 0,        -- Actually reached your bidder
    bids INTEGER DEFAULT 0,                   -- Times you chose to bid
    bids_in_auction INTEGER DEFAULT 0,        -- Your bids entered auction
    auctions_won INTEGER DEFAULT 0,           -- You won!
    impressions INTEGER DEFAULT 0,            -- Rendered impressions
    clicks INTEGER DEFAULT 0,

    -- Tracking
    bidder_id TEXT,
    row_hash TEXT UNIQUE,
    import_batch_id TEXT,
    report_type TEXT DEFAULT 'funnel',  -- 'funnel' or 'funnel_with_publishers'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_date ON rtb_funnel(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_country ON rtb_funnel(country);
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_date_country ON rtb_funnel(metric_date, country);
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_publisher ON rtb_funnel(publisher_id);
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_bidder ON rtb_funnel(bidder_id);
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_batch ON rtb_funnel(import_batch_id);

-- Composite index for joining with rtb_daily
CREATE INDEX IF NOT EXISTS idx_rtb_funnel_join ON rtb_funnel(metric_date, country, publisher_id);
