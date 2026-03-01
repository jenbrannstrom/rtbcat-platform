-- Migration 060: Add buyer/date composite indexes for home precompute hot paths.

CREATE INDEX IF NOT EXISTS idx_home_seat_buyer_date
    ON home_seat_daily (buyer_account_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_home_publisher_buyer_date_publisher
    ON home_publisher_daily (buyer_account_id, metric_date, publisher_id);

CREATE INDEX IF NOT EXISTS idx_home_geo_buyer_date_country
    ON home_geo_daily (buyer_account_id, metric_date, country);

CREATE INDEX IF NOT EXISTS idx_home_config_buyer_date_billing
    ON home_config_daily (buyer_account_id, metric_date, billing_id);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '060_home_precompute_query_indexes',
    CURRENT_TIMESTAMP,
    'Add buyer/date composite indexes for home precompute funnel and config query paths'
)
ON CONFLICT (version) DO NOTHING;
