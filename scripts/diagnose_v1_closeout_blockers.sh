#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://your-deployment.example.com/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-120}"
ECON_DAYS="${CATSCAN_CANARY_ECON_DAYS:-7}"
WORKFLOW_DAYS="${CATSCAN_CANARY_WORKFLOW_DAYS:-30}"
WORKFLOW_SCORE_LIMIT="${CATSCAN_CANARY_WORKFLOW_SCORE_LIMIT:-5000}"
WORKFLOW_PROPOSAL_LIMIT="${CATSCAN_CANARY_WORKFLOW_PROPOSAL_LIMIT:-1000}"
WORKFLOW_MIN_CONFIDENCE="${CATSCAN_CANARY_WORKFLOW_MIN_CONFIDENCE:-0.0}"
WORKFLOW_MAX_DELTA_PCT="${CATSCAN_CANARY_WORKFLOW_MAX_DELTA_PCT:-1.0}"
WORKFLOW_PROFILE="${CATSCAN_CANARY_PROFILE:-aggressive}"
OUTPUT_DIR="${CATSCAN_OUTPUT_DIR:-/tmp}"

usage() {
  cat <<'EOF'
Usage:
  scripts/diagnose_v1_closeout_blockers.sh --buyer-id <id> [options]

Runs one-pass diagnostics for current strict closeout blockers:
1) Probes data-health and optimizer economics with timing.
2) Lists optimizer models and resolves active model.
3) Isolates optimizer economics sub-endpoints (effective-cpm, assumed-value).
4) Executes score-and-propose with wide/aggressive params and prints internal counters.
5) Prints a blocker summary.

Options:
  --buyer-id <id>                 Required buyer_id
  --base-url <url>                API base URL (default: https://your-deployment.example.com/api)
  --email <email>                 X-Email identity (default from CATSCAN_CANARY_EMAIL/CATSCAN_CANARY_BEARER_TOKEN)
  --timeout <seconds>             Curl timeout per request (default: 120)
  --econ-days <n>                 Days for economics endpoint probes (default: 7)
  --workflow-days <n>             score-and-propose days (default: 30)
  --score-limit <n>               score-and-propose score_limit (default: 5000)
  --proposal-limit <n>            score-and-propose proposal_limit (default: 1000)
  --min-confidence <float>        score-and-propose min_confidence (default: 0.0)
  --max-delta-pct <float>         score-and-propose max_delta_pct (default: 1.0)
  --profile <safe|balanced|aggressive>
                                  score-and-propose profile (default: aggressive)
  --out-dir <dir>                 output directory (default: /tmp)
  -h, --help                      Show help

Examples:
  scripts/diagnose_v1_closeout_blockers.sh --buyer-id 1111111111
  scripts/diagnose_v1_closeout_blockers.sh --buyer-id 1111111111 --timeout 180 --profile aggressive
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buyer-id)
      BUYER_ID="${2:-}"
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
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --econ-days)
      ECON_DAYS="${2:-}"
      shift 2
      ;;
    --workflow-days)
      WORKFLOW_DAYS="${2:-}"
      shift 2
      ;;
    --score-limit)
      WORKFLOW_SCORE_LIMIT="${2:-}"
      shift 2
      ;;
    --proposal-limit)
      WORKFLOW_PROPOSAL_LIMIT="${2:-}"
      shift 2
      ;;
    --min-confidence)
      WORKFLOW_MIN_CONFIDENCE="${2:-}"
      shift 2
      ;;
    --max-delta-pct)
      WORKFLOW_MAX_DELTA_PCT="${2:-}"
      shift 2
      ;;
    --profile)
      WORKFLOW_PROFILE="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUTPUT_DIR="${2:-}"
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
if [[ -z "$CANARY_EMAIL" ]]; then
  echo "Provide --email or set CATSCAN_CANARY_EMAIL (or CATSCAN_CANARY_BEARER_TOKEN)." >&2
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

case "${WORKFLOW_PROFILE,,}" in
  safe|balanced|aggressive) ;;
  *)
    echo "Invalid --profile '${WORKFLOW_PROFILE}'. Expected safe|balanced|aggressive." >&2
    exit 2
    ;;
esac

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 5 )); then
  echo "Invalid --timeout '${TIMEOUT_SECONDS}'. Expected integer >= 5." >&2
  exit 2
