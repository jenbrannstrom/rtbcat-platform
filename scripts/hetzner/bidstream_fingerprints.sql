BEGIN READ ONLY;
SET LOCAL statement_timeout='15s';
SELECT 'schema',md5(string_agg(concat_ws('|',attnum,attname,atttypid,atttypmod,attnotnull,attgenerated),';' ORDER BY attnum))
FROM pg_attribute WHERE attrelid='rtb_bidstream'::regclass AND attnum>0 AND NOT attisdropped;
SELECT 'retained_sample',count(*),md5(string_agg(to_jsonb(t)::text,'' ORDER BY id))
FROM (SELECT * FROM rtb_bidstream TABLESAMPLE SYSTEM (0.05) REPEATABLE (42)
      WHERE metric_date >= DATE '2026-04-27' ORDER BY id LIMIT 1000) t;
SELECT 'indexes',count(*),count(*) FILTER (WHERE NOT indisvalid)
FROM pg_index WHERE indrelid='rtb_bidstream'::regclass;
ROLLBACK;
