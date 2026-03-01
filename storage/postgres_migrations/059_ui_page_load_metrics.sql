-- Migration 059: Persist UI page-load telemetry for QPS SLO monitoring.

CREATE TABLE IF NOT EXISTS ui_page_load_metrics (
    id BIGSERIAL PRIMARY KEY,
    page_name TEXT NOT NULL,
    buyer_id TEXT,
    user_id TEXT,
    selected_days INTEGER,
    time_to_first_table_row_ms DOUBLE PRECISION,
    time_to_table_hydrated_ms DOUBLE PRECISION,
    api_latency_ms JSONB NOT NULL DEFAULT '{}'::jsonb,
    sampled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ui_page_load_metrics_page_sampled
    ON ui_page_load_metrics (page_name, sampled_at DESC);

CREATE INDEX IF NOT EXISTS idx_ui_page_load_metrics_page_buyer_sampled
    ON ui_page_load_metrics (page_name, buyer_id, sampled_at DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '059_ui_page_load_metrics',
    CURRENT_TIMESTAMP,
    'Add ui_page_load_metrics table for QPS page-load latency telemetry'
)
ON CONFLICT (version) DO NOTHING;
