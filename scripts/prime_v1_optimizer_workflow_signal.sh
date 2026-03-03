#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-30}"
REFRESH_TIMEOUT_SECONDS="${CATSCAN_PRIME_REFRESH_TIMEOUT_SECONDS:-}"
EVENT_COUNT="${CATSCAN_PRIME_EVENT_COUNT:-20}"
EVENT_NAME="${CATSCAN_PRIME_EVENT_NAME:-purchase}"
SOURCE_TYPE="${CATSCAN_PRIME_SOURCE_TYPE:-pixel}"
EVENT_VALUE="${CATSCAN_PRIME_EVENT_VALUE:-1}"
CURRENCY="${CATSCAN_PRIME_CURRENCY:-USD}"
BILLING_ID="${CATSCAN_PRIME_BILLING_ID:-}"
AUTO_RESOLVE_BILLING_ID="${CATSCAN_PRIME_AUTO_RESOLVE_BILLING_ID:-1}"
COUNTRY="${CATSCAN_PRIME_COUNTRY:-}"
PUBLISHER_ID="${CATSCAN_PRIME_PUBLISHER_ID:-}"
APP_ID="${CATSCAN_PRIME_APP_ID:-}"
REFRESH_DAYS="${CATSCAN_PRIME_REFRESH_DAYS:-1}"
MODEL_ID="${CATSCAN_MODEL_ID:-}"
WORKFLOW_DAYS="${CATSCAN_CANARY_WORKFLOW_DAYS:-7}"
WORKFLOW_SCORE_LIMIT="${CATSCAN_CANARY_WORKFLOW_SCORE_LIMIT:-2000}"
WORKFLOW_PROPOSAL_LIMIT="${CATSCAN_CANARY_WORKFLOW_PROPOSAL_LIMIT:-400}"
WORKFLOW_MIN_CONFIDENCE="${CATSCAN_CANARY_WORKFLOW_MIN_CONFIDENCE:-0.2}"
WORKFLOW_MAX_DELTA_PCT="${CATSCAN_CANARY_WORKFLOW_MAX_DELTA_PCT:-0.5}"
WORKFLOW_PROFILE="${CATSCAN_CANARY_PROFILE:-aggressive}"
SLEEP_SECONDS="${CATSCAN_PRIME_SLEEP_SECONDS:-0.05}"
POST_REFRESH_WAIT_SECONDS="${CATSCAN_PRIME_POST_REFRESH_WAIT_SECONDS:-240}"
POLL_INTERVAL_SECONDS="${CATSCAN_PRIME_POLL_INTERVAL_SECONDS:-10}"
OUT_DIR="${CATSCAN_OUTPUT_DIR:-/tmp}"

usage() {
  cat <<'EOF'
Usage:
  scripts/prime_v1_optimizer_workflow_signal.sh --buyer-id <id> [options]

Seeds conversion signal for optimizer workflow, refreshes aggregates, and verifies
that score-and-propose can produce top proposals.

Steps:
1) Send N conversion pixel events (same segment keys).
2) Refresh conversion aggregates for buyer.
3) Check aggregate rows and event_count.
4) Run score-and-propose and print counters.

