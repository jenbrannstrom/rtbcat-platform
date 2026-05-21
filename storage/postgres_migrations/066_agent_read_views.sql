-- Agent-facing read schema for buyer-scoped reporting and analysis.
--
-- Design:
-- - agent_read exposes stable views intended for agents and report jobs.
-- - agent_private stores the database-role -> buyer grants used by those views.
-- - Direct database roles should be granted SELECT on agent_read views only.
-- - Mutations and refreshes remain app/API actions, not direct SQL writes.

CREATE SCHEMA IF NOT EXISTS agent_private;
CREATE SCHEMA IF NOT EXISTS agent_read;

REVOKE ALL ON SCHEMA agent_private FROM PUBLIC;
REVOKE ALL ON SCHEMA agent_read FROM PUBLIC;

CREATE TABLE IF NOT EXISTS agent_private.buyer_role_grants (
    database_role TEXT NOT NULL,
    buyer_id TEXT NOT NULL,
    granted_by TEXT,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (database_role, buyer_id)
);

COMMENT ON TABLE agent_private.buyer_role_grants IS
    'Maps direct database roles to buyer seats visible through agent_read views. Use buyer_id=* only for trusted internal all-buyer jobs.';

CREATE OR REPLACE FUNCTION agent_private.role_has_buyer_access(input_buyer_id TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = agent_private, pg_temp
AS $$
    SELECT input_buyer_id IS NOT NULL
       AND EXISTS (
            SELECT 1
            FROM agent_private.buyer_role_grants grant_row
            WHERE grant_row.database_role = session_user
              AND (grant_row.buyer_id = input_buyer_id OR grant_row.buyer_id = '*')
       )
$$;

REVOKE ALL ON FUNCTION agent_private.role_has_buyer_access(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION agent_private.role_has_buyer_access(TEXT) TO PUBLIC;

CREATE OR REPLACE VIEW agent_read.accessible_buyers
WITH (security_barrier = true)
AS
SELECT
    buyer_id,
    bidder_id,
    display_name,
    active,
    creative_count,
    last_synced
FROM public.buyer_seats
WHERE agent_private.role_has_buyer_access(buyer_id);

CREATE OR REPLACE VIEW agent_read.creative_language_country_signals
WITH (security_barrier = true)
AS
WITH serving_country_7d AS (
    SELECT
        creative_id,
        buyer_account_id AS buyer_id,
        country,
        SUM(COALESCE(spend_micros, 0)) AS spend_micros,
        SUM(COALESCE(impressions, 0)) AS impressions,
        SUM(COALESCE(clicks, 0)) AS clicks
    FROM public.rtb_daily
    WHERE metric_date >= CURRENT_DATE - 6
      AND creative_id IS NOT NULL
      AND buyer_account_id IS NOT NULL
      AND country IS NOT NULL
      AND country <> ''
    GROUP BY creative_id, buyer_account_id, country
),
serving_7d AS (
    SELECT
        creative_id,
        buyer_id,
        ARRAY_AGG(country ORDER BY spend_micros DESC, impressions DESC, country) AS serving_countries_7d,
        SUM(spend_micros) AS spend_7d_micros,
        SUM(impressions) AS impressions_7d,
        SUM(clicks) AS clicks_7d
    FROM serving_country_7d
    GROUP BY creative_id, buyer_id
),
perf_30d AS (
    SELECT
        creative_id,
        buyer_account_id AS buyer_id,
        SUM(COALESCE(spend_micros, 0)) AS spend_30d_micros,
        SUM(COALESCE(impressions, 0)) AS impressions_30d,
        SUM(COALESCE(clicks, 0)) AS clicks_30d,
        MAX(metric_date) AS last_active_date
    FROM public.rtb_daily
    WHERE metric_date >= CURRENT_DATE - 29
      AND creative_id IS NOT NULL
      AND buyer_account_id IS NOT NULL
    GROUP BY creative_id, buyer_account_id
),
billing_30d AS (
    SELECT
        creative_id,
        buyer_account_id AS buyer_id,
        ARRAY_AGG(DISTINCT billing_id ORDER BY billing_id) FILTER (
            WHERE billing_id IS NOT NULL AND billing_id <> ''
        ) AS billing_ids_30d
    FROM public.config_creative_daily
    WHERE metric_date >= CURRENT_DATE - 29
      AND creative_id IS NOT NULL
      AND buyer_account_id IS NOT NULL
    GROUP BY creative_id, buyer_account_id
),
latest_geo_run AS (
    SELECT DISTINCT ON (creative_id)
        id,
        creative_id,
        status,
        result,
        error_message,
        triggered_by,
        force_rerun,
        started_at,
        completed_at,
        created_at
    FROM public.creative_analysis_runs
    WHERE analysis_type = 'geo_linguistic'
    ORDER BY creative_id, created_at DESC
)
SELECT
    c.id AS creative_id,
    c.name AS creative_name,
    COALESCE(c.buyer_id, s7.buyer_id, p30.buyer_id, b30.buyer_id) AS buyer_id,
    bs.display_name AS buyer_display_name,
    c.format,
    c.approval_status,
    c.advertiser_name,
    c.app_id,
    c.app_name,
    c.detected_language,
    c.detected_language_code,
    c.language_confidence,
    c.language_source,
    c.language_analyzed_at,
    c.language_analysis_error,
    COALESCE(s7.serving_countries_7d, ARRAY[]::TEXT[]) AS serving_countries_7d,
    COALESCE(b30.billing_ids_30d, ARRAY[]::TEXT[]) AS billing_ids_30d,
    COALESCE(s7.spend_7d_micros, 0) AS spend_7d_micros,
    COALESCE(s7.impressions_7d, 0) AS impressions_7d,
    COALESCE(s7.clicks_7d, 0) AS clicks_7d,
    COALESCE(p30.spend_30d_micros, 0) AS spend_30d_micros,
    COALESCE(p30.impressions_30d, 0) AS impressions_30d,
    COALESCE(p30.clicks_30d, 0) AS clicks_30d,
    p30.last_active_date,
    geo.id AS geo_run_id,
    geo.status AS geo_run_status,
    geo.result->>'decision' AS geo_linguistic_decision,
    CASE
        WHEN geo.result->>'risk_score' ~ '^-?[0-9]+(\.[0-9]+)?$'
            THEN (geo.result->>'risk_score')::DOUBLE PRECISION
        ELSE 0.0
    END AS geo_linguistic_risk_score,
    CASE
        WHEN geo.result->>'confidence' ~ '^-?[0-9]+(\.[0-9]+)?$'
            THEN (geo.result->>'confidence')::DOUBLE PRECISION
        ELSE 0.0
    END AS geo_linguistic_confidence,
    COALESCE(geo.result->'primary_languages', '[]'::JSONB) AS geo_primary_languages,
    COALESCE(geo.result->'secondary_languages', '[]'::JSONB) AS geo_secondary_languages,
    COALESCE(geo.result->'detected_currencies', '[]'::JSONB) AS geo_detected_currencies,
    COALESCE(geo.result->'findings', '[]'::JSONB) AS geo_findings,
    geo.error_message AS geo_error_message,
    geo.completed_at AS geo_completed_at,
    CASE
        WHEN geo.status = 'completed' AND geo.result->>'decision' = 'mismatch' THEN 'red'
        WHEN geo.status = 'completed' AND geo.result->>'decision' = 'needs_review' THEN 'orange'
        WHEN geo.status = 'completed' AND geo.result->>'decision' = 'match' THEN 'green'
        WHEN geo.status = 'failed' THEN 'orange'
        WHEN geo.id IS NULL THEN 'orange'
        ELSE 'orange'
    END AS geo_linguistic_status,
    CASE
        WHEN c.detected_language_code IS NULL OR c.detected_language_code = '' THEN 'missing_language'
        WHEN geo.id IS NULL THEN 'missing_geo_linguistic_scan'
        WHEN geo.status = 'failed' THEN 'geo_linguistic_scan_failed'
        WHEN geo.status <> 'completed' THEN 'geo_linguistic_scan_pending'
        WHEN geo.result->>'decision' IN ('mismatch', 'needs_review') THEN geo.result->>'decision'
        ELSE 'ok'
    END AS report_status
FROM public.creatives c
LEFT JOIN serving_7d s7
    ON s7.creative_id = c.id
    AND (c.buyer_id IS NULL OR c.buyer_id = s7.buyer_id)
LEFT JOIN perf_30d p30
    ON p30.creative_id = c.id
    AND COALESCE(c.buyer_id, s7.buyer_id) = p30.buyer_id
LEFT JOIN billing_30d b30
    ON b30.creative_id = c.id
    AND COALESCE(c.buyer_id, s7.buyer_id, p30.buyer_id) = b30.buyer_id
LEFT JOIN public.buyer_seats bs
    ON bs.buyer_id = COALESCE(c.buyer_id, s7.buyer_id, p30.buyer_id, b30.buyer_id)
LEFT JOIN latest_geo_run geo
    ON geo.creative_id = c.id
WHERE agent_private.role_has_buyer_access(
    COALESCE(c.buyer_id, s7.buyer_id, p30.buyer_id, b30.buyer_id)
);

CREATE OR REPLACE VIEW agent_read.creative_scan_queue
WITH (security_barrier = true)
AS
SELECT
    creative_id,
    creative_name,
    buyer_id,
    buyer_display_name,
    format,
    approval_status,
    detected_language_code,
    language_analyzed_at,
    geo_run_id,
    geo_run_status,
    geo_linguistic_decision,
    geo_linguistic_status,
    spend_30d_micros,
    impressions_30d,
    last_active_date,
    CASE
        WHEN detected_language_code IS NULL OR detected_language_code = '' THEN 'analyze_language'
        WHEN geo_run_id IS NULL THEN 'analyze_geo_linguistic'
        WHEN geo_run_status = 'failed' THEN 'retry_geo_linguistic'
        WHEN geo_linguistic_status IN ('red', 'orange')
             AND (geo_completed_at IS NULL OR geo_completed_at < NOW() - INTERVAL '7 days')
            THEN 'refresh_geo_linguistic'
        ELSE 'review'
    END AS recommended_action
FROM agent_read.creative_language_country_signals
WHERE report_status <> 'ok'
   OR geo_linguistic_status IN ('red', 'orange');

CREATE OR REPLACE VIEW agent_read.buyer_daily_report_summary
WITH (security_barrier = true)
AS
SELECT
    buyer_id,
    MAX(buyer_display_name) AS buyer_display_name,
    COUNT(*) AS creatives_seen,
    COUNT(*) FILTER (WHERE spend_7d_micros > 0 OR impressions_7d > 0) AS active_creatives_7d,
    COUNT(*) FILTER (WHERE detected_language_code IS NOT NULL AND detected_language_code <> '') AS language_scanned_creatives,
    COUNT(*) FILTER (WHERE report_status = 'missing_language') AS missing_language_creatives,
    COUNT(*) FILTER (WHERE report_status = 'missing_geo_linguistic_scan') AS missing_geo_linguistic_scans,
    COUNT(*) FILTER (WHERE geo_linguistic_status = 'red') AS red_geo_linguistic_creatives,
    COUNT(*) FILTER (WHERE geo_linguistic_status = 'orange') AS orange_geo_linguistic_creatives,
    COUNT(*) FILTER (WHERE geo_linguistic_status = 'green') AS green_geo_linguistic_creatives,
    SUM(spend_7d_micros) AS spend_7d_micros,
    SUM(impressions_7d) AS impressions_7d,
    SUM(clicks_7d) AS clicks_7d,
    SUM(spend_30d_micros) AS spend_30d_micros,
    MAX(last_active_date) AS latest_metric_date
FROM agent_read.creative_language_country_signals
GROUP BY buyer_id;

CREATE OR REPLACE VIEW agent_read.creative_performance_issues
WITH (security_barrier = true)
AS
SELECT
    creative_id,
    creative_name,
    buyer_id,
    buyer_display_name,
    format,
    approval_status,
    spend_30d_micros,
    impressions_30d,
    clicks_30d,
    last_active_date,
    CASE
        WHEN spend_30d_micros > 0 AND impressions_30d = 0 THEN 'spend_without_impressions'
        WHEN impressions_30d >= 1000 AND clicks_30d = 0 THEN 'zero_clicks'
        WHEN spend_30d_micros >= 10000000 AND geo_linguistic_status = 'red' THEN 'spend_on_geo_linguistic_mismatch'
        WHEN spend_30d_micros >= 10000000 AND geo_linguistic_status = 'orange' THEN 'spend_needs_market_review'
        ELSE 'review'
    END AS issue_type,
    geo_linguistic_status,
    geo_linguistic_decision,
    report_status
FROM agent_read.creative_language_country_signals
WHERE (spend_30d_micros > 0 AND impressions_30d = 0)
   OR (impressions_30d >= 1000 AND clicks_30d = 0)
   OR (spend_30d_micros >= 10000000 AND geo_linguistic_status IN ('red', 'orange'));

COMMENT ON VIEW agent_read.creative_language_country_signals IS
    'Buyer-scoped creative language, country, spend, and latest geo-linguistic analysis signals for agents.';
COMMENT ON VIEW agent_read.creative_scan_queue IS
    'Buyer-scoped creatives that need language/geo-linguistic scan, retry, refresh, or review.';
COMMENT ON VIEW agent_read.buyer_daily_report_summary IS
    'Buyer-scoped daily summary for client reporting and report completeness checks.';
COMMENT ON VIEW agent_read.creative_performance_issues IS
    'Buyer-scoped creative inefficiency signals combining performance and market-fit status.';
