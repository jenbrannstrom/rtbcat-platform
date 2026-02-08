ALTER TABLE thumbnail_status
    ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_error_category TEXT;

CREATE INDEX IF NOT EXISTS idx_thumbnail_status_next_retry
    ON thumbnail_status(next_retry_at);

CREATE TABLE IF NOT EXISTS creative_live_fetch_telemetry (
    id BIGSERIAL PRIMARY KEY,
    creative_id TEXT NOT NULL,
    buyer_id TEXT,
    event_type TEXT NOT NULL,
    error_type TEXT,
    error_message TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_live_fetch_telemetry_occurred
    ON creative_live_fetch_telemetry(occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_live_fetch_telemetry_creative
    ON creative_live_fetch_telemetry(creative_id, occurred_at DESC);

