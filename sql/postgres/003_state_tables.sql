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
-- Pretargeting Publishers (Normalized Publisher List)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pretargeting_publishers (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('WHITELIST', 'BLACKLIST')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'pending_add', 'pending_remove')),
    source TEXT DEFAULT 'user' CHECK(source IN ('user', 'api_sync')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(billing_id, publisher_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_publishers_billing ON pretargeting_publishers(billing_id);
CREATE INDEX IF NOT EXISTS idx_publishers_status ON pretargeting_publishers(status);
CREATE INDEX IF NOT EXISTS idx_publishers_mode ON pretargeting_publishers(mode);

-- ============================================================================
-- Snapshot Comparisons (A/B Testing)
-- ============================================================================

CREATE TABLE IF NOT EXISTS snapshot_comparisons (
    id SERIAL PRIMARY KEY,
    billing_id TEXT NOT NULL,
    comparison_name TEXT,
    before_snapshot_id INTEGER REFERENCES pretargeting_snapshots(id),
    after_snapshot_id INTEGER REFERENCES pretargeting_snapshots(id),
    before_start_date DATE,
    before_end_date DATE,
    after_start_date DATE,
    after_end_date DATE,
    impressions_delta BIGINT,
    impressions_delta_pct REAL,
    spend_delta_usd REAL,
    spend_delta_pct REAL,
    ctr_delta_pct REAL,
    cpm_delta_pct REAL,
    status TEXT DEFAULT 'in_progress' CHECK(status IN ('in_progress', 'completed', 'cancelled')),
    conclusion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comparisons_billing ON snapshot_comparisons(billing_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_status ON snapshot_comparisons(status);

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
-- Creative Thumbnails
-- ============================================================================

CREATE TABLE IF NOT EXISTS creative_thumbnails (
    creative_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    error_reason TEXT,
    gcs_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_thumbnails_status ON creative_thumbnails(status);

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

-- ============================================================================
-- Import History (Upload Tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS import_history (
    id SERIAL PRIMARY KEY,
    batch_id TEXT NOT NULL,
    filename TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rows_read INTEGER DEFAULT 0,
    rows_imported INTEGER DEFAULT 0,
    rows_skipped INTEGER DEFAULT 0,
    rows_duplicate INTEGER DEFAULT 0,
    date_range_start DATE,
    date_range_end DATE,
    total_spend_usd REAL DEFAULT 0,
    total_impressions BIGINT DEFAULT 0,
    total_reached BIGINT DEFAULT 0,
    file_size_bytes BIGINT DEFAULT 0,
    status TEXT DEFAULT 'complete',
    error_message TEXT,
    bidder_id TEXT,
    buyer_id TEXT,
    billing_ids_found TEXT,
    columns_found TEXT,
    columns_missing TEXT
);

CREATE INDEX IF NOT EXISTS idx_import_history_batch ON import_history(batch_id);
CREATE INDEX IF NOT EXISTS idx_import_history_imported ON import_history(imported_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_history_bidder ON import_history(bidder_id);
CREATE INDEX IF NOT EXISTS idx_import_history_buyer ON import_history(buyer_id);

-- ============================================================================
-- Daily Upload Summary (Aggregated Upload Stats)
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_upload_summary (
    id SERIAL PRIMARY KEY,
    upload_date DATE NOT NULL UNIQUE,
    total_uploads INTEGER DEFAULT 0,
    successful_uploads INTEGER DEFAULT 0,
    failed_uploads INTEGER DEFAULT 0,
    total_rows_written BIGINT DEFAULT 0,
    total_file_size_bytes BIGINT DEFAULT 0,
    min_rows INTEGER,
    max_rows INTEGER,
    avg_rows_per_upload REAL DEFAULT 0,
    has_anomaly INTEGER DEFAULT 0,
    anomaly_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_daily_upload_date ON daily_upload_summary(upload_date DESC);

-- ============================================================================
-- Retention Configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS retention_config (
    id SERIAL PRIMARY KEY,
    seat_id TEXT,
    raw_retention_days INTEGER NOT NULL DEFAULT 90,
    summary_retention_days INTEGER NOT NULL DEFAULT 365,
    auto_aggregate_after_days INTEGER NOT NULL DEFAULT 30,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(seat_id)
);

-- ============================================================================
-- Daily Creative Summary (For Retention/Aggregation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_creative_summary (
    id SERIAL PRIMARY KEY,
    seat_id TEXT,
    creative_id TEXT NOT NULL,
    summary_date DATE NOT NULL,
    total_queries BIGINT DEFAULT 0,
    total_impressions BIGINT DEFAULT 0,
    total_clicks BIGINT DEFAULT 0,
    total_spend REAL DEFAULT 0,
    win_rate REAL,
    ctr REAL,
    cpm REAL,
    unique_geos INTEGER DEFAULT 0,
    unique_apps INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(seat_id, creative_id, summary_date)
);

CREATE INDEX IF NOT EXISTS idx_creative_summary_seat ON daily_creative_summary(seat_id);
CREATE INDEX IF NOT EXISTS idx_creative_summary_date ON daily_creative_summary(summary_date);
CREATE INDEX IF NOT EXISTS idx_creative_summary_creative ON daily_creative_summary(creative_id);
