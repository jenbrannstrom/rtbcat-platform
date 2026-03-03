#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-}"
SOURCE_TYPE="${CATSCAN_CONVERSION_SOURCE_TYPE:-appsflyer}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
DAYS="${CATSCAN_ATTRIBUTION_DAYS:-14}"
FALLBACK_WINDOW_DAYS="${CATSCAN_ATTRIBUTION_FALLBACK_WINDOW_DAYS:-1}"
LIMIT="${CATSCAN_ATTRIBUTION_REPORT_LIMIT:-50}"
OUT_DIR="${CATSCAN_OUTPUT_DIR:-/tmp}"
DOC_OUT=""
API_TOKEN="${CATSCAN_API_TOKEN:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
API_EMAIL="${CATSCAN_CANARY_EMAIL:-}"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_conversion_attribution_phase_b_report.sh --buyer-id <id> [options]

Runs conversion attribution Phase-B diagnostics:
1) POST /conversions/attribution/refresh
2) GET  /conversions/attribution/summary
3) GET  /conversions/attribution/joins (matched + unmatched fallback samples)
4) Writes markdown/json artifacts to /tmp (or --out-dir)

Options:
  --buyer-id <id>                 Required buyer_id
  --source-type <name>            Source type (default: appsflyer)
  --days <n>                      Lookback days (default: 14)
  --fallback-window-days <n>      Fallback creative-time window in days (default: 1)
  --limit <n>                     Sample rows per joins query (default: 50)
  --api-base-url <url>            API base URL (default: https://scan.rtb.cat/api)
  --token <value>                 Bearer token for API auth
  --email <value>                 X-Email identity for API auth
  --out-dir <dir>                 Output root (default: /tmp)
  --doc-out <path>                Optional markdown copy path
  -h, --help                      Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buyer-id)
      BUYER_ID="${2:-}"
      shift 2
      ;;
    --source-type)
      SOURCE_TYPE="${2:-}"
      shift 2
      ;;
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    --fallback-window-days)
      FALLBACK_WINDOW_DAYS="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --api-base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --token)
      API_TOKEN="${2:-}"
      shift 2
      ;;
    --email)
      API_EMAIL="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --doc-out)
      DOC_OUT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$BUYER_ID" ]]; then
  echo "--buyer-id is required." >&2
  exit 2
fi
if ! [[ "$DAYS" =~ ^[0-9]+$ ]] || (( DAYS < 1 || DAYS > 365 )); then
  echo "Invalid --days '${DAYS}' (expected 1..365)." >&2
  exit 2
fi
if ! [[ "$FALLBACK_WINDOW_DAYS" =~ ^[0-9]+$ ]] || (( FALLBACK_WINDOW_DAYS < 0 || FALLBACK_WINDOW_DAYS > 7 )); then
  echo "Invalid --fallback-window-days '${FALLBACK_WINDOW_DAYS}' (expected 0..7)." >&2
  exit 2
fi
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || (( LIMIT < 1 || LIMIT > 1000 )); then
  echo "Invalid --limit '${LIMIT}' (expected 1..1000)." >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "'curl' is required." >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "'jq' is required." >&2
  exit 2
fi

declare -a AUTH_HEADERS=()
if [[ -n "$API_TOKEN" ]]; then
  AUTH_HEADERS=(-H "Authorization: Bearer ${API_TOKEN}")
elif [[ -n "$API_EMAIL" ]]; then
  AUTH_HEADERS=(-H "X-Email: ${API_EMAIL}")
else
  echo "Provide --token (or CATSCAN_API_TOKEN/CATSCAN_CANARY_BEARER_TOKEN) or --email (CATSCAN_CANARY_EMAIL)." >&2
  exit 2
fi

BASE_URL="${BASE_URL%/}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${OUT_DIR%/}/conversion-attribution-phase-b-${BUYER_ID}-${STAMP}"
mkdir -p "$RUN_DIR"

