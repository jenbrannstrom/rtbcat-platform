-- Migration 017: Mark existing data as legacy
ALTER TABLE rtb_daily ADD COLUMN data_quality TEXT DEFAULT 'production';
ALTER TABLE rtb_bidstream ADD COLUMN data_quality TEXT DEFAULT 'production';
ALTER TABLE rtb_bid_filtering ADD COLUMN data_quality TEXT DEFAULT 'production';
ALTER TABLE rtb_quality ADD COLUMN data_quality TEXT DEFAULT 'production';

UPDATE rtb_daily SET data_quality = 'legacy' WHERE data_quality = 'production';
UPDATE rtb_bidstream SET data_quality = 'legacy' WHERE data_quality = 'production';
UPDATE rtb_bid_filtering SET data_quality = 'legacy' WHERE data_quality = 'production';
UPDATE rtb_quality SET data_quality = 'legacy' WHERE data_quality = 'production';

ALTER TABLE import_history ADD COLUMN data_quality TEXT DEFAULT 'production';
UPDATE import_history SET data_quality = 'legacy' WHERE data_quality = 'production';

CREATE INDEX IF NOT EXISTS idx_rtb_daily_quality ON rtb_daily(data_quality);
CREATE INDEX IF NOT EXISTS idx_rtb_bidstream_quality ON rtb_bidstream(data_quality);
CREATE INDEX IF NOT EXISTS idx_rtb_bid_filtering_quality ON rtb_bid_filtering(data_quality);

CREATE VIEW IF NOT EXISTS v_rtb_daily_production AS SELECT * FROM rtb_daily WHERE data_quality = 'production';
CREATE VIEW IF NOT EXISTS v_rtb_bidstream_production AS SELECT * FROM rtb_bidstream WHERE data_quality = 'production';
