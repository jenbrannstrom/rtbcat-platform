-- Migration 052: Seat/day report completeness materialized view for optimizer readiness.
-- Provides fast seat-day completeness rollups across all five report lanes.

DROP MATERIALIZED VIEW IF EXISTS seat_report_completeness_daily;

CREATE MATERIALIZED VIEW seat_report_completeness_daily AS
WITH daily AS (
    SELECT DISTINCT metric_date::date AS metric_date, buyer_account_id
    FROM rtb_daily
    WHERE COALESCE(buyer_account_id, '') <> ''
),
bidstream AS (
    SELECT DISTINCT metric_date::date AS metric_date, buyer_account_id
    FROM rtb_bidstream
    WHERE COALESCE(buyer_account_id, '') <> ''
),
bid_filtering AS (
    SELECT DISTINCT metric_date::date AS metric_date, buyer_account_id
    FROM rtb_bid_filtering
    WHERE COALESCE(buyer_account_id, '') <> ''
),
quality AS (
    SELECT DISTINCT metric_date::date AS metric_date, buyer_account_id
    FROM rtb_quality
    WHERE COALESCE(buyer_account_id, '') <> ''
),
web_domain AS (
    SELECT DISTINCT metric_date::date AS metric_date, buyer_account_id
    FROM web_domain_daily
    WHERE COALESCE(buyer_account_id, '') <> ''
),
seat_day_keys AS (
    SELECT metric_date, buyer_account_id FROM daily
    UNION
    SELECT metric_date, buyer_account_id FROM bidstream
    UNION
    SELECT metric_date, buyer_account_id FROM bid_filtering
    UNION
    SELECT metric_date, buyer_account_id FROM quality
    UNION
    SELECT metric_date, buyer_account_id FROM web_domain
),
seat_day_flags AS (
    SELECT
        k.metric_date,
        k.buyer_account_id,
        (d.buyer_account_id IS NOT NULL) AS has_rtb_daily,
        (bs.buyer_account_id IS NOT NULL) AS has_rtb_bidstream,
        (bf.buyer_account_id IS NOT NULL) AS has_rtb_bid_filtering,
        (q.buyer_account_id IS NOT NULL) AS has_rtb_quality,
        (wd.buyer_account_id IS NOT NULL) AS has_web_domain_daily
    FROM seat_day_keys k
    LEFT JOIN daily d
      ON d.metric_date = k.metric_date AND d.buyer_account_id = k.buyer_account_id
    LEFT JOIN bidstream bs
      ON bs.metric_date = k.metric_date AND bs.buyer_account_id = k.buyer_account_id
    LEFT JOIN bid_filtering bf
      ON bf.metric_date = k.metric_date AND bf.buyer_account_id = k.buyer_account_id
    LEFT JOIN quality q
      ON q.metric_date = k.metric_date AND q.buyer_account_id = k.buyer_account_id
    LEFT JOIN web_domain wd
      ON wd.metric_date = k.metric_date AND wd.buyer_account_id = k.buyer_account_id
)
SELECT
    metric_date,
    buyer_account_id,
    has_rtb_daily,
    has_rtb_bidstream,
    has_rtb_bid_filtering,
    has_rtb_quality,
    has_web_domain_daily,
    (
        has_rtb_daily::int
        + has_rtb_bidstream::int
        + has_rtb_bid_filtering::int
        + has_rtb_quality::int
        + has_web_domain_daily::int
    )::int AS available_report_types,
    5::int AS expected_report_types,
    ROUND(
        (
            (
                has_rtb_daily::int
                + has_rtb_bidstream::int
                + has_rtb_bid_filtering::int
                + has_rtb_quality::int
                + has_web_domain_daily::int
            )::numeric * 100.0
        ) / 5.0,
        2
    )::numeric(5,2) AS completeness_pct,
    CASE
        WHEN (
            has_rtb_daily::int
            + has_rtb_bidstream::int
            + has_rtb_bid_filtering::int
            + has_rtb_quality::int
            + has_web_domain_daily::int
        ) = 0 THEN 'unavailable'
        WHEN (
            has_rtb_daily::int
            + has_rtb_bidstream::int
            + has_rtb_bid_filtering::int
            + has_rtb_quality::int
            + has_web_domain_daily::int
        ) < 5 THEN 'degraded'
        ELSE 'healthy'
    END::text AS availability_state,
    CURRENT_TIMESTAMP AS refreshed_at
FROM seat_day_flags;

CREATE UNIQUE INDEX IF NOT EXISTS idx_seat_report_completeness_day_seat
    ON seat_report_completeness_daily(metric_date, buyer_account_id);

CREATE INDEX IF NOT EXISTS idx_seat_report_completeness_state_day
    ON seat_report_completeness_daily(availability_state, metric_date DESC);

CREATE INDEX IF NOT EXISTS idx_seat_report_completeness_seat_day
    ON seat_report_completeness_daily(buyer_account_id, metric_date DESC);

REFRESH MATERIALIZED VIEW seat_report_completeness_daily;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '052_seat_day_completeness_mv',
    CURRENT_TIMESTAMP,
    'Add seat/day report completeness materialized view for optimizer readiness'
)
ON CONFLICT (version) DO NOTHING;