do_request() {
  local method="$1"
  local path="$2"
  local out_body="$3"
  local out_meta="$4"
  local data="${5:-}"
  local -a data_args=()
  if [[ -n "$data" ]]; then
    data_args=(-H "Content-Type: application/json" -d "$data")
  fi

  local http_code
  http_code="$(
    curl -sS -X "$method" \
      "${AUTH_HEADERS[@]}" \
      "${data_args[@]}" \
      -o "$out_body" \
      -w "%{http_code}" \
      "${BASE_URL}${path}"
  )"
  echo "$http_code" > "$out_meta"
}

REFRESH_BODY="${RUN_DIR}/refresh.json"
REFRESH_META="${RUN_DIR}/refresh.http"
SUMMARY_BODY="${RUN_DIR}/summary.json"
SUMMARY_META="${RUN_DIR}/summary.http"
MATCHED_BODY="${RUN_DIR}/joins_fallback_matched.json"
MATCHED_META="${RUN_DIR}/joins_fallback_matched.http"
UNMATCHED_BODY="${RUN_DIR}/joins_fallback_unmatched.json"
UNMATCHED_META="${RUN_DIR}/joins_fallback_unmatched.http"
REPORT_MD="${RUN_DIR}/phase_b_report.md"

echo "Run dir: ${RUN_DIR}"
echo "Buyer: ${BUYER_ID}"
echo "Source type: ${SOURCE_TYPE}"
echo "Days: ${DAYS}"
echo "Fallback window days: ${FALLBACK_WINDOW_DAYS}"
echo

echo "[1/4] Refreshing attribution joins..."
do_request "POST" \
  "/conversions/attribution/refresh?buyer_id=${BUYER_ID}&source_type=${SOURCE_TYPE}&days=${DAYS}&fallback_window_days=${FALLBACK_WINDOW_DAYS}" \
  "$REFRESH_BODY" \
  "$REFRESH_META"
echo "refresh_http=$(cat "$REFRESH_META")"
if [[ "$(cat "$REFRESH_META")" != "200" ]]; then
  echo "Refresh failed. Response preview:"
  head -c 600 "$REFRESH_BODY" || true
  echo
  exit 1
fi

echo "[2/4] Fetching attribution summary..."
do_request "GET" \
  "/conversions/attribution/summary?buyer_id=${BUYER_ID}&source_type=${SOURCE_TYPE}&days=${DAYS}" \
  "$SUMMARY_BODY" \
  "$SUMMARY_META"
echo "summary_http=$(cat "$SUMMARY_META")"
if [[ "$(cat "$SUMMARY_META")" != "200" ]]; then
  echo "Summary failed. Response preview:"
  head -c 600 "$SUMMARY_BODY" || true
  echo
  exit 1
fi

echo "[3/4] Fetching fallback matched/unmatched samples..."
do_request "GET" \
  "/conversions/attribution/joins?buyer_id=${BUYER_ID}&source_type=${SOURCE_TYPE}&days=${DAYS}&join_mode=fallback_creative_time&join_status=matched&limit=${LIMIT}&offset=0" \
  "$MATCHED_BODY" \
  "$MATCHED_META"
echo "joins_fallback_matched_http=$(cat "$MATCHED_META")"
do_request "GET" \
  "/conversions/attribution/joins?buyer_id=${BUYER_ID}&source_type=${SOURCE_TYPE}&days=${DAYS}&join_mode=fallback_creative_time&join_status=unmatched&limit=${LIMIT}&offset=0" \
  "$UNMATCHED_BODY" \
  "$UNMATCHED_META"
echo "joins_fallback_unmatched_http=$(cat "$UNMATCHED_META")"

if [[ "$(cat "$MATCHED_META")" != "200" || "$(cat "$UNMATCHED_META")" != "200" ]]; then
  echo "Join samples failed. Inspect run dir: ${RUN_DIR}" >&2
  exit 1
fi

