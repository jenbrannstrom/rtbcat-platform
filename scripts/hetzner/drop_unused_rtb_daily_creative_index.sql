-- Run only after deploying the importer that no longer recreates this index.
-- Removes one nonunique index family; retained rows and columns are unchanged.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';
LOCK TABLE public.rtb_daily IN ACCESS EXCLUSIVE MODE;
DO $guard$
DECLARE
    candidate regclass := 'public.idx_rtb_daily_metric_creative'::regclass;
    alternative regclass;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_index
        WHERE indexrelid = candidate AND indrelid = 'public.rtb_daily'::regclass
          AND NOT indisunique AND NOT indisprimary AND NOT indisreplident
          AND indisvalid AND indnkeyatts = 2 AND indnatts = 2
          AND indpred IS NULL AND indexprs IS NULL
          AND pg_get_indexdef(indexrelid, 1, false) = 'metric_date'
          AND pg_get_indexdef(indexrelid, 2, false) = 'creative_id'
    ) THEN
        RAISE EXCEPTION 'Unexpected candidate definition; no index removed';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_partition_tree(candidate) t
        JOIN pg_index i ON i.indexrelid = t.relid
        WHERE NOT i.indisvalid OR i.indisunique OR i.indisprimary
           OR i.indisreplident OR pg_stat_get_numscans(i.indexrelid) <> 0
    ) THEN
        RAISE EXCEPTION 'Candidate has usage or unexpected properties; no index removed';
    END IF;
    FOREACH alternative IN ARRAY ARRAY[
        'public.idx_rtb_daily_creative'::regclass,
        'public.rtbd_p_creative_date_perf'::regclass
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_partition_tree('public.rtb_daily'::regclass) p
            WHERE NOT EXISTS (
                SELECT 1 FROM pg_partition_tree(alternative) t
                JOIN pg_index i ON i.indexrelid = t.relid
                WHERE i.indrelid = p.relid AND i.indisvalid
                  AND pg_get_indexdef(i.indexrelid, 1, false) = 'creative_id'
            )
        ) THEN
            RAISE EXCEPTION 'Missing valid alternative index coverage; no index removed';
        END IF;
    END LOOP;
END
$guard$;
DROP INDEX public.idx_rtb_daily_metric_creative;
COMMIT;
