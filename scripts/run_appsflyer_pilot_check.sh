#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-2222222222}"
SOURCE_TYPE="${CATSCAN_CONVERSION_SOURCE_TYPE:-appsflyer}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://your-deployment.example.com/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
API_TOKEN="${CATSCAN_API_TOKEN:-}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-60}"
DAYS="${CATSCAN_ATTRIBUTION_DAYS:-14}"
FRESHNESS_HOURS="${CATSCAN_CONVERSION_FRESHNESS_HOURS:-72}"
SCAN_LIMIT="${CATSCAN_CLICK_MACRO_SCAN_LIMIT:-3000}"
OUT_DIR="${CATSCAN_OUTPUT_DIR:-/tmp}"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_appsflyer_pilot_check.sh [options]

Runs end-to-end pilot checks for Customer Delta AppsFlyer onboarding:
1) /health version
2) /creatives/click-macro-coverage summary
3) /conversions/readiness
4) /conversions/attribution/summary
5) /conversions/attribution/joins (exact matched sample)

Options:
  --buyer-id <id>            Buyer ID (default: 2222222222)
  --source-type <name>       Conversion source type (default: appsflyer)
  --base-url <url>           API base URL (default: https://your-deployment.example.com/api)
  --email <email>            X-Email identity (default: CATSCAN_CANARY_EMAIL)
  --token <token>            Bearer token (overrides --email)
  --timeout <seconds>        Curl timeout per request (default: 60)
  --days <n>                 Lookback window in days (default: 14)
  --freshness-hours <n>      Readiness freshness threshold (default: 72)
  --scan-limit <n>           Click macro coverage scan limit (default: 3000)
  --out-dir <dir>            Output root (default: /tmp)
  -h, --help                 Show help

Examples:
  export CATSCAN_CANARY_EMAIL="user@example.com"
  scripts/run_appsflyer_pilot_check.sh

  scripts/run_appsflyer_pilot_check.sh --buyer-id 2222222222 --days 30
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
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --email)
      CANARY_EMAIL="${2:-}"
      shift 2
      ;;
    --token)
      API_TOKEN="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    --freshness-hours)
      FRESHNESS_HOURS="${2:-}"
      shift 2
      ;;
    --scan-limit)
      SCAN_LIMIT="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
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
if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 5 || TIMEOUT_SECONDS > 600 )); then
  echo "Invalid --timeout '${TIMEOUT_SECONDS}' (expected 5..600)." >&2
  exit 2
fi
if ! [[ "$DAYS" =~ ^[0-9]+$ ]] || (( DAYS < 1 || DAYS > 365 )); then
  echo "Invalid --days '${DAYS}' (expected 1..365)." >&2
  exit 2
fi
if ! [[ "$FRESHNESS_HOURS" =~ ^[0-9]+$ ]] || (( FRESHNESS_HOURS < 1 || FRESHNESS_HOURS > 720 )); then
  echo "Invalid --freshness-hours '${FRESHNESS_HOURS}' (expected 1..720)." >&2
  exit 2
fi
if ! [[ "$SCAN_LIMIT" =~ ^[0-9]+$ ]] || (( SCAN_LIMIT < 100 || SCAN_LIMIT > 10000 )); then
  echo "Invalid --scan-limit '${SCAN_LIMIT}' (expected 100..10000)." >&2
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

BASE_URL="${BASE_URL%/}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${OUT_DIR%/}/appsflyer-pilot-check-${BUYER_ID}-${STAMP}"
mkdir -p "$RUN_DIR"

declare -a AUTH_HEADERS=()
if [[ -n "$API_TOKEN" ]]; then
  AUTH_HEADERS=(-H "Authorization: Bearer ${API_TOKEN}")
elif [[ -n "$CANARY_EMAIL" ]]; then
  AUTH_HEADERS=(-H "X-Email: ${CANARY_EMAIL}")
else
  echo "Provide --token or --email (or set CATSCAN_CANARY_EMAIL)." >&2
  exit 2
fi

api_get() {
  local path="$1"
  local body_file="$2"
  local code_file="$3"
  : > "$body_file"
  set +e
  curl -sS -m "$TIMEOUT_SECONDS" \
    "${AUTH_HEADERS[@]}" \
    -o "$body_file" \
    -w "%{http_code}\n" \
    "${BASE_URL}${path}" > "$code_file" 2> "${code_file}.stderr"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    echo "curl_exit_${rc}" > "$code_file"
    if [[ ! -s "$body_file" ]]; then
      echo "curl failed for ${path} (exit ${rc})" > "$body_file"
    fi
  fi
}

echo "Run dir: ${RUN_DIR}"
echo "Buyer: ${BUYER_ID}"
echo "Source type: ${SOURCE_TYPE}"
echo "Base URL: ${BASE_URL}"
echo

echo "[1/5] Health version..."
health_body="${RUN_DIR}/health.json"
health_code="${RUN_DIR}/health.http"
api_get "/health" "$health_body" "$health_code"
echo "health_http=$(cat "$health_code")"

echo
echo "[2/5] Click macro + AppsFlyer coverage..."
macro_body="${RUN_DIR}/click_macro_coverage.json"
macro_code="${RUN_DIR}/click_macro_coverage.http"
api_get "/creatives/click-macro-coverage?buyer_id=${BUYER_ID}&limit=1&scan_limit=${SCAN_LIMIT}" "$macro_body" "$macro_code"
echo "click_macro_coverage_http=$(cat "$macro_code")"