echo "[4/4] Rendering report..."
TOTAL_EVENTS="$(jq -r '.total_events // 0' "$SUMMARY_BODY")"
EXACT_BLOCKED="$(jq -r '([.modes[]? | select(.mode=="exact_clickid") | (.blocked // 0)] | first) // 0' "$SUMMARY_BODY")"
FALLBACK_MATCHED="$(jq -r '([.modes[]? | select(.mode=="fallback_creative_time") | (.matched // 0)] | first) // 0' "$SUMMARY_BODY")"
FALLBACK_UNMATCHED="$(jq -r '([.modes[]? | select(.mode=="fallback_creative_time") | (.unmatched // 0)] | first) // 0' "$SUMMARY_BODY")"
FALLBACK_MATCH_RATE="$(jq -r '([.modes[]? | select(.mode=="fallback_creative_time") | (.match_rate_pct // 0)] | first) // 0' "$SUMMARY_BODY")"
FALLBACK_AVG_CONF="$(jq -r '([.modes[]? | select(.mode=="fallback_creative_time") | (.avg_confidence // 0)] | first) // 0' "$SUMMARY_BODY")"
TOP_UNMATCHED_REASONS="$(
  jq -r '.rows // [] | group_by(.reason) | map({reason: (.[0].reason // ""), count: length}) | sort_by(-.count) | .[:5] | .[] | "- \(.reason): \(.count)"' "$UNMATCHED_BODY"
)"
TOP_MATCHED_IDS="$(
  jq -r '.rows // [] | .[:10] | .[] | "- event_id=\(.conversion_event_id) confidence=\(.confidence) creative=\(.matched_creative_id) billing=\(.matched_billing_id)"' "$MATCHED_BODY"
)"

{
  echo "# Conversion Attribution Phase-B Report"
  echo
  echo "- generated_utc: ${STAMP}"
  echo "- buyer_id: \`${BUYER_ID}\`"
  echo "- source_type: \`${SOURCE_TYPE}\`"
  echo "- window_days: \`${DAYS}\`"
  echo "- fallback_window_days: \`${FALLBACK_WINDOW_DAYS}\`"
  echo
  echo "## Summary"
  echo
  echo "- total_events: \`${TOTAL_EVENTS}\`"
  echo "- exact_clickid_blocked: \`${EXACT_BLOCKED}\`"
  echo "- fallback_matched: \`${FALLBACK_MATCHED}\`"
  echo "- fallback_unmatched: \`${FALLBACK_UNMATCHED}\`"
  echo "- fallback_match_rate_pct: \`${FALLBACK_MATCH_RATE}\`"
  echo "- fallback_avg_confidence: \`${FALLBACK_AVG_CONF}\`"
  echo
  echo "## Top Unmatched Reasons (fallback)"
  echo
  if [[ -n "$TOP_UNMATCHED_REASONS" ]]; then
    echo "$TOP_UNMATCHED_REASONS"
  else
    echo "- none"
  fi
  echo
  echo "## Top Matched Samples (fallback)"
  echo
  if [[ -n "$TOP_MATCHED_IDS" ]]; then
    echo "$TOP_MATCHED_IDS"
  else
    echo "- none"
  fi
  echo
  echo "## Artifacts"
  echo
  echo "- refresh_json: \`${REFRESH_BODY}\`"
  echo "- summary_json: \`${SUMMARY_BODY}\`"
  echo "- joins_fallback_matched_json: \`${MATCHED_BODY}\`"
  echo "- joins_fallback_unmatched_json: \`${UNMATCHED_BODY}\`"
} > "$REPORT_MD"

echo "report_md=${REPORT_MD}"
if [[ -n "$DOC_OUT" ]]; then
  DOC_OUT="$(realpath -m "$DOC_OUT")"
  mkdir -p "$(dirname "$DOC_OUT")"
  cp "$REPORT_MD" "$DOC_OUT"
  echo "report_md_copy=${DOC_OUT}"
fi
