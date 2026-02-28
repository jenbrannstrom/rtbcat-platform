-- Migration 054: Universal conversion schema (Phase 1 foundation).
-- Adds raw conversion events and daily conversion aggregates.

CREATE TABLE IF NOT EXISTS conversion_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    buyer_id TEXT NOT NULL,
    billing_id TEXT,
    creative_id TEXT,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'install',
            'open',
            'registration',
            'tutorial_complete',
            'level_achieved',
            'first_purchase',
            'first_deposit',
            'purchase',
            'subscription',
            'add_to_cart',
            'checkout',
            'custom'
        )
    ),
    event_name TEXT,
    event_value NUMERIC(18,6),
    currency TEXT,
    country TEXT,
    platform TEXT,
    app_id TEXT,
    publisher_id TEXT,
    campaign_id TEXT,
    click_id TEXT,
    impression_id TEXT,
    attribution_type TEXT DEFAULT 'unknown' CHECK (
        attribution_type IN ('last_click', 'view_through', 'organic', 'unknown')
    ),
    is_retargeting BOOLEAN DEFAULT FALSE,
    click_ts TIMESTAMPTZ,
    event_ts TIMESTAMPTZ NOT NULL,
    latency_seconds INTEGER,
    fraud_status TEXT DEFAULT 'unknown' CHECK (
        fraud_status IN ('clean', 'suspected', 'confirmed_fraud', 'unknown')
    ),
    raw_payload JSONB,
    import_batch_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_type, event_id)
);

CREATE INDEX IF NOT EXISTS idx_conversion_events_event_ts
    ON conversion_events(event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_events_buyer_event_ts
    ON conversion_events(buyer_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_events_billing_event_ts
    ON conversion_events(billing_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_events_event_type_ts
    ON conversion_events(event_type, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_events_source_ts
    ON conversion_events(source_type, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_events_click_id
    ON conversion_events(click_id);
CREATE INDEX IF NOT EXISTS idx_conversion_events_impression_id
    ON conversion_events(impression_id);

CREATE TABLE IF NOT EXISTS conversion_aggregates_daily (
    agg_date DATE NOT NULL,
    buyer_id TEXT NOT NULL,
    billing_id TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    publisher_id TEXT NOT NULL DEFAULT '',
    creative_id TEXT NOT NULL DEFAULT '',
    app_id TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_count BIGINT NOT NULL DEFAULT 0,
    event_value_total NUMERIC(18,6) NOT NULL DEFAULT 0,
    impressions BIGINT NOT NULL DEFAULT 0,
    clicks BIGINT NOT NULL DEFAULT 0,
    spend_usd NUMERIC(18,6) NOT NULL DEFAULT 0,
    cost_per_event NUMERIC(18,6),
    event_rate_pct NUMERIC(18,6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        agg_date,
        buyer_id,
        billing_id,
        country,
        publisher_id,
        creative_id,
        app_id,
        source_type,
        event_type
    )
);

CREATE INDEX IF NOT EXISTS idx_conversion_agg_buyer_date
    ON conversion_aggregates_daily(buyer_id, agg_date DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_agg_billing_date
    ON conversion_aggregates_daily(billing_id, agg_date DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_agg_event_type_date
    ON conversion_aggregates_daily(event_type, agg_date DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_agg_source_date
    ON conversion_aggregates_daily(source_type, agg_date DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '054_conversion_platform',
    CURRENT_TIMESTAMP,
    'Add conversion_events and conversion_aggregates_daily tables for Phase 1'
)
ON CONFLICT (version) DO NOTHING;