fi
if ! [[ "$ECON_DAYS" =~ ^[0-9]+$ ]] || (( ECON_DAYS < 1 || ECON_DAYS > 365 )); then
  echo "Invalid --econ-days '${ECON_DAYS}'. Expected integer 1..365." >&2
  exit 2
fi

BASE_URL="${BASE_URL%/}"
RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${OUTPUT_DIR%/}/v1-closeout-diagnose-${BUYER_ID}-${RUN_STAMP}"
mkdir -p "$RUN_DIR"

meta_http_code() {
  local meta_file="$1"
  sed -n '1s/.*http=\([^ ]*\).*/\1/p' "$meta_file"
}

print_preview_if_non_200() {
  local label="$1"
  local meta_file="$2"
  local body_file="$3"
  local code
  code="$(meta_http_code "$meta_file")"
  if [[ "$code" != "200" ]]; then
    local preview
    preview="$(head -c 300 "$body_file" 2>/dev/null | tr '\n' ' ')"
    if [[ -n "$preview" ]]; then
      echo "${label}_preview=${preview}"
    fi
  fi
}

json_or_error() {
  local method="$1"
  local path="$2"
  local out_body="$3"
  local out_meta="$4"
  set +e
  curl -sS -X "$method" -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    -o "$out_body" \
    -w "http=%{http_code} connect=%{time_connect} ttfb=%{time_starttransfer} total=%{time_total}\n" \
    "${BASE_URL}${path}" > "$out_meta" 2>"${out_meta}.stderr"
  local curl_status=$?
  set -e
  if [[ "$curl_status" -ne 0 ]]; then
    {
      echo "http=curl_exit_${curl_status} connect=n/a ttfb=n/a total=n/a"
      if [[ -s "${out_meta}.stderr" ]]; then
        echo "curl_error=$(tr '\n' ' ' < "${out_meta}.stderr")"
      fi
    } > "$out_meta"
    return 0
  fi
  return 0
}

echo "Run dir: ${RUN_DIR}"
echo "Buyer: ${BUYER_ID}"
echo "Base URL: ${BASE_URL}"
echo "X-Email: ${CANARY_EMAIL}"
echo

echo "[1/5] Probing timeout-prone endpoints..."
DATA_HEALTH_BODY="${RUN_DIR}/data_health.json"
DATA_HEALTH_META="${RUN_DIR}/data_health.meta"
json_or_error "GET" "/system/data-health?buyer_id=${BUYER_ID}&days=7&limit=10" "$DATA_HEALTH_BODY" "$DATA_HEALTH_META"
echo "data_health: $(cat "$DATA_HEALTH_META")"

ECON_BODY="${RUN_DIR}/optimizer_economics.json"
ECON_META="${RUN_DIR}/optimizer_economics.meta"
json_or_error "GET" "/optimizer/economics/efficiency?buyer_id=${BUYER_ID}&days=7" "$ECON_BODY" "$ECON_META"
echo "optimizer_economics: $(cat "$ECON_META")"
print_preview_if_non_200 "optimizer_economics" "$ECON_META" "$ECON_BODY"
echo

echo "[2/5] Listing optimizer models..."
MODELS_BODY="${RUN_DIR}/models.json"
MODELS_META="${RUN_DIR}/models.meta"
json_or_error "GET" "/optimizer/models?buyer_id=${BUYER_ID}&include_inactive=true&limit=200&offset=0" "$MODELS_BODY" "$MODELS_META"
echo "models: $(cat "$MODELS_META")"

ACTIVE_MODEL_ID="$(jq -r '.rows // [] | map(select(.is_active == true)) | .[0].model_id // ""' "$MODELS_BODY" 2>/dev/null || true)"
ACTIVE_MODEL_COUNT="$(jq -r '[.rows // [] | .[] | select(.is_active == true)] | length' "$MODELS_BODY" 2>/dev/null || echo "0")"
TOTAL_MODEL_COUNT="$(jq -r '(.rows // []) | length' "$MODELS_BODY" 2>/dev/null || echo "0")"
echo "models_total=${TOTAL_MODEL_COUNT} active_models=${ACTIVE_MODEL_COUNT}"
if [[ -n "$ACTIVE_MODEL_ID" ]]; then
  echo "active_model_id=${ACTIVE_MODEL_ID}"
else
  echo "active_model_id=(none)"
fi
echo

