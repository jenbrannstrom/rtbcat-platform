-- Migration 015: Normalize billing_id values
--
-- Problem: billing_id from Google API may have whitespace, but CSV import strips it.
-- This causes mismatches between pretargeting_configs and rtb_daily tables,
-- resulting in empty data displays on the dashboard.
--
-- Solution: Trim all existing billing_id values in pretargeting_configs to match
-- the normalized format used by CSV imports.

-- Normalize billing_id in pretargeting_configs (remove leading/trailing whitespace)
UPDATE pretargeting_configs
SET billing_id = TRIM(billing_id)
WHERE billing_id IS NOT NULL AND billing_id != TRIM(billing_id);

-- Also normalize any billing_ids in pretargeting_pending_changes if they exist
UPDATE pretargeting_pending_changes
SET billing_id = TRIM(billing_id)
WHERE billing_id IS NOT NULL AND billing_id != TRIM(billing_id);

-- Log how many rows were affected (for debugging on production)
-- Note: SQLite doesn't support logging, but the UPDATE will show affected rows
