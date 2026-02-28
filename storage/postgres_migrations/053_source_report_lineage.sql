-- Migration 053: ensure source report lineage columns exist across raw RTB facts.
-- Keeps lineage parity for Postgres raw tables with parquet/BQ report_type tagging.

ALTER TABLE IF EXISTS rtb_daily
    ADD COLUMN IF NOT EXISTS source_report TEXT;

ALTER TABLE IF EXISTS rtb_bidstream
    ADD COLUMN IF NOT EXISTS source_report TEXT;

ALTER TABLE IF EXISTS rtb_bid_filtering
    ADD COLUMN IF NOT EXISTS source_report TEXT;

ALTER TABLE IF EXISTS rtb_quality
    ADD COLUMN IF NOT EXISTS source_report TEXT;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '053_source_report_lineage',
    CURRENT_TIMESTAMP,
    'Ensure source_report lineage columns exist across RTB raw fact tables'
)
ON CONFLICT (version) DO NOTHING;