echo
echo "[3/5] Conversion readiness..."
readiness_body="${RUN_DIR}/conversion_readiness.json"
readiness_code="${RUN_DIR}/conversion_readiness.http"
api_get "/conversions/readiness?buyer_id=${BUYER_ID}&days=${DAYS}&freshness_hours=${FRESHNESS_HOURS}" "$readiness_body" "$readiness_code"
echo "conversion_readiness_http=$(cat "$readiness_code")"

echo
echo "[4/5] Attribution summary..."
summary_body="${RUN_DIR}/attribution_summary.json"
summary_code="${RUN_DIR}/attribution_summary.http"
api_get "/conversions/attribution/summary?buyer_id=${BUYER_ID}&source_type=${SOURCE_TYPE}&days=${DAYS}" "$summary_body" "$summary_code"
echo "attribution_summary_http=$(cat "$summary_code")"

echo
echo "[5/5] Exact matched joins sample..."
joins_body="${RUN_DIR}/attribution_joins_exact_matched.json"
joins_code="${RUN_DIR}/attribution_joins_exact_matched.http"
api_get "/conversions/attribution/joins?buyer_id=${BUYER_ID}&source_type=${SOURCE_TYPE}&days=${DAYS}&join_mode=exact_clickid&join_status=matched&limit=10&offset=0" "$joins_body" "$joins_code"
echo "attribution_joins_http=$(cat "$joins_code")"

fail=0
for code_path in "$health_code" "$macro_code" "$readiness_code" "$summary_code" "$joins_code"; do
  code="$(cat "$code_path")"
  if [[ "$code" != "200" ]]; then
    fail=1
  fi
done

version="$(jq -r '.version // "unknown"' "$health_body" 2>/dev/null || echo "unknown")"
state_ready="$(jq -r '.state // "unknown"' "$readiness_body" 2>/dev/null || echo "unknown")"
accepted_total="$(jq -r '.accepted_total // 0' "$readiness_body" 2>/dev/null || echo "0")"

macro_with_click="$(jq -r '.summary.creatives_with_click_macro // 0' "$macro_body" 2>/dev/null || echo "0")"
macro_without_click="$(jq -r '.summary.creatives_without_click_macro // 0' "$macro_body" 2>/dev/null || echo "0")"
macro_with_af="$(jq -r '.summary.creatives_with_appsflyer_url // 0' "$macro_body" 2>/dev/null || echo "0")"
macro_with_af_clickid="$(jq -r '.summary.creatives_with_appsflyer_clickid // 0' "$macro_body" 2>/dev/null || echo "0")"

total_events="$(jq -r '.total_events // 0' "$summary_body" 2>/dev/null || echo "0")"
exact_matched="$(jq -r '([.modes[]? | select(.mode=="exact_clickid") | .matched] | first) // 0' "$summary_body" 2>/dev/null || echo "0")"
exact_total="$(jq -r '([.modes[]? | select(.mode=="exact_clickid") | .total] | first) // 0' "$summary_body" 2>/dev/null || echo "0")"
exact_match_rate="$(jq -r '([.modes[]? | select(.mode=="exact_clickid") | .match_rate_pct] | first) // 0' "$summary_body" 2>/dev/null || echo "0")"

exact_ready=0
if (( macro_with_af_clickid > 0 )); then
  exact_ready=1
fi

exact_live=0
if (( exact_matched > 0 )) && (( total_events > 0 )); then
  exact_live=1
fi

report_md="${RUN_DIR}/pilot_check_report.md"
cat > "$report_md" <<REPORT
# AppsFlyer Pilot Check

- generated_utc: ${STAMP}
- buyer_id: \`${BUYER_ID}\`
- source_type: \`${SOURCE_TYPE}\`
- api_version: \`${version}\`
- days: \`${DAYS}\`

## Endpoint status

- health_http: \`$(cat "$health_code")\`
- click_macro_coverage_http: \`$(cat "$macro_code")\`
- conversion_readiness_http: \`$(cat "$readiness_code")\`
- attribution_summary_http: \`$(cat "$summary_code")\`
- attribution_joins_http: \`$(cat "$joins_code")\`

## Readiness summary

- creatives_with_click_macro: \`${macro_with_click}\`
- creatives_without_click_macro: \`${macro_without_click}\`
- creatives_with_appsflyer_url: \`${macro_with_af}\`
- creatives_with_appsflyer_clickid: \`${macro_with_af_clickid}\`
- conversion_readiness_state: \`${state_ready}\`
- conversion_accepted_total: \`${accepted_total}\`
- attribution_total_events: \`${total_events}\`
- exact_clickid_matched: \`${exact_matched}\`
- exact_clickid_total: \`${exact_total}\`
- exact_clickid_match_rate_pct: \`${exact_match_rate}\`

## Pilot gates

- exact_ready_for_ingestion: \`${exact_ready}\`
- exact_join_live: \`${exact_live}\`

## Artifacts

- health_json: \`${health_body}\`
- click_macro_coverage_json: \`${macro_body}\`
- conversion_readiness_json: \`${readiness_body}\`
- attribution_summary_json: \`${summary_body}\`
- attribution_joins_exact_matched_json: \`${joins_body}\`
REPORT

echo
echo "report_md=${report_md}"
echo "exact_ready_for_ingestion=${exact_ready}"
echo "exact_join_live=${exact_live}"

if [[ "$fail" -ne 0 ]]; then
  echo "Result: FAIL (one or more endpoint checks failed)."
  exit 1
fi

echo "Result: PASS"
