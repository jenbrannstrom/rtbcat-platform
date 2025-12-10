-- Migration: Pretargeting Snapshots
-- Created: 2025-12-10
-- Description: Tables for tracking pretargeting config changes and A/B comparison

-- Pretargeting snapshots - captures config state at a point in time
CREATE TABLE IF NOT EXISTS pretargeting_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT NOT NULL,
    snapshot_name TEXT,              -- User-defined name like "Before geo expansion"
    snapshot_type TEXT DEFAULT 'manual',  -- 'manual', 'auto', 'before_change'

    -- Config state at snapshot time
    included_formats TEXT,
    included_platforms TEXT,
    included_sizes TEXT,
    included_geos TEXT,
    excluded_geos TEXT,
    state TEXT,                      -- 'ACTIVE', 'SUSPENDED'

    -- Performance metrics at snapshot time (accumulated)
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_spend_usd REAL DEFAULT 0,
    total_reached_queries INTEGER DEFAULT 0,
    days_tracked INTEGER DEFAULT 0,

    -- Computed metrics
    avg_daily_impressions REAL,
    avg_daily_spend_usd REAL,
    ctr_pct REAL,
    cpm_usd REAL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT                       -- User notes about why snapshot was taken
);

CREATE INDEX IF NOT EXISTS idx_snapshots_billing ON pretargeting_snapshots(billing_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_created ON pretargeting_snapshots(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_type ON pretargeting_snapshots(snapshot_type);

-- Snapshot comparisons - tracks before/after analysis
CREATE TABLE IF NOT EXISTS snapshot_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT NOT NULL,
    comparison_name TEXT,            -- e.g., "Geo expansion test Dec 2024"

    -- Before/after snapshot references
    before_snapshot_id INTEGER NOT NULL,
    after_snapshot_id INTEGER,       -- NULL until "after" is captured

    -- Date ranges for comparison
    before_start_date DATE NOT NULL,
    before_end_date DATE NOT NULL,
    after_start_date DATE,
    after_end_date DATE,

    -- Computed deltas (populated when after_snapshot_id is set)
    impressions_delta INTEGER,
    impressions_delta_pct REAL,
    spend_delta_usd REAL,
    spend_delta_pct REAL,
    ctr_delta_pct REAL,
    cpm_delta_pct REAL,

    -- Status
    status TEXT DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'abandoned'
    conclusion TEXT,                 -- User's conclusion about the change

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (before_snapshot_id) REFERENCES pretargeting_snapshots(id),
    FOREIGN KEY (after_snapshot_id) REFERENCES pretargeting_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_comparisons_billing ON snapshot_comparisons(billing_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_status ON snapshot_comparisons(status);

-- Config change log - automatically tracks any config modifications
CREATE TABLE IF NOT EXISTS pretargeting_change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT NOT NULL,
    change_type TEXT NOT NULL,       -- 'geo_added', 'geo_removed', 'size_added', 'state_changed', etc.
    field_changed TEXT NOT NULL,     -- 'included_geos', 'excluded_geos', 'included_sizes', etc.
    old_value TEXT,
    new_value TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_snapshot_id INTEGER,        -- Reference to auto-created snapshot

    FOREIGN KEY (auto_snapshot_id) REFERENCES pretargeting_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_changelog_billing ON pretargeting_change_log(billing_id);
CREATE INDEX IF NOT EXISTS idx_changelog_detected ON pretargeting_change_log(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_changelog_type ON pretargeting_change_log(change_type);

