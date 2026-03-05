#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://your-deployment.example.com/api}"
DAYS="${CATSCAN_CANARY_DAYS:-14}"
FRESHNESS_HOURS="${CATSCAN_CANARY_FRESHNESS_HOURS:-72}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-30}"
EVENT_NAME="${CATSCAN_CANARY_EVENT_NAME:-canary_purchase}"
EVENT_VALUE="${CATSCAN_CANARY_EVENT_VALUE:-1}"
CURRENCY="${CATSCAN_CANARY_CURRENCY:-USD}"
RUN_STRICT=1
RUN_BYOM=1
ENSURE_ACTIVE_MODEL=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_v1_strict_exit0_steps.sh [options]

Runs strict-exit-0 preflight steps for a buyer:
1) Probe runtime blockers:
   - /system/data-health
   - /optimizer/economics/efficiency
2) Send one conversion pixel event and check readiness/stats.
3) Inspect optimizer models (optionally ensure an active model).
4) Run strict closeout dispatch.

Options:
  --buyer-id <id>              Buyer id (required)
  --base-url <url>             API base URL (default: https://your-deployment.example.com/api)
  --days <n>                   Lookback days for economics/readiness/stats (default: 14)
  --freshness-hours <n>        Conversion readiness freshness hours (default: 72)
  --timeout <seconds>          Curl timeout (default: 30)
  --event-name <name>          Pixel event name (default: canary_purchase)
  --event-value <value>        Pixel event value (default: 1)
  --currency <code>            Pixel currency (default: USD)
  --no-byom                    Strict closeout run without --run-byom
  --no-strict-rerun            Skip final strict closeout dispatch
  --ensure-active-model        If none active, activate first inactive model or create rules model
  --dry-run                    Print planned actions only
  -h, --help                   Show help

Environment:
  CATSCAN_CANARY_EMAIL or CATSCAN_CANARY_BEARER_TOKEN
    Used as X-Email header for authenticated API endpoints.
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
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    --freshness-hours)
      FRESHNESS_HOURS="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --event-name)
      EVENT_NAME="${2:-}"
      shift 2
      ;;
    --event-value)
      EVENT_VALUE="${2:-}"
      shift 2
      ;;
    --currency)
      CURRENCY="${2:-}"
      shift 2
      ;;
    --no-byom)
      RUN_BYOM=0
      shift
      ;;
    --no-strict-rerun)
      RUN_STRICT=0
      shift
      ;;
    --ensure-active-model)
      ENSURE_ACTIVE_MODEL=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
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

CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
BASE_URL="${BASE_URL%/}"

if [[ -z "$BUYER_ID" ]]; then
  echo "--buyer-id is required." >&2
  exit 2
fi
if [[ -z "$CANARY_EMAIL" ]]; then
  echo "Set CATSCAN_CANARY_EMAIL or CATSCAN_CANARY_BEARER_TOKEN first." >&2
  exit 2
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "'curl' is required." >&2
  exit 2
fi

HAS_JQ=0
if command -v jq >/dev/null 2>&1; then
  HAS_JQ=1
fi

if ! [[ "$DAYS" =~ ^[0-9]+$ ]] || (( DAYS < 1 || DAYS > 365 )); then
  echo "Invalid --days value: ${DAYS}" >&2
  exit 2
fi
if ! [[ "$FRESHNESS_HOURS" =~ ^[0-9]+$ ]] || (( FRESHNESS_HOURS < 1 || FRESHNESS_HOURS > 720 )); then
  echo "Invalid --freshness-hours value: ${FRESHNESS_HOURS}" >&2
  exit 2
fi
if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 5 || TIMEOUT_SECONDS > 180 )); then
  echo "Invalid --timeout value: ${TIMEOUT_SECONDS}" >&2
  exit 2
fi

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Dry run:
  buyer_id=${BUYER_ID}
  base_url=${BASE_URL}
  days=${DAYS}
  freshness_hours=${FRESHNESS_HOURS}
  timeout=${TIMEOUT_SECONDS}
  event_name=${EVENT_NAME}
  event_value=${EVENT_VALUE}
  currency=${CURRENCY}
  ensure_active_model=${ENSURE_ACTIVE_MODEL}
  run_strict_rerun=${RUN_STRICT}
  run_byom=${RUN_BYOM}
EOF
  exit 0
fi

tmp_root="$(mktemp -d /tmp/v1-strict-exit0.XXXXXX)"
trap 'rm -rf "$tmp_root"' EXIT

