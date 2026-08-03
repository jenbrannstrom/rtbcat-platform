-- Migration 073: durable queue for precompute refresh jobs.
--
-- Cloud Scheduler's 30-minute attempt deadline cannot cover a refresh that
-- runs for hours, and edge-timeout retries previously launched overlapping
-- refreshes. The scheduled endpoint now enqueues here and returns 202; a
-- single in-process worker claims jobs one at a time.

CREATE TABLE IF NOT EXISTS precompute_jobs (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL CHECK (source IN ('scheduler', 'gmail-import', 'manual')),
    dedupe_key TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    include_legacy_performance BOOLEAN NOT NULL DEFAULT FALSE,
    run_validation BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    claimed_by TEXT,
    error_text TEXT,
    result JSONB,
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

-- Retries of the same scheduled execution (or the same import) collapse onto
-- the one job that is still queued or running; finished jobs never block a
-- new enqueue for the same key.
CREATE UNIQUE INDEX IF NOT EXISTS uq_precompute_jobs_active_dedupe
    ON precompute_jobs (dedupe_key)
    WHERE status IN ('queued', 'running');

CREATE INDEX IF NOT EXISTS idx_precompute_jobs_status_enqueued
    ON precompute_jobs (status, enqueued_at);
