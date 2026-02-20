-- Migration 046: Create config breakdown precompute tables.
-- These tables were previously only created at runtime by config_precompute.py
-- or via standalone sql/postgres/001_precompute_tables.sql, meaning migrations
-- alone did not produce a complete schema. This closes the gap so CI
-- schema-compatibility checks pass deterministically.

-- ============================================================================
-- 1. Create tables (idempotent)
-- ============================================================================

CREATE TABLE IF NOT EXISTS config_size_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, creative_size)
);

CREATE TABLE IF NOT EXISTS config_geo_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    country TEXT NOT NULL,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, country)
);

CREATE TABLE IF NOT EXISTS config_publisher_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    publisher_name TEXT,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, publisher_id)
);

CREATE TABLE IF NOT EXISTS config_creative_daily (
    metric_date DATE NOT NULL,
    buyer_account_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    creative_id TEXT NOT NULL,
    creative_size TEXT,
    reached_queries BIGINT DEFAULT 0,
    impressions BIGINT DEFAULT 0,
    spend_micros BIGINT DEFAULT 0,
    PRIMARY KEY (metric_date, buyer_account_id, billing_id, creative_id)
);

-- ============================================================================
-- 2. Indexes (matching sql/postgres/001_precompute_tables.sql)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_cfg_size_date ON config_size_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_cfg_size_billing ON config_size_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_cfg_geo_date ON config_geo_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_cfg_geo_billing ON config_geo_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_cfg_pub_date ON config_publisher_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_cfg_pub_billing ON config_publisher_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_cfg_creative_date ON config_creative_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_cfg_creative_billing ON config_creative_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_cfg_creative_date_buyer_billing_size
    ON config_creative_daily(metric_date, buyer_account_id, billing_id, creative_size);

-- ============================================================================
-- 3. Normalize column types on pre-existing tables
--    (config_precompute.py creates with TEXT/INTEGER; canonical is DATE/BIGINT)
--    Must drop dependent views first since ALTER TYPE fails with view refs.
-- ============================================================================

DO $$
DECLARE
    col RECORD;
    needs_normalize BOOLEAN := FALSE;
BEGIN
    -- Check whether any normalization is needed
    SELECT EXISTS(
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND ((column_name = 'metric_date' AND data_type = 'text')
               OR (column_name IN ('reached_queries', 'impressions', 'spend_micros')
                   AND data_type = 'integer'))
          AND table_name IN (
              'config_size_daily', 'config_geo_daily',
              'config_publisher_daily', 'config_creative_daily'
          )
    ) INTO needs_normalize;

    IF NOT needs_normalize THEN
        RAISE NOTICE 'Column types already correct, skipping normalization';
        RETURN;
    END IF;

    -- Drop dependent alias views before altering columns
    DROP VIEW IF EXISTS pretarg_size_daily;
    DROP VIEW IF EXISTS pretarg_geo_daily;
    DROP VIEW IF EXISTS pretarg_publisher_daily;
    DROP VIEW IF EXISTS pretarg_creative_daily;

    -- Fix metric_date TEXT -> DATE
    FOR col IN
        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'metric_date'
          AND data_type = 'text'
          AND table_name IN (
              'config_size_daily', 'config_geo_daily',
              'config_publisher_daily', 'config_creative_daily'
          )
    LOOP
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN metric_date TYPE DATE USING metric_date::DATE',
            col.table_name
        );
        RAISE NOTICE 'Normalized metric_date to DATE on %', col.table_name;
    END LOOP;

    -- Fix INTEGER -> BIGINT for counter columns
    FOR col IN
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND data_type = 'integer'
          AND column_name IN ('reached_queries', 'impressions', 'spend_micros')
          AND table_name IN (
              'config_size_daily', 'config_geo_daily',
              'config_publisher_daily', 'config_creative_daily'
          )
    LOOP
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I TYPE BIGINT',
            col.table_name, col.column_name
        );
        RAISE NOTICE 'Normalized %.% to BIGINT', col.table_name, col.column_name;
    END LOOP;
END $$;

-- ============================================================================
-- 4. Create/refresh canonical alias views
--    (migration 044 skipped these if source tables did not exist yet;
--     step 3 drops them before ALTER so they are always recreated here)
-- ============================================================================

CREATE OR REPLACE VIEW pretarg_size_daily AS SELECT * FROM config_size_daily;
CREATE OR REPLACE VIEW pretarg_geo_daily AS SELECT * FROM config_geo_daily;
CREATE OR REPLACE VIEW pretarg_publisher_daily AS SELECT * FROM config_publisher_daily;
CREATE OR REPLACE VIEW pretarg_creative_daily AS SELECT * FROM config_creative_daily;

-- ============================================================================
-- 5. Version marker
-- ============================================================================

INSERT INTO schema_migrations (version, applied_at, description)
VALUES ('046_config_breakdown_tables', CURRENT_TIMESTAMP,
        'Create config breakdown precompute tables and refresh alias views')
ON CONFLICT (version) DO NOTHING;
