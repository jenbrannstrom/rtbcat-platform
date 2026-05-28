-- Migration 068: hashed API tokens for outside agent access.
--
-- Agent tokens are bound to normal Cat-Scan users. Buyer isolation still comes
-- from user_buyer_seat_permissions, with optional per-token buyer narrowing.

CREATE TABLE IF NOT EXISTS agent_api_tokens (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    token_prefix TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    buyer_id TEXT REFERENCES buyer_seats(buyer_id) ON DELETE CASCADE,
    scopes TEXT NOT NULL DEFAULT 'agent:stats:read',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ NOT NULL,
    last_used_at TIMESTAMPTZ,
    last_used_ip TEXT,
    last_used_user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_api_tokens_hash
    ON agent_api_tokens(token_hash);

CREATE INDEX IF NOT EXISTS idx_agent_api_tokens_user
    ON agent_api_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_agent_api_tokens_buyer
    ON agent_api_tokens(buyer_id);

CREATE INDEX IF NOT EXISTS idx_agent_api_tokens_active_expiry
    ON agent_api_tokens(is_active, expires_at);

COMMENT ON TABLE agent_api_tokens IS
    'Hashed bearer tokens for outside agents. Plaintext tokens are returned only at creation time.';
