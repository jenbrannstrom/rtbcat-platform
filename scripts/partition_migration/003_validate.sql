-- Per-month reconciliation between the unpartitioned source and the
-- partitioned target. Zero rows returned = clean. Any row returned is a
-- month whose counts or sums disagree — do not cut over.
--
-- Usage:
--   psql "$POSTGRES_DSN" -v source=rtb_daily -v target=rtb_daily_p \
--        -f 003_validate.sql

\if :{?source}
\else
\set source rtb_daily
\endif
\if :{?target}
\else
\set target rtb_daily_p
\endif

WITH src AS (
    SELECT date_trunc('month', metric_date)::date AS month,
           count(*)                AS rows,
           count(DISTINCT row_hash) AS hashes,
           sum(spend_micros)       AS spend_micros,
           sum(impressions)        AS impressions,
           sum(clicks)             AS clicks,
           sum(bid_requests)       AS bid_requests
    FROM :source
    GROUP BY 1
), tgt AS (
    SELECT date_trunc('month', metric_date)::date AS month,
           count(*)                AS rows,
           count(DISTINCT row_hash) AS hashes,
           sum(spend_micros)       AS spend_micros,
           sum(impressions)        AS impressions,
           sum(clicks)             AS clicks,
           sum(bid_requests)       AS bid_requests
    FROM :target
    GROUP BY 1
)
SELECT COALESCE(s.month, t.month) AS month,
       s.rows  AS src_rows,  t.rows  AS tgt_rows,
       s.spend_micros AS src_spend, t.spend_micros AS tgt_spend,
       s.hashes AS src_hashes, t.hashes AS tgt_hashes
FROM src s
FULL OUTER JOIN tgt t USING (month)
WHERE s.rows IS DISTINCT FROM t.rows
   OR s.hashes IS DISTINCT FROM t.hashes
   OR s.spend_micros IS DISTINCT FROM t.spend_micros
   OR s.impressions IS DISTINCT FROM t.impressions
   OR s.clicks IS DISTINCT FROM t.clicks
   OR s.bid_requests IS DISTINCT FROM t.bid_requests
ORDER BY 1;
