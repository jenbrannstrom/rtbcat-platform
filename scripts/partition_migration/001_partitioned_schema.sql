-- Partitioned replacement for rtb_daily (monthly RANGE partitions on metric_date).
--
-- Creates the table as rtb_daily_p so it can coexist with the live table
-- during rehearsal and cutover; 004_cutover.sql renames it into place.
-- On a fresh target (e.g. Hetzner restore) where no rtb_daily exists yet,
-- run with:  psql -v parent=rtb_daily -f 001_partitioned_schema.sql
--
-- Deliberate changes vs. the unpartitioned table (see README.md):
--   * id is BIGINT. The live sequence was at 589,656,298 of an INTEGER
--     column's 2,147,483,647 max on 2026-07-09, burning ~26% above row
--     count because ON CONFLICT DO NOTHING consumes sequence values.
--   * PRIMARY KEY is (metric_date, id) and the dedup unique index is
--     (metric_date, row_hash): partitioned unique indexes must include
--     the partition key. metric_date is the first input to every
--     compute_row_hash() key list, so (metric_date, row_hash) uniqueness
--     is exactly equivalent to (row_hash) uniqueness.
--   * 16 indexes reduced to 7. Kept/dropped per pg_stat_user_indexes
--     scan counts measured 2026-01-23 → 2026-07-09; table in README.md.

\if :{?parent}
\else
\set parent rtb_daily_p
\endif

-- The live sequence already exists in prod and in any full restore; this
-- covers a bare rehearsal database. (Sequences are always 64-bit.)
CREATE SEQUENCE IF NOT EXISTS rtb_daily_id_seq;

CREATE TABLE :parent (
    id                      bigint NOT NULL DEFAULT nextval('rtb_daily_id_seq'),
    metric_date             date NOT NULL,
    creative_id             text,
    billing_id              text,
    creative_size           text,
    creative_format         text,
    country                 text,
    platform                text,
    environment             text,
    app_id                  text,
    app_name                text,
    publisher_id            text,
    publisher_name          text,
    publisher_domain        text,
    deal_id                 text,
    deal_name               text,
    transaction_type        text,
    advertiser              text,
    buyer_account_id        text,
    buyer_account_name      text,
    bidder_id               text,
    report_type             text,
    hour                    integer,
    reached_queries         bigint DEFAULT 0,
    impressions             bigint DEFAULT 0,
    clicks                  bigint DEFAULT 0,
    spend_micros            bigint DEFAULT 0,
    video_starts            bigint DEFAULT 0,
    video_first_quartile    bigint DEFAULT 0,
    video_midpoint          bigint DEFAULT 0,
    video_third_quartile    bigint DEFAULT 0,
    video_completions       bigint DEFAULT 0,
    vast_errors             bigint DEFAULT 0,
    engaged_views           bigint DEFAULT 0,
    active_view_measurable  bigint DEFAULT 0,
    active_view_viewable    bigint DEFAULT 0,
    bids                    bigint DEFAULT 0,
    bids_in_auction         bigint DEFAULT 0,
    auctions_won            bigint DEFAULT 0,
    gma_sdk                 integer,
    buyer_sdk               integer,
    row_hash                text,
    import_batch_id         text,
    created_at              timestamp DEFAULT CURRENT_TIMESTAMP,
    viewable_impressions    integer DEFAULT 0,
    measurable_impressions  integer DEFAULT 0,
    source_report           text,
    bid_requests            bigint DEFAULT 0,
    buyer_id                text,
    PRIMARY KEY (metric_date, id),
    UNIQUE (metric_date, row_hash)
) PARTITION BY RANGE (metric_date);

-- Kept indexes (names deliberately distinct from the old table's so both
-- can coexist until the old table is dropped).
CREATE INDEX rtbd_p_creative_date_perf
    ON :parent (creative_id, metric_date)
    INCLUDE (spend_micros, impressions, clicks);
CREATE INDEX rtbd_p_billing ON :parent (billing_id);
CREATE INDEX rtbd_p_date_country ON :parent (metric_date, country);
CREATE INDEX rtbd_p_buyer_date_creative_spend
    ON :parent (buyer_account_id, metric_date, creative_id, spend_micros);
CREATE INDEX rtbd_p_date_buyer ON :parent (metric_date, buyer_account_id);

-- Creates monthly partitions named <parent>_YYYYMM covering
-- [from_month, from_month + n_months). Idempotent.
CREATE OR REPLACE FUNCTION ensure_month_partitions(
    parent regclass,
    from_month date,
    n_months integer
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    month_start date := date_trunc('month', from_month)::date;
    part_name   text;
    created     integer := 0;
    i           integer;
BEGIN
    FOR i IN 0 .. n_months - 1 LOOP
        part_name := format('%s_%s', parent::text,
                            to_char(month_start + (i || ' months')::interval, 'YYYYMM'));
        IF to_regclass(part_name) IS NULL THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF %s FOR VALUES FROM (%L) TO (%L)',
                part_name, parent::text,
                month_start + (i || ' months')::interval,
                month_start + ((i + 1) || ' months')::interval
            );
            created := created + 1;
        END IF;
    END LOOP;
    RETURN created;
END;
$$;

-- Cover existing data (oldest row is 2026-01-07) plus headroom; the
-- retention job (partition_retention.py) keeps creating ahead after cutover.
SELECT ensure_month_partitions(:'parent', DATE '2026-01-01', 12);
