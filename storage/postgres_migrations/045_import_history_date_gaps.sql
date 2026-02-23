-- Migration 045: Persist import date continuity metadata in import_history.
-- Stores missing-day diagnostics from unified importer so UI/API can surface them.

ALTER TABLE IF EXISTS import_history
    ADD COLUMN IF NOT EXISTS date_gaps TEXT;

ALTER TABLE IF EXISTS import_history
    ADD COLUMN IF NOT EXISTS date_gap_warning TEXT;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '045_import_history_date_gaps',
    CURRENT_TIMESTAMP,
    'Add date_gaps and date_gap_warning to import_history for continuity diagnostics'
)
ON CONFLICT (version) DO NOTHING;
