-- Migration 030: Ensure auth baseline tables exist before auth-related migrations.
--
-- Why this exists:
-- - 031_user_permissions_table.sql references users(id)
-- - 034_user_passwords.sql references users(id)
-- - 035_audit_log.sql references users(id)
-- Some installations only ran storage/postgres_migrations and missed legacy
-- schema files that originally created users/user_sessions/system_settings.
--
-- This migration is idempotent and safe on existing databases.

-- ============================================================================
-- Users
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'user')),
    is_active INTEGER DEFAULT 1,
    default_language TEXT DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- ============================================================================
-- User sessions
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);

-- ============================================================================
-- System settings
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

INSERT INTO system_settings (key, value, description) VALUES
    ('audit_retention_days', '60', 'Number of days to retain audit logs'),
    ('session_duration_days', '30', 'Session duration in days'),
    ('multi_user_enabled', '1', 'Whether multi-user mode is enabled')
ON CONFLICT (key) DO NOTHING;
