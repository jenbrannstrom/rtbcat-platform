-- Migration 040: Optional web/domain data lane
-- Adds web_domain_daily table for domain-level analytics.
-- Feature-flagged off by default — no impact on existing tables.
-- All operations are idempotent (IF NOT EXISTS, ON CONFLICT DO NOTHING).

CREATE TABLE IF NOT EXISTS web_domain_daily (
    id              SERIAL PRIMARY KEY,
    metric_date     DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id      TEXT NOT NULL,
    publisher_id    TEXT,
    publisher_domain TEXT NOT NULL,
    inventory_type  TEXT NOT NULL CHECK (inventory_type IN ('web', 'app', 'unknown')),
    impressions     BIGINT DEFAULT 0,
    reached_queries BIGINT DEFAULT 0,
    spend_micros    BIGINT DEFAULT 0,
    source_report   TEXT,
    row_hash        TEXT,
    import_batch_id TEXT,
    ingested_at     TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (metric_date, buyer_account_id, billing_id, publisher_domain)
);

CREATE INDEX IF NOT EXISTS idx_web_domain_daily_date
    ON web_domain_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_web_domain_daily_buyer
    ON web_domain_daily(metric_date, buyer_account_id);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (40, CURRENT_TIMESTAMP, 'Add web_domain_daily table for optional domain lane')
ON CONFLICT (version) DO NOTHING;