echo "[3/5] Isolating economics sub-endpoints..."
ECON_ECPM_BODY="${RUN_DIR}/optimizer_economics_effective_cpm.json"
ECON_ECPM_META="${RUN_DIR}/optimizer_economics_effective_cpm.meta"
json_or_error "GET" "/optimizer/economics/effective-cpm?buyer_id=${BUYER_ID}&days=${ECON_DAYS}" "$ECON_ECPM_BODY" "$ECON_ECPM_META"
echo "effective_cpm: $(cat "$ECON_ECPM_META")"
print_preview_if_non_200 "effective_cpm" "$ECON_ECPM_META" "$ECON_ECPM_BODY"

ECON_AV_BODY="${RUN_DIR}/optimizer_economics_assumed_value.json"
ECON_AV_META="${RUN_DIR}/optimizer_economics_assumed_value.meta"
json_or_error "GET" "/optimizer/economics/assumed-value?buyer_id=${BUYER_ID}&days=${ECON_DAYS}" "$ECON_AV_BODY" "$ECON_AV_META"
echo "assumed_value: $(cat "$ECON_AV_META")"
print_preview_if_non_200 "assumed_value" "$ECON_AV_META" "$ECON_AV_BODY"
echo

echo "[4/5] Running score-and-propose with wide parameters..."
WORKFLOW_BODY="${RUN_DIR}/score_and_propose.json"
WORKFLOW_META="${RUN_DIR}/score_and_propose.meta"

if [[ -z "$ACTIVE_MODEL_ID" ]]; then
  echo "No active model. Skipping workflow execution."
  echo "http=skipped_no_active_model connect=n/a ttfb=n/a total=n/a" > "$WORKFLOW_META"
else
  WORKFLOW_PATH="/optimizer/workflows/score-and-propose?buyer_id=${BUYER_ID}&model_id=${ACTIVE_MODEL_ID}&days=${WORKFLOW_DAYS}&score_limit=${WORKFLOW_SCORE_LIMIT}&proposal_limit=${WORKFLOW_PROPOSAL_LIMIT}&min_confidence=${WORKFLOW_MIN_CONFIDENCE}&max_delta_pct=${WORKFLOW_MAX_DELTA_PCT}&profile=${WORKFLOW_PROFILE}"
  json_or_error "POST" "$WORKFLOW_PATH" "$WORKFLOW_BODY" "$WORKFLOW_META"
fi
echo "score_and_propose: $(cat "$WORKFLOW_META")"
print_preview_if_non_200 "score_and_propose" "$WORKFLOW_META" "$WORKFLOW_BODY"

TOP_PROPOSAL_COUNT="0"
FIRST_PROPOSAL_ID=""
SCORES_WRITTEN="0"
SEGMENTS_SCANNED="0"
SCORES_CONSIDERED="0"
PROPOSALS_CREATED="0"
if [[ -f "$WORKFLOW_BODY" ]]; then
  TOP_PROPOSAL_COUNT="$(jq -r '(.proposal_run.top_proposals // []) | length' "$WORKFLOW_BODY" 2>/dev/null || echo "0")"
  FIRST_PROPOSAL_ID="$(jq -r '(.proposal_run.top_proposals // [])[0].proposal_id // ""' "$WORKFLOW_BODY" 2>/dev/null || true)"
  SCORES_WRITTEN="$(jq -r '.score_run.scores_written // 0' "$WORKFLOW_BODY" 2>/dev/null || echo "0")"
  SEGMENTS_SCANNED="$(jq -r '.score_run.segments_scanned // 0' "$WORKFLOW_BODY" 2>/dev/null || echo "0")"
  SCORES_CONSIDERED="$(jq -r '.proposal_run.scores_considered // 0' "$WORKFLOW_BODY" 2>/dev/null || echo "0")"
  PROPOSALS_CREATED="$(jq -r '.proposal_run.proposals_created // 0' "$WORKFLOW_BODY" 2>/dev/null || echo "0")"
fi
echo "workflow_segments_scanned=${SEGMENTS_SCANNED}"
echo "workflow_scores_written=${SCORES_WRITTEN}"
echo "workflow_scores_considered=${SCORES_CONSIDERED}"
echo "workflow_proposals_created=${PROPOSALS_CREATED}"
echo "top_proposals_count=${TOP_PROPOSAL_COUNT}"
if [[ -n "$FIRST_PROPOSAL_ID" ]]; then
  echo "first_proposal_id=${FIRST_PROPOSAL_ID}"
else
  echo "first_proposal_id=(none)"
fi

