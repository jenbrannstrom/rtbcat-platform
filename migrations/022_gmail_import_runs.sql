-- Migration: Track Gmail report ingestion per seat
-- Created: 2026-01-18
-- Description: Store per-file Gmail import results for admin alerts

CREATE TABLE IF NOT EXISTS gmail_import_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at TEXT NOT NULL,
    report_date TEXT,
    buyer_account_id TEXT,
    report_kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    rows_imported INTEGER DEFAULT 0,
    rows_duplicate INTEGER DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_gmail_import_runs_date
    ON gmail_import_runs(report_date);

CREATE INDEX IF NOT EXISTS idx_gmail_import_runs_seat_date
    ON gmail_import_runs(buyer_account_id, report_date);
