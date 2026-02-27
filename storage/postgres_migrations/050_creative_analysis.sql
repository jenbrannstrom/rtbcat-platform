-- Creative analysis runs and evidence tables for geo-linguistic mismatch detection.

CREATE TABLE IF NOT EXISTS creative_analysis_runs (
    id TEXT PRIMARY KEY,
    creative_id TEXT NOT NULL,
    analysis_type TEXT NOT NULL DEFAULT 'geo_linguistic',
    status TEXT NOT NULL DEFAULT 'pending',
    result JSONB,
    error_message TEXT,
    triggered_by TEXT,
    force_rerun BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS creative_analysis_evidence (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES creative_analysis_runs(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL,
    file_path TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_creative_type
    ON creative_analysis_runs (creative_id, analysis_type);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_creative_created
    ON creative_analysis_runs (creative_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_status
    ON creative_analysis_runs (status);

CREATE INDEX IF NOT EXISTS idx_analysis_evidence_run
    ON creative_analysis_evidence (run_id);
