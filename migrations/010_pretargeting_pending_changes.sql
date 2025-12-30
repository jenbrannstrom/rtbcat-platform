-- Migration: Pretargeting Pending Changes
-- Created: 2025-12-11
-- Description: Track staged/pending changes to pretargeting configs before applying to Google API

-- Pending changes table - stores changes staged but not yet applied to Google
CREATE TABLE IF NOT EXISTS pretargeting_pending_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    change_type TEXT NOT NULL,  -- 'add_size', 'remove_size', 'add_geo', 'remove_geo', 'add_format', 'remove_format', 'change_state'
    field_name TEXT NOT NULL,   -- 'included_sizes', 'included_geos', 'excluded_geos', 'included_formats', 'state'
    value TEXT NOT NULL,        -- The value to add/remove (e.g., '300x250', 'US', 'HTML')
    reason TEXT,                -- User-provided reason for the change
    estimated_qps_impact REAL,  -- Estimated QPS waste reduction
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending', 'applied', 'rejected', 'cancelled'
    applied_at TIMESTAMP,
    applied_by TEXT,
    FOREIGN KEY (billing_id) REFERENCES pretargeting_configs(billing_id)
);

CREATE INDEX IF NOT EXISTS idx_pending_changes_billing ON pretargeting_pending_changes(billing_id);
CREATE INDEX IF NOT EXISTS idx_pending_changes_status ON pretargeting_pending_changes(status);
CREATE INDEX IF NOT EXISTS idx_pending_changes_created ON pretargeting_pending_changes(created_at DESC);

-- View to see all pending changes grouped by config
CREATE VIEW IF NOT EXISTS v_pending_changes_summary AS
SELECT
    billing_id,
    COUNT(*) as pending_count,
    SUM(CASE WHEN change_type LIKE 'remove_%' THEN estimated_qps_impact ELSE 0 END) as total_qps_reduction,
    GROUP_CONCAT(DISTINCT change_type) as change_types,
    MIN(created_at) as first_change,
    MAX(created_at) as last_change
FROM pretargeting_pending_changes
WHERE status = 'pending'
GROUP BY billing_id;