print_probe() {
  local path="$1"
  local body_file="$2"
  local code="$3"
  local timing="$4"
  echo "=== ${path}"
  echo "http=${code} ${timing}"
  head -c 500 "$body_file" || true
  echo
  echo
}

probe_get() {
  local path="$1"
  local body_file="$2"
  local code_file="$3"
  local timing_file="$4"
  set +e
  curl -sS -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    -o "$body_file" \
    -w "%{http_code}\n%{time_connect} %{time_starttransfer} %{time_total}\n" \
    "${BASE_URL}${path}" > "$code_file" 2> "${code_file}.stderr"
  local curl_status=$?
  set -e

  if [[ "$curl_status" -ne 0 ]]; then
    echo "curl_exit_${curl_status}" > "${code_file}.status"
    echo "n/a n/a n/a" > "$timing_file"
    if [[ -s "${code_file}.stderr" ]]; then
      cp "${code_file}.stderr" "$body_file"
    else
      echo "curl failed with exit ${curl_status}" > "$body_file"
    fi
    return 0
  fi

  sed -n '1p' "$code_file" > "${code_file}.status"
  sed -n '2p' "$code_file" > "$timing_file"
}

echo "Buyer: ${BUYER_ID}"
echo "Base URL: ${BASE_URL}"
echo

echo "[1/4] Probing runtime blocker endpoints..."
probe1_body="${tmp_root}/data_health.json"
probe1_raw="${tmp_root}/data_health.raw"
probe1_timing="${tmp_root}/data_health.timing"
probe_get "/system/data-health?buyer_id=${BUYER_ID}" "$probe1_body" "$probe1_raw" "$probe1_timing"
probe1_code="$(cat "${probe1_raw}.status")"
probe1_time="$(cat "$probe1_timing")"
print_probe "/system/data-health?buyer_id=${BUYER_ID}" "$probe1_body" "$probe1_code" "connect/ttfb/total=${probe1_time}"

probe2_body="${tmp_root}/economics_efficiency.json"
probe2_raw="${tmp_root}/economics_efficiency.raw"
probe2_timing="${tmp_root}/economics_efficiency.timing"
probe_get "/optimizer/economics/efficiency?buyer_id=${BUYER_ID}&days=${DAYS}" "$probe2_body" "$probe2_raw" "$probe2_timing"
probe2_code="$(cat "${probe2_raw}.status")"
probe2_time="$(cat "$probe2_timing")"
print_probe "/optimizer/economics/efficiency?buyer_id=${BUYER_ID}&days=${DAYS}" "$probe2_body" "$probe2_code" "connect/ttfb/total=${probe2_time}"

echo "[2/4] Sending canary conversion pixel event and checking readiness..."
event_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
pixel_headers="${tmp_root}/pixel.headers"
pixel_body="${tmp_root}/pixel.body"
pixel_code="$(curl -sS -m "$TIMEOUT_SECONDS" \
  -H "X-Email: ${CANARY_EMAIL}" \
  -D "$pixel_headers" \
  -o "$pixel_body" \
  -w "%{http_code}" \
  "${BASE_URL}/conversions/pixel?buyer_id=${BUYER_ID}&source_type=pixel&event_name=${EVENT_NAME}&event_value=${EVENT_VALUE}&currency=${CURRENCY}&event_ts=${event_ts}")"
pixel_status="$(awk -F': ' 'tolower($1)=="x-catscan-conversion-status"{print $2}' "$pixel_headers" | tr -d '\r' | tail -n1)"
echo "pixel_http=${pixel_code} x-catscan-conversion-status=${pixel_status:-unknown}"

readiness_body="${tmp_root}/readiness.json"
readiness_code="$(curl -sS -m "$TIMEOUT_SECONDS" \
  -H "X-Email: ${CANARY_EMAIL}" \
  -o "$readiness_body" \
  -w "%{http_code}" \
  "${BASE_URL}/conversions/readiness?buyer_id=${BUYER_ID}&days=${DAYS}&freshness_hours=${FRESHNESS_HOURS}")"
echo "readiness_http=${readiness_code}"
if [[ "$HAS_JQ" == "1" ]]; then
  readiness_state="$(jq -r '.state // "unknown"' "$readiness_body" 2>/dev/null || echo "unknown")"
  readiness_acc="$(jq -r '.accepted_total // 0' "$readiness_body" 2>/dev/null || echo "0")"
  echo "readiness_state=${readiness_state} accepted_total=${readiness_acc}"
