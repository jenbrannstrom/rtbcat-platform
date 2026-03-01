-- Migration 058: Harden pretargeting query paths with composite indexes.

CREATE INDEX IF NOT EXISTS idx_pretargeting_configs_bidder_dedupe_synced_desc
    ON pretargeting_configs (
        bidder_id,
        (COALESCE(NULLIF(TRIM(billing_id), ''), config_id)),
        synced_at DESC,
        id DESC
    );

CREATE INDEX IF NOT EXISTS idx_pretargeting_configs_dedupe_synced_desc
    ON pretargeting_configs (
        (COALESCE(NULLIF(TRIM(billing_id), ''), config_id)),
        synced_at DESC,
        id DESC
    );

CREATE INDEX IF NOT EXISTS idx_pretargeting_configs_billing_synced_desc
    ON pretargeting_configs (billing_id, synced_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_pretargeting_configs_billing_config
    ON pretargeting_configs (billing_id, config_id);

CREATE INDEX IF NOT EXISTS idx_pretargeting_history_config_changed_id_desc
    ON pretargeting_history (config_id, changed_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_pending_changes_billing_status_created_desc
    ON pretargeting_pending_changes (billing_id, status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_pending_changes_status_created_desc
    ON pretargeting_pending_changes (status, created_at DESC, id DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '058_pretargeting_query_path_indexes',
    CURRENT_TIMESTAMP,
    'Add composite indexes for pretargeting list/detail/history and pending-change query paths'
)
ON CONFLICT (version) DO NOTHING;
