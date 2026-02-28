-- Migration 056: BYOM optimizer platform foundation (Phase 3).
-- Adds model registry, segment scores, and QPS proposal control tables.

CREATE TABLE IF NOT EXISTS optimization_models (
    id BIGSERIAL PRIMARY KEY,
    model_id TEXT NOT NULL UNIQUE,
    buyer_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    model_type TEXT NOT NULL CHECK (model_type IN ('api', 'rules', 'csv')),
    endpoint_url TEXT,
    auth_header_encrypted TEXT,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_optimization_models_buyer_active
    ON optimization_models(buyer_id, is_active, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_optimization_models_buyer_model_type
    ON optimization_models(buyer_id, model_type, updated_at DESC);

CREATE TABLE IF NOT EXISTS segment_scores (
    id BIGSERIAL PRIMARY KEY,
    score_id TEXT NOT NULL UNIQUE,
    model_id TEXT NOT NULL REFERENCES optimization_models(model_id) ON DELETE CASCADE,
    buyer_id TEXT NOT NULL,
    billing_id TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    publisher_id TEXT NOT NULL DEFAULT '',
    app_id TEXT NOT NULL DEFAULT '',
    creative_size TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT '',
    environment TEXT NOT NULL DEFAULT '',
    hour SMALLINT,
    score_date DATE NOT NULL,
    value_score NUMERIC(8, 6),
    confidence NUMERIC(8, 6),
    reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_segment_scores_model_date
    ON segment_scores(model_id, score_date DESC);
CREATE INDEX IF NOT EXISTS idx_segment_scores_buyer_date
    ON segment_scores(buyer_id, score_date DESC);
CREATE INDEX IF NOT EXISTS idx_segment_scores_billing_date
    ON segment_scores(billing_id, score_date DESC);

CREATE TABLE IF NOT EXISTS qps_allocation_proposals (
    id BIGSERIAL PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    model_id TEXT NOT NULL REFERENCES optimization_models(model_id) ON DELETE CASCADE,
    buyer_id TEXT NOT NULL,
    billing_id TEXT NOT NULL DEFAULT '',
    current_qps NUMERIC(18, 6) NOT NULL DEFAULT 0,
    proposed_qps NUMERIC(18, 6) NOT NULL DEFAULT 0,
    delta_qps NUMERIC(18, 6) NOT NULL DEFAULT 0,
    rationale TEXT,
    projected_impact JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'applied', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_qps_proposals_buyer_status_created
    ON qps_allocation_proposals(buyer_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qps_proposals_model_created
    ON qps_allocation_proposals(model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qps_proposals_billing_created
    ON qps_allocation_proposals(billing_id, created_at DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '056_byom_optimizer_platform',
    CURRENT_TIMESTAMP,
    'Add optimization_models, segment_scores, and qps_allocation_proposals tables'
)
ON CONFLICT (version) DO NOTHING;
