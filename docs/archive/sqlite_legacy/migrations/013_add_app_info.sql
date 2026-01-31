-- Migration 013: Add app info and disapproval tracking to creatives
--
-- Adds columns for:
-- - App store identification (app_id, app_name, app_store)
-- - Disapproval tracking (disapproval_reasons, serving_restrictions)
--
-- These enable better creative clustering by app/product and visibility
-- into disapproval issues.

-- Add app identification columns
ALTER TABLE creatives ADD COLUMN app_id TEXT;
ALTER TABLE creatives ADD COLUMN app_name TEXT;
ALTER TABLE creatives ADD COLUMN app_store TEXT;

-- Add disapproval tracking columns (stored as JSON strings)
ALTER TABLE creatives ADD COLUMN disapproval_reasons TEXT;
ALTER TABLE creatives ADD COLUMN serving_restrictions TEXT;

-- Create index on app_id for clustering queries
CREATE INDEX IF NOT EXISTS idx_creatives_app_id ON creatives(app_id);

-- Create index on app_name for clustering queries
CREATE INDEX IF NOT EXISTS idx_creatives_app_name ON creatives(app_name);

-- Create index on approval_status for filtering disapproved creatives
CREATE INDEX IF NOT EXISTS idx_creatives_approval_status ON creatives(approval_status);
