CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id UUID PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (source_type IN ('csv', 'api')),
    buyer_id TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    row_count BIGINT NOT NULL DEFAULT 0,
    error_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_started_at
    ON ingestion_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_source_status
    ON ingestion_runs(source_type, status, started_at DESC);

CREATE TABLE IF NOT EXISTS source_coverage_daily (
    metric_date DATE NOT NULL,
    buyer_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('csv', 'api')),
    has_country BOOLEAN NOT NULL DEFAULT FALSE,
    has_publisher BOOLEAN NOT NULL DEFAULT FALSE,
    has_billing_id BOOLEAN NOT NULL DEFAULT FALSE,
    coverage_score NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    availability_state TEXT NOT NULL DEFAULT 'unavailable'
        CHECK (availability_state IN ('healthy', 'degraded', 'unavailable')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (metric_date, buyer_id, source_type)
);

CREATE INDEX IF NOT EXISTS idx_source_coverage_daily_buyer_date
    ON source_coverage_daily(buyer_id, metric_date DESC);

