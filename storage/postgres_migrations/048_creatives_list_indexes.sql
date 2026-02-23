-- Migration 048: Speed up creatives list queries used by dashboard.
--
-- The creatives list endpoint orders by created_at DESC and frequently filters
-- by buyer_id. Add covering order indexes so large creative tables do not need
-- full-table sort scans for each request.

CREATE INDEX IF NOT EXISTS idx_creatives_created_at_desc
    ON creatives (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_creatives_buyer_created_at_desc
    ON creatives (buyer_id, created_at DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '048_creatives_list_indexes',
    CURRENT_TIMESTAMP,
    'Add created_at indexes for creatives list performance'
)
ON CONFLICT (version) DO NOTHING;
