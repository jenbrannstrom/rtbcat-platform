-- Migration 065: Add publisher-targeting columns on pretargeting_snapshots
-- Snapshots now preserve publisher targeting mode and values for suspend/rollback flows.

ALTER TABLE IF EXISTS pretargeting_snapshots
    ADD COLUMN IF NOT EXISTS publisher_targeting_mode TEXT;

ALTER TABLE IF EXISTS pretargeting_snapshots
    ADD COLUMN IF NOT EXISTS publisher_targeting_values JSONB;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '065_pretargeting_snapshot_publisher_columns',
    CURRENT_TIMESTAMP,
    'Add publisher targeting fields to pretargeting snapshots'
)
ON CONFLICT (version) DO NOTHING;