else
  head -c 500 "$readiness_body"; echo
fi

stats_body="${tmp_root}/ingestion_stats.json"
stats_code="$(curl -sS -m "$TIMEOUT_SECONDS" \
  -H "X-Email: ${CANARY_EMAIL}" \
  -o "$stats_body" \
  -w "%{http_code}" \
  "${BASE_URL}/conversions/ingestion/stats?buyer_id=${BUYER_ID}&days=${DAYS}")"
echo "ingestion_stats_http=${stats_code}"
if [[ "$HAS_JQ" == "1" ]]; then
  stats_acc="$(jq -r '.accepted_total // 0' "$stats_body" 2>/dev/null || echo "0")"
  stats_rej="$(jq -r '.rejected_total // 0' "$stats_body" 2>/dev/null || echo "0")"
  echo "stats accepted_total=${stats_acc} rejected_total=${stats_rej}"
else
  head -c 500 "$stats_body"; echo
fi
echo

echo "[3/4] Checking optimizer model state..."
models_body="${tmp_root}/models.json"
models_code="$(curl -sS -m "$TIMEOUT_SECONDS" \
  -H "X-Email: ${CANARY_EMAIL}" \
  -o "$models_body" \
  -w "%{http_code}" \
  "${BASE_URL}/optimizer/models?buyer_id=${BUYER_ID}&include_inactive=true&limit=50")"
echo "models_http=${models_code}"

active_count="unknown"
first_inactive_model_id=""
if [[ "$HAS_JQ" == "1" ]]; then
  active_count="$(jq -r '[.rows[]? | select(.is_active==true)] | length' "$models_body" 2>/dev/null || echo "unknown")"
  first_inactive_model_id="$(jq -r '[.rows[]? | select(.is_active!=true)][0].model_id // ""' "$models_body" 2>/dev/null || true)"
  echo "active_model_count=${active_count}"
else
  head -c 500 "$models_body"; echo
fi

if [[ "$ENSURE_ACTIVE_MODEL" == "1" && "$HAS_JQ" == "1" ]]; then
  if [[ "$active_count" == "0" ]]; then
    echo "No active model found; ensuring one exists..."
    if [[ -n "$first_inactive_model_id" ]]; then
      echo "Activating existing model: ${first_inactive_model_id}"
      curl -sS -m "$TIMEOUT_SECONDS" \
        -H "X-Email: ${CANARY_EMAIL}" \
        -X POST \
        "${BASE_URL}/optimizer/models/${first_inactive_model_id}/activate?buyer_id=${BUYER_ID}" \
        > "${tmp_root}/activate_model.json"
    else
      echo "Creating fallback active rules model..."
      curl -sS -m "$TIMEOUT_SECONDS" \
        -H "X-Email: ${CANARY_EMAIL}" \
        -H "Content-Type: application/json" \
        -X POST \
        "${BASE_URL}/optimizer/models" \
        -d "{
          \"buyer_id\": \"${BUYER_ID}\",
          \"name\": \"strict-canary-rules\",
          \"description\": \"Rules model for strict closeout precondition\",
          \"model_type\": \"rules\",
          \"is_active\": true,
          \"input_schema\": {},
          \"output_schema\": {}
        }" > "${tmp_root}/create_model.json"
    fi

    curl -sS -m "$TIMEOUT_SECONDS" \
      -H "X-Email: ${CANARY_EMAIL}" \
      -o "$models_body" \
      "${BASE_URL}/optimizer/models?buyer_id=${BUYER_ID}&include_inactive=true&limit=50"
    active_count="$(jq -r '[.rows[]? | select(.is_active==true)] | length' "$models_body" 2>/dev/null || echo "unknown")"
    echo "active_model_count_after_ensure=${active_count}"
  fi
fi
echo

if [[ "$RUN_STRICT" == "1" ]]; then
  echo "[4/4] Running strict closeout dispatch..."
  if [[ ! -x scripts/run_v1_closeout_deployed_dispatch.sh ]]; then
    echo "Missing required helper: scripts/run_v1_closeout_deployed_dispatch.sh" >&2
    exit 2
  fi
  closeout_cmd=(scripts/run_v1_closeout_deployed_dispatch.sh --buyer-id "$BUYER_ID" --allow-blocked false)
  if [[ "$RUN_BYOM" == "1" ]]; then
    closeout_cmd+=(--run-byom)
  fi
  "${closeout_cmd[@]}"
else
  echo "[4/4] Strict closeout rerun skipped (--no-strict-rerun)."
fi
