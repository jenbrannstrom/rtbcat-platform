-- Migration 063: Attribution join evidence table for conversion-to-RTB matching.
-- Stores exact/fallback join attempts with confidence and match diagnostics.

CREATE TABLE IF NOT EXISTS conversion_attribution_joins (
    id BIGSERIAL PRIMARY KEY,
    conversion_event_id BIGINT NOT NULL REFERENCES conversion_events(id) ON DELETE CASCADE,
    conversion_event_ts TIMESTAMPTZ NOT NULL,
    buyer_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    join_mode TEXT NOT NULL CHECK (join_mode IN ('exact_clickid', 'fallback_creative_time')),
    join_status TEXT NOT NULL CHECK (join_status IN ('matched', 'unmatched', 'blocked')),
    confidence NUMERIC(8, 6) NOT NULL DEFAULT 0,
    reason TEXT,
    matched_metric_date DATE,
    matched_billing_id TEXT,
    matched_creative_id TEXT,
    matched_app_id TEXT,
    matched_country TEXT,
    matched_publisher_id TEXT,
    matched_impressions BIGINT NOT NULL DEFAULT 0,
    matched_clicks BIGINT NOT NULL DEFAULT 0,
    matched_spend_usd NUMERIC(18, 6) NOT NULL DEFAULT 0,
    fallback_window_days INTEGER NOT NULL DEFAULT 1,
    fallback_candidate_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (conversion_event_id, join_mode)
);

CREATE INDEX IF NOT EXISTS idx_conversion_attr_joins_buyer_ts
    ON conversion_attribution_joins(buyer_id, conversion_event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_attr_joins_source_mode_status
    ON conversion_attribution_joins(source_type, join_mode, join_status);
CREATE INDEX IF NOT EXISTS idx_conversion_attr_joins_confidence
    ON conversion_attribution_joins(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_attr_joins_matched_billing
    ON conversion_attribution_joins(matched_billing_id);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '063_conversion_attribution_joins',
    CURRENT_TIMESTAMP,
    'Add conversion_attribution_joins table for exact/fallback join evidence and confidence'
)
ON CONFLICT (version) DO NOTHING;
