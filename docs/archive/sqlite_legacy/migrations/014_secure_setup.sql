-- Migration: Secure Setup Flow
-- Created: 2026-01-08
-- Description: Add password change requirement and setup state for secure first-run experience

-- ============================================================================
-- Add must_change_password to users
-- ============================================================================
-- When true, user must change password before accessing sensitive features
ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0;

-- ============================================================================
-- Add setup_completed to system_settings
-- ============================================================================
-- Tracks whether initial setup (first admin creation) is complete
INSERT OR IGNORE INTO system_settings (key, value, description) VALUES
    ('setup_completed', '0', 'Whether initial setup (admin creation) has been completed');

-- ============================================================================
-- Add password_changed_at to users
-- ============================================================================
-- Track when password was last changed for security compliance
ALTER TABLE users ADD COLUMN password_changed_at TEXT;
