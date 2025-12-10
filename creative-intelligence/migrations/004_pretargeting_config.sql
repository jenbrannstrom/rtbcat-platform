-- Migration: Pretargeting Configuration
-- Created: 2025-12-10
-- Description: Tables for RTB pretargeting configuration, seats, and endpoints
-- Note: These match the existing table schemas in the database

-- Seats table (billing accounts)
CREATE TABLE IF NOT EXISTS seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT UNIQUE NOT NULL,
    account_name TEXT,
    account_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_seats_billing ON seats(billing_id);

-- Pretargeting configs
CREATE TABLE IF NOT EXISTS pretargeting_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bidder_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    billing_id TEXT,
    display_name TEXT,
    user_name TEXT,
    state TEXT DEFAULT 'ACTIVE',
    included_formats TEXT,
    included_platforms TEXT,
    included_sizes TEXT,
    included_geos TEXT,
    excluded_geos TEXT,
    raw_config TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bidder_id, config_id)
);

CREATE INDEX IF NOT EXISTS idx_pretargeting_bidder ON pretargeting_configs(bidder_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_billing ON pretargeting_configs(billing_id);

-- Pretargeting history (audit trail)
CREATE TABLE IF NOT EXISTS pretargeting_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id TEXT NOT NULL,
    bidder_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT,
    change_source TEXT DEFAULT 'api_sync',
    raw_config_snapshot TEXT,
    FOREIGN KEY (config_id) REFERENCES pretargeting_configs(config_id)
);

CREATE INDEX IF NOT EXISTS idx_pretargeting_history_config ON pretargeting_history(config_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_date ON pretargeting_history(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_bidder ON pretargeting_history(bidder_id);

-- RTB endpoints configuration
CREATE TABLE IF NOT EXISTS rtb_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bidder_id TEXT NOT NULL,
    endpoint_id TEXT NOT NULL,
    url TEXT NOT NULL,
    maximum_qps INTEGER,
    trading_location TEXT,
    bid_protocol TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bidder_id, endpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_rtb_endpoints_bidder ON rtb_endpoints(bidder_id);

-- Retention config (per-seat settings)
CREATE TABLE IF NOT EXISTS retention_config (
    id INTEGER PRIMARY KEY,
    seat_id INTEGER REFERENCES seats(id),
    raw_retention_days INTEGER DEFAULT 90,
    summary_retention_days INTEGER DEFAULT 365,
    auto_aggregate_after_days INTEGER DEFAULT 30,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