Options:
  --buyer-id <id>                 Required buyer_id
  --base-url <url>                API base URL (default: https://scan.rtb.cat/api)
  --email <email>                 X-Email identity (default: env CATSCAN_CANARY_EMAIL)
  --timeout <seconds>             HTTP timeout per request (default: 30)
  --refresh-timeout <seconds>     Timeout for aggregates refresh (default: --timeout)
  --event-count <n>               Number of pixel events to emit (default: 20)
  --event-name <name>             Event name (default: purchase)
  --source-type <type>            Conversion source_type (default: pixel)
  --event-value <value>           Event value (default: 1)
  --currency <code>               Currency code (default: USD)
  --billing-id <id>               Optional stable billing_id dimension
  --auto-resolve-billing-id <bool>
                                  Auto-pick billing_id from pretargeting config when missing (default: true)
  --country <code>                Optional stable country dimension
  --publisher-id <id>             Optional stable publisher_id dimension
  --app-id <id>                   Optional stable app_id dimension
  --refresh-days <n>              Days window for aggregate refresh (default: 1)
  --model-id <id>                 Optional model_id override (auto-resolve active if omitted)
  --workflow-days <n>             score-and-propose days (default: 7)
  --score-limit <n>               score-and-propose score_limit (default: 2000)
  --proposal-limit <n>            score-and-propose proposal_limit (default: 400)
  --min-confidence <float>        score-and-propose min_confidence (default: 0.2)
  --max-delta-pct <float>         score-and-propose max_delta_pct (default: 0.5)
  --profile <safe|balanced|aggressive>
                                  score-and-propose profile (default: aggressive)
  --sleep-seconds <n>             Delay between pixel calls (default: 0.05)
  --post-refresh-wait <seconds>   Poll window after refresh timeout (default: 240)
  --poll-interval <seconds>       Poll interval while waiting (default: 10)
  --out-dir <dir>                 Output directory root (default: /tmp)
  -h, --help                      Show help

Exit code:
  0 when top_proposals_count > 0
  1 otherwise
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buyer-id) BUYER_ID="${2:-}"; shift 2 ;;
    --base-url) BASE_URL="${2:-}"; shift 2 ;;
    --email) CANARY_EMAIL="${2:-}"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="${2:-}"; shift 2 ;;
    --refresh-timeout) REFRESH_TIMEOUT_SECONDS="${2:-}"; shift 2 ;;
    --event-count) EVENT_COUNT="${2:-}"; shift 2 ;;
    --event-name) EVENT_NAME="${2:-}"; shift 2 ;;
    --source-type) SOURCE_TYPE="${2:-}"; shift 2 ;;
    --event-value) EVENT_VALUE="${2:-}"; shift 2 ;;
    --currency) CURRENCY="${2:-}"; shift 2 ;;
    --billing-id) BILLING_ID="${2:-}"; shift 2 ;;
    --auto-resolve-billing-id) AUTO_RESOLVE_BILLING_ID="${2:-}"; shift 2 ;;
    --country) COUNTRY="${2:-}"; shift 2 ;;
    --publisher-id) PUBLISHER_ID="${2:-}"; shift 2 ;;
    --app-id) APP_ID="${2:-}"; shift 2 ;;
    --refresh-days) REFRESH_DAYS="${2:-}"; shift 2 ;;
    --model-id) MODEL_ID="${2:-}"; shift 2 ;;
    --workflow-days) WORKFLOW_DAYS="${2:-}"; shift 2 ;;
    --score-limit) WORKFLOW_SCORE_LIMIT="${2:-}"; shift 2 ;;
    --proposal-limit) WORKFLOW_PROPOSAL_LIMIT="${2:-}"; shift 2 ;;
    --min-confidence) WORKFLOW_MIN_CONFIDENCE="${2:-}"; shift 2 ;;
    --max-delta-pct) WORKFLOW_MAX_DELTA_PCT="${2:-}"; shift 2 ;;
    --profile) WORKFLOW_PROFILE="${2:-}"; shift 2 ;;
    --sleep-seconds) SLEEP_SECONDS="${2:-}"; shift 2 ;;
    --post-refresh-wait) POST_REFRESH_WAIT_SECONDS="${2:-}"; shift 2 ;;
    --poll-interval) POLL_INTERVAL_SECONDS="${2:-}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

parse_bool() {
  local value="${1:-}"
  case "${value,,}" in
    1|true|yes|y|on) echo "1" ;;
    0|false|no|n|off) echo "0" ;;
    *)
      echo "Invalid boolean '${value}' (expected true/false)." >&2
      exit 2
      ;;
  esac
}

if [[ -z "$BUYER_ID" ]]; then
  echo "--buyer-id is required." >&2
  exit 2
fi
if [[ -z "$CANARY_EMAIL" ]]; then
  echo "Provide --email or set CATSCAN_CANARY_EMAIL/CATSCAN_CANARY_BEARER_TOKEN." >&2
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
if ! [[ "$EVENT_COUNT" =~ ^[0-9]+$ ]] || (( EVENT_COUNT < 1 )); then
  echo "Invalid --event-count '${EVENT_COUNT}'." >&2
  exit 2
fi
if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 5 )); then
  echo "Invalid --timeout '${TIMEOUT_SECONDS}'." >&2
  exit 2
fi
if [[ -z "$REFRESH_TIMEOUT_SECONDS" ]]; then
  REFRESH_TIMEOUT_SECONDS="$TIMEOUT_SECONDS"
