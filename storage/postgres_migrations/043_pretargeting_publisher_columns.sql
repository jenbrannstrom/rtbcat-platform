-- Migration 043: Add publisher-targeting compatibility columns on pretargeting_configs
-- Some runtime paths still write these fields directly on pretargeting_configs.
-- Keep this idempotent so mixed-version deployments can sync safely.

ALTER TABLE IF EXISTS pretargeting_configs
    ADD COLUMN IF NOT EXISTS included_publishers JSONB;

ALTER TABLE IF EXISTS pretargeting_configs
    ADD COLUMN IF NOT EXISTS excluded_publishers JSONB;

ALTER TABLE IF EXISTS pretargeting_configs
    ADD COLUMN IF NOT EXISTS publisher_targeting_mode TEXT;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES ('043_pretargeting_publisher_columns', CURRENT_TIMESTAMP, 'Add pretargeting publisher compatibility columns')
ON CONFLICT (version) DO NOTHING;
