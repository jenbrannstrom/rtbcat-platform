-- ============================================================================
-- RTB Endpoints Current QPS (derived/precompute)
-- ============================================================================

CREATE TABLE IF NOT EXISTS rtb_endpoints_current (
    id SERIAL PRIMARY KEY,
    bidder_id TEXT NOT NULL,
    endpoint_id TEXT NOT NULL,
    current_qps REAL NOT NULL DEFAULT 0,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bidder_id, endpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_endpoints_current_bidder ON rtb_endpoints_current(bidder_id);
