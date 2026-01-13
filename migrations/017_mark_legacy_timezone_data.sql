-- Migration 017: Mark existing data as legacy (wrong timezone)
--
-- All data imported before this migration used inconsistent timezones.
-- New data starting 2026-01-14 will be in UTC.
--
-- Strategy: Add data_quality column to distinguish:
--   - 'legacy': Pre-UTC data (wrong timezone, keep for development only)
--   - 'production': UTC data (real analytics)
--   - 'sample': Manually marked sample data

-- Add data_quality column to rtb_daily
ALTER TABLE rtb_daily ADD COLUMN data_quality TEXT DEFAULT 'production';

-- Add data_quality column to rtb_bidstream
ALTER TABLE rtb_bidstream ADD COLUMN data_quality TEXT DEFAULT 'production';

-- Add data_quality column to rtb_bid_filtering
ALTER TABLE rtb_bid_filtering ADD COLUMN data_quality TEXT DEFAULT 'production';

-- Add data_quality column to rtb_quality (for future use)
ALTER TABLE rtb_quality ADD COLUMN data_quality TEXT DEFAULT 'production';

-- Mark ALL existing data as 'legacy' (imported before UTC switch)
UPDATE rtb_daily SET data_quality = 'legacy' WHERE data_quality = 'production';
UPDATE rtb_bidstream SET data_quality = 'legacy' WHERE data_quality = 'production';
UPDATE rtb_bid_filtering SET data_quality = 'legacy' WHERE data_quality = 'production';
UPDATE rtb_quality SET data_quality = 'legacy' WHERE data_quality = 'production';

-- Also mark import_history entries as legacy
ALTER TABLE import_history ADD COLUMN data_quality TEXT DEFAULT 'production';
UPDATE import_history SET data_quality = 'legacy' WHERE data_quality = 'production';

-- Create index for filtering by data_quality
CREATE INDEX IF NOT EXISTS idx_rtb_daily_quality ON rtb_daily(data_quality);
CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_quality ON rtb_bidstream(data_quality);
CREATE INDEX IF NOT EXISTS idx_rtb_bid_filtering_quality ON rtb_bid_filtering(data_quality);

-- View: Production-only data for analytics
CREATE VIEW IF NOT EXISTS v_rtb_daily_production AS
SELECT * FROM rtb_daily WHERE data_quality = 'production';

CREATE VIEW IF NOT EXISTS v_rtb_bidstream_production AS
SELECT * FROM rtb_bidstream WHERE data_quality = 'production';
