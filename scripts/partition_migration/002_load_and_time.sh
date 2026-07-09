#!/usr/bin/env bash
# Copy rtb_daily into the partitioned rtb_daily_p one month at a time,
# timing each chunk. This is the rehearsal workhorse: run it on the TARGET
# instance (restored copy), never casually on live prod (it reads the full
# source table and writes ~190 GB of heap).
#
# Usage:
#   POSTGRES_DSN=postgres://... ./002_load_and_time.sh [source] [target]
# Defaults: source=rtb_daily target=rtb_daily_p
#
# Re-runnable: ON CONFLICT DO NOTHING against the (metric_date, row_hash)
# unique index makes a partially loaded month safe to repeat.

set -euo pipefail

DSN="${POSTGRES_DSN:?set POSTGRES_DSN to the target database DSN}"
SOURCE="${1:-rtb_daily}"
TARGET="${2:-rtb_daily_p}"

# Explicit column list: the live table has a dropped-column gap, so
# SELECT * ordering is not something to depend on.
COLS="id, metric_date, creative_id, billing_id, creative_size, creative_format,
country, platform, environment, app_id, app_name, publisher_id, publisher_name,
publisher_domain, deal_id, deal_name, transaction_type, advertiser,
buyer_account_id, buyer_account_name, bidder_id, report_type, hour,
reached_queries, impressions, clicks, spend_micros, video_starts,
video_first_quartile, video_midpoint, video_third_quartile, video_completions,
vast_errors, engaged_views, active_view_measurable, active_view_viewable,
bids, bids_in_auction, auctions_won, gma_sdk, buyer_sdk, row_hash,
import_batch_id, created_at, viewable_impressions, measurable_impressions,
source_report, bid_requests, buyer_id"

months=$(psql "$DSN" -Atc \
  "SELECT to_char(m, 'YYYY-MM-01') FROM generate_series(
     date_trunc('month', (SELECT min(metric_date) FROM ${SOURCE})),
     date_trunc('month', (SELECT max(metric_date) FROM ${SOURCE})),
     interval '1 month') m")

total_start=$(date +%s)
echo "month        rows        seconds"
echo "--------------------------------"
for month in $months; do
  start=$(date +%s)
  rows=$(psql "$DSN" -Atc \
    "INSERT INTO ${TARGET} (${COLS})
     SELECT ${COLS} FROM ${SOURCE}
     WHERE metric_date >= DATE '${month}'
       AND metric_date < DATE '${month}' + INTERVAL '1 month'
     ON CONFLICT (metric_date, row_hash) DO NOTHING" \
    | sed 's/INSERT 0 //')
  echo "${month}   ${rows:-?}   $(( $(date +%s) - start ))"
done
echo "--------------------------------"
echo "total: $(( $(date +%s) - total_start ))s"
echo "Record these timings in the runbook, then run 003_validate.sql."
