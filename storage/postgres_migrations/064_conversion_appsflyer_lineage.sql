-- Migration 064: AppsFlyer raw ingestion lineage + quality counters.
-- Adds:
--   1) conversion_raw_events: raw + normalized payload lineage for webhook ingress
--   2) conversion_ingestion_lineage_daily: persisted accepted/rejected/unknown mapping counters

CREATE TABLE IF NOT EXISTS conversion_raw_events (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    buyer_id TEXT,
    endpoint_path TEXT,
    event_id TEXT,
    idempotency_key TEXT,
    request_headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_payload JSONB NOT NULL,
    normalized_payload JSONB,
    mapping_scope TEXT NOT NULL DEFAULT 'builtin_default',
    mapping_setting_key TEXT,
    mapping_field_hits JSONB NOT NULL DEFAULT '{}'::jsonb,
    mapping_unresolved_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    unknown_mapping_count INTEGER NOT NULL DEFAULT 0,
    ingestion_status TEXT NOT NULL DEFAULT 'pending' CHECK (
        ingestion_status IN ('pending', 'accepted', 'duplicate', 'rejected')
    ),
    error_code TEXT,
    error_message TEXT,
    import_batch_id TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversion_raw_events_source_received
    ON conversion_raw_events(source_type, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_raw_events_buyer_received
    ON conversion_raw_events(buyer_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_raw_events_status_received
    ON conversion_raw_events(ingestion_status, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_raw_events_import_batch
    ON conversion_raw_events(import_batch_id);

CREATE TABLE IF NOT EXISTS conversion_ingestion_lineage_daily (
    metric_date DATE NOT NULL,
    source_type TEXT NOT NULL,
    buyer_id TEXT NOT NULL,
    mapping_scope TEXT NOT NULL DEFAULT 'builtin_default',
    accepted_count BIGINT NOT NULL DEFAULT 0,
    duplicate_count BIGINT NOT NULL DEFAULT 0,
    rejected_count BIGINT NOT NULL DEFAULT 0,
    unknown_mapping_count BIGINT NOT NULL DEFAULT 0,
    last_event_ts TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (metric_date, source_type, buyer_id, mapping_scope)
);

CREATE INDEX IF NOT EXISTS idx_conversion_lineage_daily_buyer_date
    ON conversion_ingestion_lineage_daily(buyer_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_lineage_daily_source_date
    ON conversion_ingestion_lineage_daily(source_type, metric_date DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '064_conversion_appsflyer_lineage',
    CURRENT_TIMESTAMP,
    'Add conversion_raw_events and conversion_ingestion_lineage_daily for AppsFlyer lineage + counters'
)
ON CONFLICT (version) DO NOTHING;
