-- Generic buyer-scoped daily ad spend and data-freshness views for agents
-- and external read-only integrations.
--
-- Design mirrors 066_agent_read_views.sql:
-- - security_barrier views in agent_read, row-scoped per database role via
--   agent_private.role_has_buyer_access().
-- - Precomputed sources only (rtb_app_daily, buyer_seats) — never rtb_daily
--   in batch.
-- - Neutral ad-platform data only: identifiers, dates, spend, freshness.
--   Daily grain only; no app-level or billing-level rows are exposed.

CREATE OR REPLACE VIEW agent_read.buyer_daily_spend
WITH (security_barrier = true)
AS
SELECT
    buyer_account_id,
    metric_date,
    SUM(COALESCE(spend_micros, 0))::bigint AS spend_micros,
    SUM(COALESCE(impressions, 0))::bigint AS impressions,
    SUM(COALESCE(clicks, 0))::bigint AS clicks,
    COUNT(*)::int AS source_row_count,
    COUNT(DISTINCT NULLIF(app_name, ''))::int AS app_count,
    COUNT(DISTINCT NULLIF(billing_id, ''))::int AS billing_count
FROM public.rtb_app_daily
WHERE buyer_account_id IS NOT NULL
  AND agent_private.role_has_buyer_access(buyer_account_id)
GROUP BY buyer_account_id, metric_date;

CREATE OR REPLACE VIEW agent_read.buyer_data_freshness
WITH (security_barrier = true)
AS
SELECT
    bs.buyer_id,
    bs.display_name,
    bs.active,
    bs.last_synced,
    spend.latest_metric_date,
    (CURRENT_DATE - spend.latest_metric_date) AS days_behind,
    CASE
        WHEN spend.latest_metric_date IS NULL THEN 'missing'
        WHEN spend.latest_metric_date >= CURRENT_DATE - 2 THEN 'fresh'
        WHEN spend.latest_metric_date >= CURRENT_DATE - 7 THEN 'stale'
        ELSE 'very_stale'
    END AS data_status
FROM public.buyer_seats bs
LEFT JOIN (
    SELECT
        buyer_account_id,
        MAX(metric_date) AS latest_metric_date
    FROM public.rtb_app_daily
    GROUP BY buyer_account_id
) spend ON spend.buyer_account_id = bs.buyer_id
WHERE agent_private.role_has_buyer_access(bs.buyer_id);

COMMENT ON VIEW agent_read.buyer_daily_spend IS
    'Buyer-scoped daily spend/impressions/clicks totals from precomputed rtb_app_daily.';
COMMENT ON VIEW agent_read.buyer_data_freshness IS
    'Buyer-scoped latest-data-date and freshness status for external spend consumers.';
