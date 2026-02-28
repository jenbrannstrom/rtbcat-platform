-- Migration 057: Add proposal workflow audit trail for optimizer QPS changes.

CREATE TABLE IF NOT EXISTS qps_allocation_proposal_history (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    proposal_id TEXT NOT NULL REFERENCES qps_allocation_proposals(proposal_id) ON DELETE CASCADE,
    buyer_id TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL CHECK (to_status IN ('draft', 'approved', 'applied', 'rejected')),
    apply_mode TEXT CHECK (apply_mode IN ('queue', 'live')),
    changed_by TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qps_proposal_history_proposal_created
    ON qps_allocation_proposal_history(proposal_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qps_proposal_history_buyer_created
    ON qps_allocation_proposal_history(buyer_id, created_at DESC);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '057_qps_proposal_history',
    CURRENT_TIMESTAMP,
    'Add qps_allocation_proposal_history table for proposal workflow audit trail'
)
ON CONFLICT (version) DO NOTHING;
