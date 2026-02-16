#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Clone a UI-focused subset of Cat-Scan data from remote Postgres into local Postgres.

Usage:
  scripts/clone_subset_to_local.sh \
    --remote-dsn "postgresql://user:pass@host:5432/db" \
    --local-dsn  "postgresql://user:pass@127.0.0.1:5433/db" \
    [--buyer-id 6634662463] \
    [--days 30] \
    [--skip-truncate] \
    [--skip-campaigns] \
    [--skip-geographies]

Notes:
  - Run local migrations first so target tables exist:
      ./venv/bin/python scripts/postgres_migrate.py
  - By default, target tables are truncated before import to avoid duplicate-key conflicts.
  - Use a dedicated local DB; this script is intentionally destructive for copied tables.
USAGE
}

REMOTE_DSN="${REMOTE_DSN:-}"
LOCAL_DSN="${LOCAL_DSN:-}"
BUYER_ID=""
DAYS=30
SKIP_TRUNCATE=0
SKIP_CAMPAIGNS=0
SKIP_GEOGRAPHIES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote-dsn)
      REMOTE_DSN="${2:-}"
      shift 2
      ;;
    --local-dsn)
      LOCAL_DSN="${2:-}"
      shift 2
      ;;
    --buyer-id)
      BUYER_ID="${2:-}"
      shift 2
      ;;
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    --skip-truncate)
      SKIP_TRUNCATE=1
      shift
      ;;
    --skip-campaigns)
      SKIP_CAMPAIGNS=1
      shift
      ;;
    --skip-geographies)
      SKIP_GEOGRAPHIES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$REMOTE_DSN" || -z "$LOCAL_DSN" ]]; then
  echo "ERROR: --remote-dsn and --local-dsn are required." >&2
  usage
  exit 1
fi

if ! [[ "$DAYS" =~ ^[0-9]+$ ]] || (( DAYS < 1 )); then
  echo "ERROR: --days must be a positive integer." >&2
  exit 1
fi

if [[ -n "$BUYER_ID" ]] && ! [[ "$BUYER_ID" =~ ^[A-Za-z0-9._:-]+$ ]]; then
  echo "ERROR: --buyer-id contains unsupported characters." >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql is required." >&2
  exit 1
fi

run_sql_remote() {
  local sql="$1"
  psql "$REMOTE_DSN" -v ON_ERROR_STOP=1 -Atqc "$sql"
}

table_exists() {
  local dsn="$1"
  local table="$2"
  local exists
  exists="$(psql "$dsn" -v ON_ERROR_STOP=1 -Atqc "SELECT to_regclass('public.${table}') IS NOT NULL;")"
  [[ "$exists" == "t" ]]
}

copy_table() {
  local table="$1"
  local query="$2"

  if ! table_exists "$REMOTE_DSN" "$table"; then
    echo "- skip ${table}: not found in remote"
    return
  fi

  if ! table_exists "$LOCAL_DSN" "$table"; then
    echo "- skip ${table}: not found in local"
    return
  fi

  local out_file="${TMP_DIR}/${table}.csv"
  echo "- copy ${table}"

  psql "$REMOTE_DSN" -v ON_ERROR_STOP=1 -c "\\copy (${query}) TO '${out_file}' WITH (FORMAT csv, HEADER true)"

  local line_count
  line_count="$(wc -l < "${out_file}" | tr -d ' ')"
  local row_count=0
  if [[ -n "$line_count" ]] && (( line_count > 0 )); then
    row_count=$((line_count - 1))
  fi

  if (( row_count == 0 )); then
    echo "  rows: 0"
    IMPORT_COUNTS["$table"]=0
    return
  fi

  psql "$LOCAL_DSN" -v ON_ERROR_STOP=1 -c "\\copy ${table} FROM '${out_file}' WITH (FORMAT csv, HEADER true)"
  echo "  rows: ${row_count}"
  IMPORT_COUNTS["$table"]="$row_count"
}

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/catscan-clone-XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

declare -A IMPORT_COUNTS

DATE_FILTER="metric_date::date >= CURRENT_DATE - INTERVAL '${DAYS} days'"
CDS_DATE_FILTER="date::date >= CURRENT_DATE - INTERVAL '${DAYS} days'"

BIDDER_ID_LIST=""
if [[ -n "$BUYER_ID" ]]; then
  BIDDER_ID_LIST="$(run_sql_remote "SELECT string_agg(DISTINCT quote_literal(bidder_id), ',') FROM buyer_seats WHERE buyer_id='${BUYER_ID}'")"
  if [[ -z "$BIDDER_ID_LIST" ]]; then
    BIDDER_ID_LIST="'${BUYER_ID}'"
  fi
