-- Migration: Import Tracking
-- Created: 2025-12-10
-- Description: Tables for tracking CSV imports and upload history

-- Import history - tracks each CSV import
CREATE TABLE IF NOT EXISTS import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL UNIQUE,
    filename TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rows_read INTEGER DEFAULT 0,
    rows_imported INTEGER DEFAULT 0,
    rows_skipped INTEGER DEFAULT 0,
    rows_duplicate INTEGER DEFAULT 0,
    date_range_start DATE,
    date_range_end DATE,
    columns_found TEXT,
    columns_missing TEXT,
    total_reached INTEGER DEFAULT 0,
    total_impressions INTEGER DEFAULT 0,
    total_spend_usd REAL DEFAULT 0,
    status TEXT DEFAULT 'complete',
    error_message TEXT,
    file_size_bytes INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_import_history_batch ON import_history(batch_id);
CREATE INDEX IF NOT EXISTS idx_import_history_date ON import_history(imported_at DESC);

-- Daily upload summary - aggregated stats per day
CREATE TABLE IF NOT EXISTS daily_upload_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_date DATE NOT NULL UNIQUE,
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_daily_upload_date ON daily_upload_summary(upload_date DESC);

-- Import anomalies - tracks data quality issues found during import
CREATE TABLE IF NOT EXISTS import_anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id TEXT NOT NULL,
    row_number INTEGER,
    anomaly_type TEXT NOT NULL,
    creative_id TEXT,
    app_id TEXT,
    app_name TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_anomalies_import ON import_anomalies(import_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON import_anomalies(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_anomalies_app ON import_anomalies(app_id);
