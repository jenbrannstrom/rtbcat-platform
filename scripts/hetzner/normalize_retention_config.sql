-- Keep one global policy and support the existing ON CONFLICT(seat_id) API.
BEGIN;
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='15s';
LOCK TABLE public.retention_config IN ACCESS EXCLUSIVE MODE;
DO $guard$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM retention_config WHERE seat_id IS NULL)
      OR EXISTS (SELECT 1 FROM retention_config WHERE seat_id IS NULL
                 AND (raw_retention_days<>180 OR summary_retention_days<>180))
      OR (SELECT count(DISTINCT ROW(raw_retention_days,summary_retention_days,auto_aggregate_after_days))
          FROM retention_config WHERE seat_id IS NULL)<>1 THEN
        RAISE EXCEPTION 'Global policy differs from the approved identical 180-day rows';
    END IF;
END $guard$;
DELETE FROM retention_config WHERE seat_id IS NULL
AND id<>(SELECT min(id) FROM retention_config WHERE seat_id IS NULL);
DO $constraint$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.retention_config'::regclass
                   AND conname='retention_config_seat_id_unique') THEN
        ALTER TABLE public.retention_config ADD CONSTRAINT retention_config_seat_id_unique
        UNIQUE NULLS NOT DISTINCT (seat_id);
    END IF;
END $constraint$;
COMMIT;

-- Plan the API's existing upsert without executing it.
EXPLAIN (COSTS OFF) INSERT INTO retention_config
(seat_id,raw_retention_days,summary_retention_days,auto_aggregate_after_days,updated_at)
VALUES (NULL,180,180,7,CURRENT_TIMESTAMP)
ON CONFLICT (seat_id) DO UPDATE SET
raw_retention_days=EXCLUDED.raw_retention_days,
summary_retention_days=EXCLUDED.summary_retention_days,
auto_aggregate_after_days=EXCLUDED.auto_aggregate_after_days,
updated_at=EXCLUDED.updated_at;
