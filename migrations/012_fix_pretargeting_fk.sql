-- Migration 012: Fix broken foreign key constraints in pretargeting tables
-- The FK constraints reference columns that aren't unique, causing sync failures

-- Disable FK checks for this migration
PRAGMA foreign_keys = OFF;

-- Recreate pretargeting_pending_changes without the broken FK
DROP TABLE IF EXISTS pretargeting_pending_changes_old;
ALTER TABLE pretargeting_pending_changes RENAME TO pretargeting_pending_changes_old;

CREATE TABLE pretargeting_pending_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value TEXT NOT NULL,
    reason TEXT,
    estimated_qps_impact REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    status TEXT DEFAULT 'pending',
    applied_at TIMESTAMP,
    applied_by TEXT
    -- Removed: FOREIGN KEY (billing_id) REFERENCES pretargeting_configs(billing_id)
);

-- Copy data if any exists
INSERT INTO pretargeting_pending_changes
    (id, billing_id, config_id, change_type, field_name, value, reason,
     estimated_qps_impact, created_at, created_by, status, applied_at, applied_by)
SELECT id, billing_id, config_id, change_type, field_name, value, reason,
       estimated_qps_impact, created_at, created_by, status, applied_at, applied_by
FROM pretargeting_pending_changes_old;

DROP TABLE pretargeting_pending_changes_old;

-- Recreate pretargeting_history without the broken FK
DROP TABLE IF EXISTS pretargeting_history_old;
ALTER TABLE pretargeting_history RENAME TO pretargeting_history_old;

CREATE TABLE pretargeting_history (
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
    raw_config_snapshot TEXT
    -- Removed: FOREIGN KEY (config_id) REFERENCES pretargeting_configs(config_id)
);

-- Copy data if any exists
INSERT INTO pretargeting_history
    (id, config_id, bidder_id, change_type, field_changed, old_value, new_value,
     changed_at, changed_by, change_source, raw_config_snapshot)
SELECT id, config_id, bidder_id, change_type, field_changed, old_value, new_value,
       changed_at, changed_by, change_source, raw_config_snapshot
FROM pretargeting_history_old;

DROP TABLE pretargeting_history_old;

-- Re-enable FK checks
PRAGMA foreign_keys = ON;

-- Create indexes for the columns that would have been FK targets
CREATE INDEX IF NOT EXISTS idx_pending_changes_billing ON pretargeting_pending_changes(billing_id);
CREATE INDEX IF NOT EXISTS idx_pending_changes_config ON pretargeting_pending_changes(config_id);
CREATE INDEX IF NOT EXISTS idx_history_config ON pretargeting_history(config_id);
CREATE INDEX IF NOT EXISTS idx_history_bidder ON pretargeting_history(bidder_id);
