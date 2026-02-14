-- Migration 042: Append-only precompute refresh run ledger
-- Tracks each refresh attempt per cache/table with row counts and runtime metadata.
-- Idempotent via IF NOT EXISTS / ON CONFLICT DO NOTHING.

CREATE TABLE IF NOT EXISTS precompute_refresh_runs (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    cache_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    buyer_account_id TEXT NOT NULL,
    refresh_start TEXT,
    refresh_end TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    row_count BIGINT NOT NULL DEFAULT 0,
    error_text TEXT,
    host TEXT NOT NULL DEFAULT 'unknown',
    app_version TEXT NOT NULL DEFAULT 'unknown',
    git_sha TEXT NOT NULL DEFAULT 'unknown',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_precompute_runs_started_at
    ON precompute_refresh_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_precompute_runs_run_id
    ON precompute_refresh_runs(run_id);

CREATE INDEX IF NOT EXISTS idx_precompute_runs_cache_table_status
    ON precompute_refresh_runs(cache_name, table_name, status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_precompute_runs_buyer_dates
    ON precompute_refresh_runs(buyer_account_id, refresh_start, refresh_end, started_at DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES ('042_precompute_refresh_runs', CURRENT_TIMESTAMP, 'Add append-only precompute refresh run ledger')
ON CONFLICT (version) DO NOTHING;
