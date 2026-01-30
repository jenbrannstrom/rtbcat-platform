-- Postgres schema for state/config tables (migrated from SQLite)
-- These tables store application state, user auth, and pretargeting configs

-- ============================================================================
-- User Authentication & Sessions
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

CREATE TABLE IF NOT EXISTS user_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);

-- ============================================================================
-- Service Accounts & Buyer Seats
-- ============================================================================

CREATE TABLE IF NOT EXISTS service_accounts (
    id TEXT PRIMARY KEY,
    client_email TEXT UNIQUE NOT NULL,
    project_id TEXT,
    display_name TEXT,
    credentials_path TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP
);

CREATE TABLE IF NOT EXISTS buyer_seats (
    buyer_id TEXT PRIMARY KEY,
    bidder_id TEXT NOT NULL,
    service_account_id TEXT REFERENCES service_accounts(id),
    display_name TEXT,
    active INTEGER DEFAULT 1,
    creative_count INTEGER DEFAULT 0,
    last_synced TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bidder_id, buyer_id)
);

CREATE INDEX IF NOT EXISTS idx_buyer_seats_bidder ON buyer_seats(bidder_id);
CREATE INDEX IF NOT EXISTS idx_buyer_seats_service_account ON buyer_seats(service_account_id);

-- ============================================================================
-- System Settings
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- Default settings
INSERT INTO system_settings (key, value, description) VALUES
    ('audit_retention_days', '60', 'Number of days to retain audit logs'),
    ('session_duration_days', '30', 'Session duration in days'),
    ('multi_user_enabled', '1', 'Whether multi-user mode is enabled')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- Pretargeting Configurations
-- ============================================================================

CREATE TABLE IF NOT EXISTS pretargeting_configs (
    id SERIAL PRIMARY KEY,
    bidder_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    billing_id TEXT,
    display_name TEXT,
    user_name TEXT,
    state TEXT DEFAULT 'ACTIVE',
    included_formats TEXT,
    included_platforms TEXT,
    included_sizes TEXT,
    included_geos TEXT,
    excluded_geos TEXT,
    included_publishers TEXT,
    excluded_publishers TEXT,
    publisher_targeting_mode TEXT,
    raw_config TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bidder_id, config_id)
);

CREATE INDEX IF NOT EXISTS idx_pretargeting_bidder ON pretargeting_configs(bidder_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_billing ON pretargeting_configs(billing_id);

-- ============================================================================
-- Pretargeting Pending Changes
-- ============================================================================

CREATE TABLE IF NOT EXISTS pretargeting_pending_changes (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value TEXT NOT NULL,
    reason TEXT,
    estimated_qps_impact REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    status TEXT DEFAULT 'pending',
    applied_at TIMESTAMP,
    applied_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_pending_changes_billing ON pretargeting_pending_changes(billing_id);
CREATE INDEX IF NOT EXISTS idx_pending_changes_status ON pretargeting_pending_changes(status);
CREATE INDEX IF NOT EXISTS idx_pending_changes_created ON pretargeting_pending_changes(created_at DESC);

-- ============================================================================
-- Pretargeting History (Audit Trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pretargeting_history (
    id SERIAL PRIMARY KEY,
    config_id TEXT NOT NULL,
    bidder_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT,
    change_source TEXT DEFAULT 'api_sync',
    raw_config_snapshot TEXT
);

CREATE INDEX IF NOT EXISTS idx_pretargeting_history_config ON pretargeting_history(config_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_date ON pretargeting_history(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_pretargeting_history_bidder ON pretargeting_history(bidder_id);

-- ============================================================================
-- Pretargeting Snapshots (For A/B Comparison)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pretargeting_snapshots (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    snapshot_name TEXT,
    snapshot_type TEXT DEFAULT 'manual',
    included_formats TEXT,
    included_platforms TEXT,
    included_sizes TEXT,
    included_geos TEXT,
    excluded_geos TEXT,
    state TEXT,
    total_impressions BIGINT DEFAULT 0,
    total_clicks BIGINT DEFAULT 0,
    total_spend_usd REAL DEFAULT 0,
    total_reached_queries BIGINT DEFAULT 0,
    days_tracked INTEGER DEFAULT 0,
    avg_daily_impressions REAL,
    avg_daily_spend_usd REAL,
    ctr_pct REAL,
    cpm_usd REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_billing ON pretargeting_snapshots(billing_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_created ON pretargeting_snapshots(created_at DESC);

-- ============================================================================
-- Pretargeting Change Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS pretargeting_change_log (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_changed TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_snapshot_id INTEGER REFERENCES pretargeting_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_changelog_billing ON pretargeting_change_log(billing_id);
CREATE INDEX IF NOT EXISTS idx_changelog_detected ON pretargeting_change_log(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_changelog_type ON pretargeting_change_log(change_type);

-- ============================================================================
-- RTB Endpoints
-- ============================================================================

CREATE TABLE IF NOT EXISTS rtb_endpoints (
    id SERIAL PRIMARY KEY,
    bidder_id TEXT NOT NULL,
    endpoint_id TEXT NOT NULL,
    url TEXT,
    maximum_qps INTEGER,
    trading_location TEXT,
    bid_protocol TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bidder_id, endpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_endpoints_bidder ON rtb_endpoints(bidder_id);

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

-- ============================================================================
-- Audit Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id);

-- ============================================================================
-- Precompute Refresh Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS precompute_refresh_log (
    id SERIAL PRIMARY KEY,
    cache_name TEXT NOT NULL,
    buyer_account_id TEXT,
    refreshed_dates TEXT,
    refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_refresh_log_cache ON precompute_refresh_log(cache_name);
CREATE INDEX IF NOT EXISTS idx_refresh_log_buyer ON precompute_refresh_log(buyer_account_id);
