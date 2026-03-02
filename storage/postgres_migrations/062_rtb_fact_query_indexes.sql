-- Migration 062: Add composite buyer/date indexes for RTB fact query hot paths.
-- Improves latency for data-health and optimizer economics endpoints.

CREATE INDEX IF NOT EXISTS idx_rtb_daily_buyer_metric_date_desc
    ON rtb_daily (buyer_account_id, metric_date DESC);

CREATE INDEX IF NOT EXISTS idx_rtb_quality_buyer_metric_date_desc
    ON rtb_quality (buyer_account_id, metric_date DESC);

CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_buyer_metric_date_desc
    ON rtb_bidstream (buyer_account_id, metric_date DESC);

CREATE INDEX IF NOT EXISTS idx_rtb_bid_filtering_buyer_metric_date_desc
    ON rtb_bid_filtering (buyer_account_id, metric_date DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '062_rtb_fact_query_indexes',
    CURRENT_TIMESTAMP,
    'Add composite buyer/date indexes for RTB fact query hot paths'
)
ON CONFLICT (version) DO NOTHING;
