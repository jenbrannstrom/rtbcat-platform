-- Migration: Multi-Account Upload Tracking
-- Created: 2025-12-10
-- Description: Add bidder_id column to track which account each upload belongs to
--              This fixes the single-account assumption in upload tracking.

-- Add bidder_id to import_history to track which account each import belongs to
ALTER TABLE import_history ADD COLUMN bidder_id TEXT;
ALTER TABLE import_history ADD COLUMN billing_ids_found TEXT;  -- JSON list of billing IDs found in import

CREATE INDEX IF NOT EXISTS idx_import_history_bidder ON import_history(bidder_id);

-- Add bidder_id to daily_upload_summary for per-account daily stats
-- Note: This changes the unique constraint - now tracks per account per day
-- Keep upload_date unique for backward compat, but add bidder tracking

ALTER TABLE daily_upload_summary ADD COLUMN bidder_id TEXT;

-- Create new table for per-account daily summaries (preserves backward compat)
CREATE TABLE IF NOT EXISTS account_daily_upload_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_date DATE NOT NULL,
    bidder_id TEXT NOT NULL,
    total_uploads INTEGER DEFAULT 0,
    successful_uploads INTEGER DEFAULT 0,
    failed_uploads INTEGER DEFAULT 0,
    total_rows_written INTEGER DEFAULT 0,
    total_file_size_bytes INTEGER DEFAULT 0,
    avg_rows_per_upload REAL DEFAULT 0,
    min_rows INTEGER,
    max_rows INTEGER,
    has_anomaly INTEGER DEFAULT 0,
    anomaly_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(upload_date, bidder_id)
);

CREATE INDEX IF NOT EXISTS idx_account_daily_upload_date ON account_daily_upload_summary(upload_date DESC);
CREATE INDEX IF NOT EXISTS idx_account_daily_upload_bidder ON account_daily_upload_summary(bidder_id);

-- Add bidder_id to rtb_daily for multi-account querying
ALTER TABLE rtb_daily ADD COLUMN bidder_id TEXT;

CREATE INDEX IF NOT EXISTS idx_rtb_bidder ON rtb_daily(bidder_id);
CREATE INDEX IF NOT EXISTS idx_rtb_date_bidder ON rtb_daily(metric_date, bidder_id);
