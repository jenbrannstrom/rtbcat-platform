-- Cutover: swap the partitioned table into place. Instant (metadata-only),
-- but take a short write pause: stop importers / scheduled precompute
-- refreshes first. Run ONLY after 003_validate.sql returns zero rows.
--
--   psql "$POSTGRES_DSN" -1 -f 004_cutover.sql
--
-- The importer picks its ON CONFLICT target by probing pg_partitioned_table
-- at connection time (importers/unified_importer.py), so no code deploy has
-- to be synchronized with this swap.

BEGIN;

ALTER TABLE rtb_daily RENAME TO rtb_daily_unpart;
ALTER TABLE rtb_daily_p RENAME TO rtb_daily;

-- Keep the shared sequence alive when rtb_daily_unpart is eventually
-- dropped: hand ownership to the new table's id column.
ALTER SEQUENCE rtb_daily_id_seq OWNED BY rtb_daily.id;

COMMIT;

-- After a soak period (suggested: 7 days of clean contract checks and
-- precompute refreshes), reclaim ~330 GB:
--   DROP TABLE rtb_daily_unpart;
--
-- Rollback before that drop is the mirror rename:
--   BEGIN;
--   ALTER TABLE rtb_daily RENAME TO rtb_daily_p;
--   ALTER TABLE rtb_daily_unpart RENAME TO rtb_daily;
--   ALTER SEQUENCE rtb_daily_id_seq OWNED BY rtb_daily.id;
--   COMMIT;
