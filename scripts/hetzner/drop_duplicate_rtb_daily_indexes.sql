-- Remove only exact duplicate, non-constraint index trees. Keep all table data.
-- Run with psql -X -v ON_ERROR_STOP=1 -d rtbcat_serving -f this-file.sql.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';
LOCK TABLE public.rtb_daily IN ACCESS EXCLUSIVE MODE;
DO $guard$
DECLARE
    pair text[];
    obsolete oid;
    retained oid;
    expected_children integer;
    matched_children integer;
BEGIN
    SELECT count(*) INTO expected_children FROM pg_inherits
    WHERE inhparent='public.rtb_daily'::regclass;
    FOREACH pair SLICE 1 IN ARRAY ARRAY[
        ['rtbd_p_billing','idx_rtb_daily_billing'],
        ['rtbd_p_date_buyer','idx_rtb_daily_metric_buyer'],
        ['rtbd_p_date_country','idx_rtb_daily_metric_country']
    ] LOOP
        obsolete := to_regclass('public.' || pair[1]);
        retained := to_regclass('public.' || pair[2]);
        IF obsolete IS NULL THEN
            RAISE NOTICE 'Already absent: %', pair[1];
            CONTINUE;
        END IF;
        IF retained IS NULL OR NOT EXISTS (
            SELECT 1 FROM pg_index a JOIN pg_index b ON b.indexrelid=retained
            JOIN pg_class ac ON ac.oid=a.indexrelid
            JOIN pg_class bc ON bc.oid=b.indexrelid
            WHERE a.indexrelid=obsolete AND a.indrelid='public.rtb_daily'::regclass
              AND b.indrelid=a.indrelid
              AND (to_jsonb(a)-'indexrelid')=(to_jsonb(b)-'indexrelid')
              AND a.indisvalid AND b.indisvalid AND NOT a.indisunique
              AND NOT a.indisprimary AND NOT a.indisreplident
              AND ac.relam=bc.relam AND ac.reloptions IS NOT DISTINCT FROM bc.reloptions
              AND NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conindid=obsolete)
        ) THEN
            RAISE EXCEPTION 'Index pair is not an exact unneeded duplicate: %', pair;
        END IF;
        SELECT count(*) INTO matched_children
        FROM pg_inherits ai JOIN pg_index a ON a.indexrelid=ai.inhrelid
        JOIN pg_inherits bi ON bi.inhparent=retained
        JOIN pg_index b ON b.indexrelid=bi.inhrelid AND b.indrelid=a.indrelid
        JOIN pg_class ac ON ac.oid=a.indexrelid
        JOIN pg_class bc ON bc.oid=b.indexrelid
        WHERE ai.inhparent=obsolete
          AND (to_jsonb(a)-'indexrelid')=(to_jsonb(b)-'indexrelid')
          AND a.indisvalid AND b.indisvalid
          AND ac.relam=bc.relam AND ac.reloptions IS NOT DISTINCT FROM bc.reloptions
          AND NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conindid=a.indexrelid);
        IF matched_children <> expected_children THEN
            RAISE EXCEPTION 'Missing or mismatched child indexes for %', pair;
        END IF;
        EXECUTE format('DROP INDEX public.%I',pair[1]);
        RAISE NOTICE 'Removed %, retained equivalent %',pair[1],pair[2];
    END LOOP;
END $guard$;
COMMIT;
