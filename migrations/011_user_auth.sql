-- Migration: User Authentication
-- Created: 2025-12-30
-- Description: Add multi-user authentication with sessions, permissions, rate limiting, and audit logging

-- ============================================================================
-- Users Table
-- ============================================================================
-- Stores user accounts with password hashes and metadata
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'user')),
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT,
    last_login_at TEXT
);

-- ============================================================================
-- User Sessions Table
-- ============================================================================
-- HTTP-only cookie sessions with 30-day expiry
CREATE TABLE IF NOT EXISTS user_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================================
-- User Service Account Permissions
-- ============================================================================
-- Controls which service accounts a user can access
CREATE TABLE IF NOT EXISTS user_service_account_permissions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    service_account_id TEXT NOT NULL,
    permission_level TEXT DEFAULT 'read' CHECK(permission_level IN ('read', 'write', 'admin')),
    granted_by TEXT,
    granted_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (service_account_id) REFERENCES service_accounts(id) ON DELETE CASCADE,
    UNIQUE(user_id, service_account_id)
);

-- ============================================================================
-- Login Attempts Table (Rate Limiting)
-- ============================================================================
-- Track failed login attempts for rate limiting (5 attempts = 1 hour lockout)
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ip_address TEXT,
    attempted_at TEXT NOT NULL DEFAULT (datetime('now')),
    success INTEGER DEFAULT 0
);

-- ============================================================================
-- Audit Log Table
-- ============================================================================
-- Tracks all user actions for compliance and debugging
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================================
-- System Settings Table
-- ============================================================================
-- Stores configurable settings like audit retention period
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT DEFAULT (datetime('now')),
    updated_by TEXT
);

-- Default settings
INSERT OR IGNORE INTO system_settings (key, value, description) VALUES
    ('audit_retention_days', '60', 'Number of days to retain audit logs (30, 60, 90, 120, or 0 for unlimited)'),
    ('session_duration_days', '30', 'Session duration in days'),
    ('login_lockout_attempts', '5', 'Number of failed login attempts before lockout'),
    ('login_lockout_duration_minutes', '60', 'Lockout duration in minutes after failed attempts'),
    ('multi_user_enabled', '1', 'Whether multi-user mode is enabled (0 for single-user/open-source)');

-- ============================================================================
-- Indexes for Performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);

CREATE INDEX IF NOT EXISTS idx_user_perms_user ON user_service_account_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_perms_sa ON user_service_account_permissions(service_account_id);

CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON login_attempts(email);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address);
CREATE INDEX IF NOT EXISTS idx_login_attempts_time ON login_attempts(attempted_at);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id);
