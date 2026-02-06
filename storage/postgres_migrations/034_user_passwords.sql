-- Migration 034: Add user_passwords table for password authentication
-- This table stores password hashes separately from user records for security

CREATE TABLE IF NOT EXISTS user_passwords (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_user_passwords_updated_at ON user_passwords(updated_at);

-- Comment explaining the table
COMMENT ON TABLE user_passwords IS 'Password hashes for users who opt for email/password login. OAuth users may not have a row here.';