fi

echo "Preparing local target tables..."
BASE_TABLES=(
  buyer_seats
  pretargeting_configs
  creatives
  rtb_daily
  rtb_bidstream
  rtb_bid_filtering
  home_seat_daily
  home_publisher_daily
  home_geo_daily
  home_config_daily
  home_size_daily
  config_size_daily
  config_geo_daily
  config_publisher_daily
  config_creative_daily
  rtb_funnel_daily
  rtb_publisher_daily
  rtb_geo_daily
  rtb_app_daily
  rtb_app_size_daily
  rtb_app_country_daily
  rtb_app_creative_daily
  fact_delivery_daily
  fact_dimension_gaps_daily
  rtb_endpoints
  rtb_endpoints_current
)

if (( SKIP_CAMPAIGNS == 0 )); then
  BASE_TABLES+=(
    campaign_daily_summary
    creative_campaigns
    ai_campaigns
  )
fi

if (( SKIP_GEOGRAPHIES == 0 )); then
  BASE_TABLES+=(geographies)
fi

EXISTING_LOCAL_TABLES=()
for t in "${BASE_TABLES[@]}"; do
  if table_exists "$LOCAL_DSN" "$t"; then
    EXISTING_LOCAL_TABLES+=("$t")
  fi
done

if (( SKIP_TRUNCATE == 0 )) && (( ${#EXISTING_LOCAL_TABLES[@]} > 0 )); then
  joined="$(IFS=,; echo "${EXISTING_LOCAL_TABLES[*]}")"
  echo "Truncating local tables (${#EXISTING_LOCAL_TABLES[@]}): ${joined}"
  psql "$LOCAL_DSN" -v ON_ERROR_STOP=1 -c "TRUNCATE TABLE ${joined} RESTART IDENTITY CASCADE"
else
  echo "Skipping truncate step."
fi

echo "Cloning data subset..."

if [[ -n "$BUYER_ID" ]]; then
  copy_table "buyer_seats" "SELECT * FROM buyer_seats WHERE buyer_id='${BUYER_ID}'"
  copy_table "pretargeting_configs" "SELECT * FROM pretargeting_configs WHERE bidder_id IN (${BIDDER_ID_LIST})"
  copy_table "creatives" "SELECT * FROM creatives WHERE buyer_id='${BUYER_ID}'"

  copy_table "rtb_daily" "SELECT * FROM rtb_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "rtb_bidstream" "SELECT * FROM rtb_bidstream WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "rtb_bid_filtering" "SELECT * FROM rtb_bid_filtering WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"

  copy_table "home_seat_daily" "SELECT * FROM home_seat_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "home_publisher_daily" "SELECT * FROM home_publisher_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "home_geo_daily" "SELECT * FROM home_geo_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "home_config_daily" "SELECT * FROM home_config_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "home_size_daily" "SELECT * FROM home_size_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"

  copy_table "config_size_daily" "SELECT * FROM config_size_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "config_geo_daily" "SELECT * FROM config_geo_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "config_publisher_daily" "SELECT * FROM config_publisher_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "config_creative_daily" "SELECT * FROM config_creative_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"

  copy_table "rtb_funnel_daily" "SELECT * FROM rtb_funnel_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "rtb_publisher_daily" "SELECT * FROM rtb_publisher_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "rtb_geo_daily" "SELECT * FROM rtb_geo_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "rtb_app_daily" "SELECT * FROM rtb_app_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "rtb_app_size_daily" "SELECT * FROM rtb_app_size_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "rtb_app_country_daily" "SELECT * FROM rtb_app_country_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "rtb_app_creative_daily" "SELECT * FROM rtb_app_creative_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"

  copy_table "fact_delivery_daily" "SELECT * FROM fact_delivery_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"
  copy_table "fact_dimension_gaps_daily" "SELECT * FROM fact_dimension_gaps_daily WHERE buyer_account_id='${BUYER_ID}' AND ${DATE_FILTER}"

  copy_table "rtb_endpoints" "SELECT * FROM rtb_endpoints WHERE bidder_id IN (${BIDDER_ID_LIST})"
  copy_table "rtb_endpoints_current" "SELECT * FROM rtb_endpoints_current WHERE bidder_id IN (${BIDDER_ID_LIST})"

  if (( SKIP_CAMPAIGNS == 0 )); then
    copy_table "ai_campaigns" "SELECT DISTINCT ac.* FROM ai_campaigns ac JOIN creative_campaigns cc ON cc.campaign_id = ac.id JOIN creatives c ON c.id = cc.creative_id WHERE c.buyer_id='${BUYER_ID}'"
    copy_table "creative_campaigns" "SELECT cc.* FROM creative_campaigns cc JOIN creatives c ON c.id = cc.creative_id WHERE c.buyer_id='${BUYER_ID}'"
    copy_table "campaign_daily_summary" "SELECT DISTINCT cds.* FROM campaign_daily_summary cds JOIN creative_campaigns cc ON cc.campaign_id = cds.campaign_id JOIN creatives c ON c.id = cc.creative_id WHERE c.buyer_id='${BUYER_ID}' AND ${CDS_DATE_FILTER}"
  fi
else
  copy_table "buyer_seats" "SELECT * FROM buyer_seats"
  copy_table "pretargeting_configs" "SELECT * FROM pretargeting_configs"
  copy_table "creatives" "SELECT * FROM creatives"

  copy_table "rtb_daily" "SELECT * FROM rtb_daily WHERE ${DATE_FILTER}"
  copy_table "rtb_bidstream" "SELECT * FROM rtb_bidstream WHERE ${DATE_FILTER}"
  copy_table "rtb_bid_filtering" "SELECT * FROM rtb_bid_filtering WHERE ${DATE_FILTER}"

  copy_table "home_seat_daily" "SELECT * FROM home_seat_daily WHERE ${DATE_FILTER}"
  copy_table "home_publisher_daily" "SELECT * FROM home_publisher_daily WHERE ${DATE_FILTER}"
  copy_table "home_geo_daily" "SELECT * FROM home_geo_daily WHERE ${DATE_FILTER}"
  copy_table "home_config_daily" "SELECT * FROM home_config_daily WHERE ${DATE_FILTER}"
  copy_table "home_size_daily" "SELECT * FROM home_size_daily WHERE ${DATE_FILTER}"

  copy_table "config_size_daily" "SELECT * FROM config_size_daily WHERE ${DATE_FILTER}"
  copy_table "config_geo_daily" "SELECT * FROM config_geo_daily WHERE ${DATE_FILTER}"
  copy_table "config_publisher_daily" "SELECT * FROM config_publisher_daily WHERE ${DATE_FILTER}"
  copy_table "config_creative_daily" "SELECT * FROM config_creative_daily WHERE ${DATE_FILTER}"

  copy_table "rtb_funnel_daily" "SELECT * FROM rtb_funnel_daily WHERE ${DATE_FILTER}"
  copy_table "rtb_publisher_daily" "SELECT * FROM rtb_publisher_daily WHERE ${DATE_FILTER}"
  copy_table "rtb_geo_daily" "SELECT * FROM rtb_geo_daily WHERE ${DATE_FILTER}"
  copy_table "rtb_app_daily" "SELECT * FROM rtb_app_daily WHERE ${DATE_FILTER}"
  copy_table "rtb_app_size_daily" "SELECT * FROM rtb_app_size_daily WHERE ${DATE_FILTER}"
  copy_table "rtb_app_country_daily" "SELECT * FROM rtb_app_country_daily WHERE ${DATE_FILTER}"
  copy_table "rtb_app_creative_daily" "SELECT * FROM rtb_app_creative_daily WHERE ${DATE_FILTER}"

  copy_table "fact_delivery_daily" "SELECT * FROM fact_delivery_daily WHERE ${DATE_FILTER}"
  copy_table "fact_dimension_gaps_daily" "SELECT * FROM fact_dimension_gaps_daily WHERE ${DATE_FILTER}"

  copy_table "rtb_endpoints" "SELECT * FROM rtb_endpoints"
  copy_table "rtb_endpoints_current" "SELECT * FROM rtb_endpoints_current"

  if (( SKIP_CAMPAIGNS == 0 )); then
    copy_table "ai_campaigns" "SELECT * FROM ai_campaigns"
    copy_table "creative_campaigns" "SELECT * FROM creative_campaigns"
    copy_table "campaign_daily_summary" "SELECT * FROM campaign_daily_summary WHERE ${CDS_DATE_FILTER}"
  fi
fi

if (( SKIP_GEOGRAPHIES == 0 )); then
  copy_table "geographies" "SELECT * FROM geographies"
fi

echo
echo "Clone complete. Imported row counts:"
for key in "${!IMPORT_COUNTS[@]}"; do
  printf "  %s: %s\n" "$key" "${IMPORT_COUNTS[$key]}"
done

echo
echo "Next steps:"
echo "  1) export POSTGRES_DSN='${LOCAL_DSN}'"
echo "  2) export POSTGRES_SERVING_DSN='${LOCAL_DSN}'"
echo "  3) start API + dashboard locally"