if [[ -n "$ACTIVE_MODEL_ID" ]]; then
  SEGMENTS_BODY="${RUN_DIR}/scoring_segments.json"
  SEGMENTS_META="${RUN_DIR}/scoring_segments.meta"
  json_or_error "GET" "/optimizer/scoring/segments?buyer_id=${BUYER_ID}&model_id=${ACTIVE_MODEL_ID}&days=${WORKFLOW_DAYS}&limit=500&offset=0" "$SEGMENTS_BODY" "$SEGMENTS_META"
  echo "scoring_segments: $(cat "$SEGMENTS_META")"
  if [[ "$(meta_http_code "$SEGMENTS_META")" == "200" ]]; then
    SEG_ROWS="$(jq -r '(.rows // []) | length' "$SEGMENTS_BODY" 2>/dev/null || echo "0")"
    SEG_TOTAL="$(jq -r '.meta.total // 0' "$SEGMENTS_BODY" 2>/dev/null || echo "0")"
    C_GE_020="$(jq -r '[.rows // [] | .[] | select((.confidence // 0) >= 0.2)] | length' "$SEGMENTS_BODY" 2>/dev/null || echo "0")"
    C_GE_030="$(jq -r '[.rows // [] | .[] | select((.confidence // 0) >= 0.3)] | length' "$SEGMENTS_BODY" 2>/dev/null || echo "0")"
    C_GE_045="$(jq -r '[.rows // [] | .[] | select((.confidence // 0) >= 0.45)] | length' "$SEGMENTS_BODY" 2>/dev/null || echo "0")"
    echo "scoring_segments_rows=${SEG_ROWS} scoring_segments_total=${SEG_TOTAL} conf_ge_0_2=${C_GE_020} conf_ge_0_3=${C_GE_030} conf_ge_0_45=${C_GE_045}"
  else
    print_preview_if_non_200 "scoring_segments" "$SEGMENTS_META" "$SEGMENTS_BODY"
  fi
fi
echo

echo "[5/5] Blocker summary..."
FAIL_COUNT=0

if grep -q "http=200" "$DATA_HEALTH_META"; then
  echo "PASS: data-health endpoint reachable."
else
  echo "FAIL: data-health endpoint timeout/error."
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

if grep -q "http=200" "$ECON_META"; then
  echo "PASS: optimizer economics endpoint reachable."
else
  echo "FAIL: optimizer economics endpoint timeout/error."
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

if [[ "$(meta_http_code "$ECON_ECPM_META")" == "200" && "$(meta_http_code "$ECON_AV_META")" != "200" ]]; then
  echo "HINT: assumed-value appears to be the economics bottleneck."
elif [[ "$(meta_http_code "$ECON_ECPM_META")" != "200" && "$(meta_http_code "$ECON_AV_META")" == "200" ]]; then
  echo "HINT: effective-cpm appears to be the economics bottleneck."
elif [[ "$(meta_http_code "$ECON_ECPM_META")" != "200" && "$(meta_http_code "$ECON_AV_META")" != "200" ]]; then
  echo "HINT: both economics sub-endpoints are failing/slow."
fi

if [[ -z "$ACTIVE_MODEL_ID" ]]; then
  echo "FAIL: no active optimizer model."
  FAIL_COUNT=$((FAIL_COUNT + 1))
elif [[ "$TOP_PROPOSAL_COUNT" =~ ^[0-9]+$ ]] && (( TOP_PROPOSAL_COUNT > 0 )); then
  echo "PASS: score-and-propose generated top proposals."
else
  echo "FAIL: score-and-propose generated zero top proposals."
  if [[ "$SCORES_WRITTEN" =~ ^[0-9]+$ ]] && (( SCORES_WRITTEN == 0 )); then
    echo "HINT: scoring wrote zero rows (likely no conversion_aggregates_daily data in window)."
  elif [[ "$SCORES_CONSIDERED" =~ ^[0-9]+$ ]] && (( SCORES_CONSIDERED == 0 )); then
    echo "HINT: proposals considered zero scores (confidence/window/model mismatch)."
  elif [[ "$PROPOSALS_CREATED" =~ ^[0-9]+$ ]] && (( PROPOSALS_CREATED == 0 )); then
    echo "HINT: scores exist but proposal creation returned zero rows."
  fi
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo
echo "Artifacts written under: ${RUN_DIR}"
if (( FAIL_COUNT > 0 )); then
  echo "Result: FAIL (${FAIL_COUNT} blocker(s) remain)"
  exit 1
fi

echo "Result: PASS (no blocker detected by this diagnostic)"
