-- Migration 031: Create user_service_account_permissions table
-- This table was defined in 003_state_tables.sql but not applied to Cloud SQL
--
-- Copied verbatim from sql/postgres/003_state_tables.sql lines 293-304

-- ============================================================================
-- User Service Account Permissions
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_service_account_permissions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_account_id TEXT NOT NULL REFERENCES service_accounts(id) ON DELETE CASCADE,
    permission_level TEXT DEFAULT 'read' CHECK(permission_level IN ('read', 'write', 'admin')),
    granted_by TEXT,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, service_account_id)
);

CREATE INDEX IF NOT EXISTS idx_permissions_user ON user_service_account_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_permissions_service_account ON user_service_account_permissions(service_account_id);
