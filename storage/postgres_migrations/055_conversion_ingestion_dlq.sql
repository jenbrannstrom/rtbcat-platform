-- Migration 055: Conversion connector observability + dead-letter queue.
-- Tracks rejected webhook payloads and supports replay/discard workflows.

CREATE TABLE IF NOT EXISTS conversion_ingestion_failures (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    buyer_id TEXT,
    endpoint_path TEXT,
    error_code TEXT NOT NULL,
    error_message TEXT,
    payload JSONB NOT NULL,
    request_headers JSONB,
    idempotency_key TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'replayed', 'discarded')),
    replay_attempts INTEGER NOT NULL DEFAULT 0,
    last_replayed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversion_failures_created
    ON conversion_ingestion_failures(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_failures_status_created
    ON conversion_ingestion_failures(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_failures_source_created
    ON conversion_ingestion_failures(source_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_failures_buyer_created
    ON conversion_ingestion_failures(buyer_id, created_at DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '055_conversion_ingestion_dlq',
    CURRENT_TIMESTAMP,
    'Add conversion_ingestion_failures DLQ table for connector observability and replay'
)
ON CONFLICT (version) DO NOTHING;
