-- Migration: Remove password-based auth fields
-- Created: 2026-01-15
-- Description: Drop password-related columns and login_attempts table for OAuth2-only auth

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- Recreate users table without password-related columns
CREATE TABLE IF NOT EXISTS users_new (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'user')),
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT,
    last_login_at TEXT
);

INSERT INTO users_new (
    id,
    email,
    display_name,
    role,
    is_active,
    created_at,
    updated_at,
    last_login_at
)
SELECT
    id,
    email,
    display_name,
    role,
    is_active,
    created_at,
    updated_at,
    last_login_at
FROM users;

DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- Remove login attempt tracking (password auth no longer supported)
DROP TABLE IF EXISTS login_attempts;

DELETE FROM system_settings
WHERE key IN ('login_lockout_attempts', 'login_lockout_duration_minutes');

COMMIT;
PRAGMA foreign_keys=ON;
