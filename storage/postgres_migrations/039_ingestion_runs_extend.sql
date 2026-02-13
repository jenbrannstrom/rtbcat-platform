-- Migration 039: Extend ingestion_runs with report_type, filename, bidder_id
-- and ensure import_history has buyer_id/bidder_id columns.
-- All operations are idempotent (ADD COLUMN IF NOT EXISTS).

ALTER TABLE ingestion_runs ADD COLUMN IF NOT EXISTS report_type TEXT;
ALTER TABLE ingestion_runs ADD COLUMN IF NOT EXISTS filename TEXT;
ALTER TABLE ingestion_runs ADD COLUMN IF NOT EXISTS bidder_id TEXT;

ALTER TABLE import_history ADD COLUMN IF NOT EXISTS buyer_id TEXT;
ALTER TABLE import_history ADD COLUMN IF NOT EXISTS bidder_id TEXT;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES ('039_ingestion_runs_extend', CURRENT_TIMESTAMP, 'Extend ingestion_runs with report_type/filename/bidder_id; add buyer_id/bidder_id to import_history')
ON CONFLICT (version) DO NOTHING;
