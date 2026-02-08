CREATE TABLE IF NOT EXISTS fact_delivery_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    publisher_id TEXT NOT NULL DEFAULT '',
    publisher_name TEXT NOT NULL DEFAULT '',
    reached_queries BIGINT NOT NULL DEFAULT 0,
    impressions BIGINT NOT NULL DEFAULT 0,
    clicks BIGINT NOT NULL DEFAULT 0,
    spend_micros BIGINT NOT NULL DEFAULT 0,
    source_used TEXT NOT NULL,
    source_priority INTEGER NOT NULL DEFAULT 1,
    data_scope TEXT NOT NULL DEFAULT 'billing'
        CHECK (data_scope IN ('billing', 'buyer_fallback')),
    confidence NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
    PRIMARY KEY (
        metric_date,
        buyer_account_id,
        billing_id,
        country,
        publisher_id,
        source_used,
        data_scope
    )
);

CREATE INDEX IF NOT EXISTS idx_fact_delivery_buyer_date
    ON fact_delivery_daily(buyer_account_id, metric_date DESC);

CREATE INDEX IF NOT EXISTS idx_fact_delivery_billing_date
    ON fact_delivery_daily(billing_id, metric_date DESC);

CREATE INDEX IF NOT EXISTS idx_fact_delivery_scope
    ON fact_delivery_daily(data_scope, metric_date DESC);

CREATE TABLE IF NOT EXISTS fact_dimension_gaps_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    total_rows BIGINT NOT NULL DEFAULT 0,
    missing_country_rows BIGINT NOT NULL DEFAULT 0,
    missing_publisher_rows BIGINT NOT NULL DEFAULT 0,
    missing_billing_rows BIGINT NOT NULL DEFAULT 0,
    country_missing_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,
    publisher_missing_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,
    billing_missing_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,
    availability_state TEXT NOT NULL DEFAULT 'unavailable'
        CHECK (availability_state IN ('healthy', 'degraded', 'unavailable')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (metric_date, buyer_account_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_dimension_gaps_buyer_date
    ON fact_dimension_gaps_daily(buyer_account_id, metric_date DESC);
