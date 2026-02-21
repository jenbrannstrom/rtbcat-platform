-- Migration 047: Add explicit import trigger/source tracking.
-- Tracks whether imports came from manual CSV uploads, manual Gmail runs,
-- or scheduled Gmail automation.

ALTER TABLE ingestion_runs
    ADD COLUMN IF NOT EXISTS import_trigger TEXT;

UPDATE ingestion_runs
SET import_trigger = 'gmail-auto'
WHERE import_trigger IS NULL
  AND (
      report_type = 'gmail-scheduled'
      OR filename LIKE 'scheduler:%'
  );

UPDATE ingestion_runs
SET import_trigger = 'manual'
WHERE import_trigger IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ingestion_runs_import_trigger_check'
    ) THEN
        ALTER TABLE ingestion_runs
            ADD CONSTRAINT ingestion_runs_import_trigger_check
            CHECK (import_trigger IN ('manual', 'gmail-auto', 'gmail-manual'));
    END IF;
END $$;

ALTER TABLE ingestion_runs
    ALTER COLUMN import_trigger SET DEFAULT 'manual';

ALTER TABLE ingestion_runs
    ALTER COLUMN import_trigger SET NOT NULL;

ALTER TABLE import_history
    ADD COLUMN IF NOT EXISTS import_trigger TEXT;

UPDATE import_history
SET import_trigger = 'manual'
WHERE import_trigger IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'import_history_import_trigger_check'
    ) THEN
        ALTER TABLE import_history
            ADD CONSTRAINT import_history_import_trigger_check
            CHECK (import_trigger IN ('manual', 'gmail-auto', 'gmail-manual'));
    END IF;
END $$;

ALTER TABLE import_history
    ALTER COLUMN import_trigger SET DEFAULT 'manual';

ALTER TABLE import_history
    ALTER COLUMN import_trigger SET NOT NULL;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '047_import_trigger_tracking',
    CURRENT_TIMESTAMP,
    'Add import_trigger source tracking for ingestion_runs and import_history'
)
ON CONFLICT (version) DO NOTHING;