fi
if ! [[ "$REFRESH_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( REFRESH_TIMEOUT_SECONDS < 5 )); then
  echo "Invalid --refresh-timeout '${REFRESH_TIMEOUT_SECONDS}'." >&2
  exit 2
fi
if ! [[ "$REFRESH_DAYS" =~ ^[0-9]+$ ]] || (( REFRESH_DAYS < 1 || REFRESH_DAYS > 365 )); then
  echo "Invalid --refresh-days '${REFRESH_DAYS}'." >&2
  exit 2
fi
if ! [[ "$POST_REFRESH_WAIT_SECONDS" =~ ^[0-9]+$ ]] || (( POST_REFRESH_WAIT_SECONDS < 0 )); then
  echo "Invalid --post-refresh-wait '${POST_REFRESH_WAIT_SECONDS}'." >&2
  exit 2
fi
AUTO_RESOLVE_BILLING_ID="$(parse_bool "$AUTO_RESOLVE_BILLING_ID")"
if ! [[ "$POLL_INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || (( POLL_INTERVAL_SECONDS < 1 )); then
  echo "Invalid --poll-interval '${POLL_INTERVAL_SECONDS}'." >&2
  exit 2
fi
case "${WORKFLOW_PROFILE,,}" in
  safe|balanced|aggressive) ;;
  *)
    echo "Invalid --profile '${WORKFLOW_PROFILE}'. Expected safe|balanced|aggressive." >&2
    exit 2
    ;;
esac

BASE_URL="${BASE_URL%/}"
RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${OUT_DIR%/}/v1-prime-workflow-signal-${BUYER_ID}-${RUN_STAMP}"
mkdir -p "$RUN_DIR"

echo "Run dir: ${RUN_DIR}"
echo "Buyer: ${BUYER_ID}"
echo "Base URL: ${BASE_URL}"
echo "X-Email: ${CANARY_EMAIL}"
echo

if [[ -z "$BILLING_ID" && "$AUTO_RESOLVE_BILLING_ID" == "1" ]]; then
  pretargeting_body="${RUN_DIR}/pretargeting_configs.json"
  pretargeting_http="$(curl -sS -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    -o "$pretargeting_body" \
    -w "%{http_code}" \
    "${BASE_URL}/settings/pretargeting?buyer_id=${BUYER_ID}&limit=500&summary_only=true")"
  if [[ "$pretargeting_http" == "200" ]]; then
    BILLING_ID="$(jq -r '
      (
        [.[]? | select(((.billing_id // "") | tostring) != "" and (((.state // "ACTIVE") | tostring | ascii_upcase) == "ACTIVE"))]
        | .[0].billing_id
      ) // (
        [.[]? | select(((.billing_id // "") | tostring) != "")]
        | .[0].billing_id
      ) // ""
    ' "$pretargeting_body" 2>/dev/null || true)"
  fi
fi
if [[ -n "$BILLING_ID" ]]; then
  echo "seed_billing_id=${BILLING_ID}"
else
  echo "seed_billing_id=(none)"
fi
echo

today_utc="$(date -u +%Y-%m-%d)"
refresh_timed_out=0

accepted=0
rejected=0

echo "[1/4] Sending ${EVENT_COUNT} conversion pixel events..."
for ((i = 1; i <= EVENT_COUNT; i++)); do
  event_id="prime-${RUN_STAMP}-${i}"
  event_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  header_file="${RUN_DIR}/pixel_${i}.headers"
  body_file="${RUN_DIR}/pixel_${i}.body"

  curl -sS --get -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    -D "$header_file" \
    -o "$body_file" \
    --data-urlencode "buyer_id=${BUYER_ID}" \
    --data-urlencode "source_type=${SOURCE_TYPE}" \
    --data-urlencode "event_name=${EVENT_NAME}" \
    --data-urlencode "event_value=${EVENT_VALUE}" \
    --data-urlencode "currency=${CURRENCY}" \
    --data-urlencode "event_ts=${event_ts}" \
    --data-urlencode "event_id=${event_id}" \
    ${BILLING_ID:+--data-urlencode "billing_id=${BILLING_ID}"} \
    ${COUNTRY:+--data-urlencode "country=${COUNTRY}"} \
    ${PUBLISHER_ID:+--data-urlencode "publisher_id=${PUBLISHER_ID}"} \
    ${APP_ID:+--data-urlencode "app_id=${APP_ID}"} \
    "${BASE_URL}/conversions/pixel" >/dev/null

  ingest_status="$(awk -F': ' 'tolower($1)=="x-catscan-conversion-status"{print $2}' "$header_file" | tr -d '\r' | tail -n1)"
  if [[ "${ingest_status,,}" == "accepted" ]]; then
    accepted=$((accepted + 1))
  else
    rejected=$((rejected + 1))
  fi
  sleep "$SLEEP_SECONDS"
done
echo "pixel_accepted=${accepted} pixel_rejected=${rejected}"
echo

echo "[2/4] Refreshing conversion aggregates..."
refresh_body="${RUN_DIR}/aggregates_refresh.json"
refresh_err="${RUN_DIR}/aggregates_refresh.err"
set +e
refresh_http="$(curl -sS -m "$REFRESH_TIMEOUT_SECONDS" -X POST \
  -H "X-Email: ${CANARY_EMAIL}" \
  -o "$refresh_body" \
  -w "%{http_code}" \
  "${BASE_URL}/conversions/aggregates/refresh?buyer_id=${BUYER_ID}&days=${REFRESH_DAYS}" \
  2>"$refresh_err")"
refresh_status=$?
set -e
if [[ "$refresh_status" -ne 0 ]]; then
  echo "aggregates_refresh_http=curl_exit_${refresh_status}"
  if [[ -s "$refresh_err" ]]; then
    echo "aggregates_refresh_error=$(tr '\n' ' ' < "$refresh_err")"
  fi
  refresh_timed_out=1
else
  echo "aggregates_refresh_http=${refresh_http}"
  if [[ "$refresh_http" == "200" ]]; then
    upserted="$(jq -r '.upserted_rows // 0' "$refresh_body" 2>/dev/null || echo "0")"
    deleted="$(jq -r '.deleted_rows // 0' "$refresh_body" 2>/dev/null || echo "0")"
    echo "aggregates_upserted_rows=${upserted} aggregates_deleted_rows=${deleted}"
  else
    echo "aggregates_refresh_body_preview=$(head -c 300 "$refresh_body" | tr '\n' ' ')"
  fi
fi
echo

echo "[3/4] Checking aggregate/scoring readiness..."
aggs_body="${RUN_DIR}/aggregates_rows.json"
fetch_aggregates_snapshot() {
  curl -sS -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    -o "$aggs_body" \
    -w "%{http_code}" \
    "${BASE_URL}/conversions/aggregates?buyer_id=${BUYER_ID}&start_date=${today_utc}&end_date=${today_utc}&source_type=${SOURCE_TYPE}&event_type=${EVENT_NAME}&limit=10"
}

aggs_http="$(fetch_aggregates_snapshot)"
echo "aggregates_http=${aggs_http}"
aggs_total="0"
top_event_count="0"
if [[ "$aggs_http" == "200" ]]; then
  aggs_total="$(jq -r '.meta.total // 0' "$aggs_body" 2>/dev/null || echo "0")"
  top_event_count="$(jq -r '(.rows // [])[0].event_count // 0' "$aggs_body" 2>/dev/null || echo "0")"
  echo "aggregates_total=${aggs_total} top_row_event_count=${top_event_count} (today=${today_utc})"
else
  echo "aggregates_body_preview=$(head -c 300 "$aggs_body" | tr '\n' ' ')"
fi

if [[ "$refresh_timed_out" == "1" && "$aggs_total" == "0" && "$POST_REFRESH_WAIT_SECONDS" -gt 0 ]]; then
  echo "Refresh timed out; polling aggregates for up to ${POST_REFRESH_WAIT_SECONDS}s..."
  deadline=$((SECONDS + POST_REFRESH_WAIT_SECONDS))
  while (( SECONDS < deadline )); do
    sleep "$POLL_INTERVAL_SECONDS"
    aggs_http="$(fetch_aggregates_snapshot)"
    if [[ "$aggs_http" != "200" ]]; then
      continue
    fi
    aggs_total="$(jq -r '.meta.total // 0' "$aggs_body" 2>/dev/null || echo "0")"
    top_event_count="$(jq -r '(.rows // [])[0].event_count // 0' "$aggs_body" 2>/dev/null || echo "0")"
    echo "poll aggregates_total=${aggs_total} top_row_event_count=${top_event_count}"
    if [[ "$aggs_total" =~ ^[0-9]+$ ]] && (( aggs_total > 0 )); then
      break
    fi
  done
fi

if [[ -z "$MODEL_ID" ]]; then
  models_body="${RUN_DIR}/models.json"
  models_http="$(curl -sS -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    -o "$models_body" \
    -w "%{http_code}" \
    "${BASE_URL}/optimizer/models?buyer_id=${BUYER_ID}&include_inactive=true&limit=200&offset=0")"
  echo "models_http=${models_http}"
  if [[ "$models_http" == "200" ]]; then
    MODEL_ID="$(jq -r '.rows // [] | map(select(.is_active == true)) | .[0].model_id // ""' "$models_body" 2>/dev/null || true)"
  fi
fi
if [[ -z "$MODEL_ID" ]]; then
  echo "No active model found; cannot run score-and-propose." >&2
  exit 1
fi
echo "model_id=${MODEL_ID}"
echo

echo "[4/4] Running score-and-propose..."
workflow_body="${RUN_DIR}/score_and_propose.json"
workflow_http="$(curl -sS -m "$TIMEOUT_SECONDS" -X POST \
  -H "X-Email: ${CANARY_EMAIL}" \
  -o "$workflow_body" \
  -w "%{http_code}" \
  "${BASE_URL}/optimizer/workflows/score-and-propose?buyer_id=${BUYER_ID}&model_id=${MODEL_ID}&days=${WORKFLOW_DAYS}&score_limit=${WORKFLOW_SCORE_LIMIT}&proposal_limit=${WORKFLOW_PROPOSAL_LIMIT}&min_confidence=${WORKFLOW_MIN_CONFIDENCE}&max_delta_pct=${WORKFLOW_MAX_DELTA_PCT}&profile=${WORKFLOW_PROFILE}")"
echo "workflow_http=${workflow_http}"
if [[ "$workflow_http" != "200" ]]; then
  echo "workflow_body_preview=$(head -c 300 "$workflow_body" | tr '\n' ' ')"
  exit 1
fi

segments_scanned="$(jq -r '.score_run.segments_scanned // 0' "$workflow_body" 2>/dev/null || echo "0")"
scores_written="$(jq -r '.score_run.scores_written // 0' "$workflow_body" 2>/dev/null || echo "0")"
scores_considered="$(jq -r '.proposal_run.scores_considered // 0' "$workflow_body" 2>/dev/null || echo "0")"
proposals_created="$(jq -r '.proposal_run.proposals_created // 0' "$workflow_body" 2>/dev/null || echo "0")"
top_count="$(jq -r '(.proposal_run.top_proposals // []) | length' "$workflow_body" 2>/dev/null || echo "0")"
first_proposal_id="$(jq -r '(.proposal_run.top_proposals // [])[0].proposal_id // ""' "$workflow_body" 2>/dev/null || true)"
echo "workflow_segments_scanned=${segments_scanned}"
echo "workflow_scores_written=${scores_written}"
echo "workflow_scores_considered=${scores_considered}"
echo "workflow_proposals_created=${proposals_created}"
echo "top_proposals_count=${top_count}"
if [[ -n "$first_proposal_id" ]]; then
  echo "first_proposal_id=${first_proposal_id}"
else
  echo "first_proposal_id=(none)"
fi

echo
echo "Artifacts written under: ${RUN_DIR}"
if [[ "$top_count" =~ ^[0-9]+$ ]] && (( top_count > 0 )); then
  echo "Result: PASS (workflow now generates proposals)"
  exit 0
fi

echo "Result: FAIL (no top proposals yet)"
if [[ -z "$BILLING_ID" ]]; then
  echo "Hint: no billing_id was seeded; proposals require billing_id-backed scores."
  echo "      Re-run with --billing-id <active_config_billing_id> (or keep --auto-resolve-billing-id true)."
fi
if [[ "$refresh_timed_out" == "1" ]]; then
  echo "Hint: refresh timed out; if this persists, run with --refresh-days 1 and longer --refresh-timeout, or debug /conversions/aggregates/refresh query path."
fi
exit 1
