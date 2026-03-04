#!/usr/bin/env bash
set -euo pipefail

BUYER_ID=""
API_BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-}"
TIMEOUT_SECONDS="${CATSCAN_UNBLOCK_CHECK_TIMEOUT_SECONDS:-180}"
DAYS="${CATSCAN_UNBLOCK_CHECK_DAYS:-14}"
SINCE_HOURS="${CATSCAN_CANARY_QPS_PAGE_SLO_SINCE_HOURS:-168}"
PROFILE="${CATSCAN_CANARY_PROFILE:-balanced}"
RUN_STRICT=1
AUTO_FETCH_EVIDENCE=1

# Budgets mirror canary defaults used in strict runtime checks.
MAX_QPS_P95_FIRST_MS="${CATSCAN_MAX_QPS_PAGE_P95_FIRST_ROW_MS:-6000}"
MAX_QPS_P95_HYDRATED_MS="${CATSCAN_MAX_QPS_PAGE_P95_HYDRATED_MS:-8000}"
MAX_SETTINGS_ENDPOINTS_MS="${CATSCAN_MAX_SETTINGS_ENDPOINTS_LATENCY_MS:-12000}"
MAX_SETTINGS_PRETARGETING_MS="${CATSCAN_MAX_SETTINGS_PRETARGETING_LATENCY_MS:-12000}"
MAX_HOME_CONFIGS_MS="${CATSCAN_MAX_HOME_CONFIGS_LATENCY_MS:-12000}"
MAX_HOME_ENDPOINT_EFFICIENCY_MS="${CATSCAN_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS:-12000}"

REQUIRED_API_PATHS=(
  "/settings/endpoints"
  "/settings/pretargeting"
  "/analytics/home/configs"
  "/analytics/home/endpoint-efficiency"
)

STEP_NAMES=()
STEP_STATUSES=()
STEP_NOTES=()
FAIL_COUNT=0
BLOCKED_COUNT=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_v1_runtime_health_unblock_check.sh --buyer-id <id> [options]

Runs a 4-step runtime-health unblock check with explicit PASS/FAIL/BLOCKED output:
1) Buyer report coverage diagnostic
2) Data-health bidstream coverage
3) QPS page SLO summary rollup readiness
4) Runtime-health strict workflow dispatch (optional)

Options:
  --buyer-id <id>             Required buyer ID
  --email <email>             X-Email header value (or set CATSCAN_CANARY_EMAIL)
  --api-base-url <url>        API base URL (default: https://scan.rtb.cat/api)
  --timeout <seconds>         Curl/script timeout (default: 180)
  --days <n>                  Days lookback for coverage diagnostics (default: 14)
  --since-hours <n>           Hours lookback for QPS SLO summary (default: 168)
  --profile <name>            Canary profile for strict dispatch (default: balanced)
  --skip-strict               Skip step 4 strict workflow dispatch
  --no-auto-fetch             Do not auto-run fetch evidence helper on strict failure
  -h, --help                  Show help

Examples:
  export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
  scripts/run_v1_runtime_health_unblock_check.sh --buyer-id 1487810529 --profile balanced
USAGE
}

record_step() {
  STEP_NAMES+=("$1")
  STEP_STATUSES+=("$2")
  STEP_NOTES+=("$3")
  case "$2" in
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
    BLOCKED) BLOCKED_COUNT=$((BLOCKED_COUNT + 1)) ;;
  esac
}

print_summary() {
  echo
  echo "=== Runtime Health Unblock Summary ==="
  local i
  for i in "${!STEP_NAMES[@]}"; do
    printf -- "- [%s] %s -> %s\n" "${STEP_STATUSES[$i]}" "${STEP_NAMES[$i]}" "${STEP_NOTES[$i]}"
  done
  if (( FAIL_COUNT > 0 || BLOCKED_COUNT > 0 )); then
    for i in "${!STEP_NAMES[@]}"; do
      if [[ "${STEP_STATUSES[$i]}" != "PASS" ]]; then
        echo "First non-pass signal: [${STEP_STATUSES[$i]}] ${STEP_NAMES[$i]} -> ${STEP_NOTES[$i]}"
        break
      fi
    done
  fi
  echo
  if (( FAIL_COUNT > 0 )); then
    echo "Result: FAIL (${FAIL_COUNT} failing step(s), ${BLOCKED_COUNT} blocked step(s))"
    return 1
  fi
  if (( BLOCKED_COUNT > 0 )); then
    echo "Result: BLOCKED (${BLOCKED_COUNT} blocked step(s))"
    return 2
  fi
  echo "Result: PASS"
  return 0
}

extract_run_id() {
  local text="$1"
  grep -Eo 'Detected runtime-health strict run: [0-9]+' <<<"$text" | awk '{print $NF}' | tail -1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buyer-id)
      BUYER_ID="${2:-}"
      shift 2
      ;;
    --email)
      CANARY_EMAIL="${2:-}"
      shift 2
      ;;
    --api-base-url)
      API_BASE_URL="${2:-}"
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
    --since-hours)
      SINCE_HOURS="${2:-}"
      shift 2
      ;;
    --profile)
      PROFILE="${2:-}"
      shift 2
      ;;
    --skip-strict)
      RUN_STRICT=0
      shift
      ;;
    --no-auto-fetch)
      AUTO_FETCH_EVIDENCE=0
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

if [[ -z "$BUYER_ID" ]]; then
  echo "--buyer-id is required." >&2
  usage
  exit 2
fi
if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 1 )); then
  echo "--timeout must be a positive integer." >&2
  exit 2
fi
if [[ -z "$CANARY_EMAIL" ]]; then
  echo "CATSCAN_CANARY_EMAIL is not set. Use --email or export CATSCAN_CANARY_EMAIL." >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required." >&2
  exit 2
fi

echo "Buyer: ${BUYER_ID}"
echo "Base URL: ${API_BASE_URL}"
echo "X-Email: ${CANARY_EMAIL}"
echo "Timeout: ${TIMEOUT_SECONDS}s"

# 1) Coverage diagnostic
echo
echo "[1/4] Buyer report coverage diagnostic"
coverage_log="$(mktemp)"
set +e
CATSCAN_CANARY_EMAIL="$CANARY_EMAIL" scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id "$BUYER_ID" \
  --timeout "$TIMEOUT_SECONDS" \
  --days "$DAYS" >"$coverage_log" 2>&1
coverage_exit=$?
set -e
cat "$coverage_log"
coverage_result_line="$(grep -E '^Result: ' "$coverage_log" | tail -1 || true)"
coverage_reason_line="$(grep -E '^(FAIL|BLOCKED|PASS):' "$coverage_log" | tail -1 || true)"
if grep -q 'Result: PASS' <<<"$coverage_result_line"; then
  record_step "Buyer coverage diagnostic" "PASS" "${coverage_reason_line:-coverage checks passed}"
elif grep -q 'Result: BLOCKED' <<<"$coverage_result_line"; then
  record_step "Buyer coverage diagnostic" "BLOCKED" "${coverage_reason_line:-coverage endpoint blocked}"
else
  if [[ -z "$coverage_reason_line" ]]; then
    coverage_reason_line="diagnostic script exit ${coverage_exit}"
  fi
  record_step "Buyer coverage diagnostic" "FAIL" "$coverage_reason_line"
fi
rm -f "$coverage_log"

# 2) Data-health bidstream coverage
echo
echo "[2/4] Data-health bidstream coverage"
dh_body="$(mktemp)"
dh_err="$(mktemp)"
set +e
dh_code="$(curl -sS \
  -H "X-Email: ${CANARY_EMAIL}" \
  -o "$dh_body" \
  -w '%{http_code}' \
  --max-time "$TIMEOUT_SECONDS" \
  "${API_BASE_URL%/}/system/data-health?buyer_id=${BUYER_ID}&days=7&limit=10" 2>"$dh_err")"
dh_curl_exit=$?
set -e
if (( dh_curl_exit != 0 )); then
  record_step "Data-health bidstream coverage" "FAIL" "curl failed: $(tr '\n' ' ' < "$dh_err" | sed 's/[[:space:]]\+/ /g')"
elif [[ "$dh_code" != "200" ]]; then
  record_step "Data-health bidstream coverage" "FAIL" "HTTP ${dh_code} from /system/data-health"
else
  bidstream_state="$(jq -r '.optimizer_readiness.bidstream_dimension_coverage.availability_state // "missing"' "$dh_body")"
  bidstream_rows="$(jq -r '.optimizer_readiness.bidstream_dimension_coverage.total_rows // 0' "$dh_body")"
  platform_missing="$(jq -r '.optimizer_readiness.bidstream_dimension_coverage.platform_missing_pct // "null"' "$dh_body")"
  env_missing="$(jq -r '.optimizer_readiness.bidstream_dimension_coverage.environment_missing_pct // "null"' "$dh_body")"
  tx_missing="$(jq -r '.optimizer_readiness.bidstream_dimension_coverage.transaction_type_missing_pct // "null"' "$dh_body")"
  all_dimensions_missing=0
  if [[ "$platform_missing" =~ ^[0-9]+([.][0-9]+)?$ ]] && \
     [[ "$env_missing" =~ ^[0-9]+([.][0-9]+)?$ ]] && \
     [[ "$tx_missing" =~ ^[0-9]+([.][0-9]+)?$ ]] && \
     awk -v p="$platform_missing" -v e="$env_missing" -v t="$tx_missing" 'BEGIN{exit !((p >= 99.9) && (e >= 99.9) && (t >= 99.9))}'; then
    all_dimensions_missing=1
  fi

  if [[ "$bidstream_state" == "unavailable" ]] || (( bidstream_rows <= 0 )); then
    record_step "Data-health bidstream coverage" "BLOCKED" "state=${bidstream_state}, total_rows=${bidstream_rows}"
  elif (( all_dimensions_missing == 1 )); then
    record_step "Data-health bidstream coverage" "BLOCKED" "state=${bidstream_state}, rows=${bidstream_rows}, all dimension columns missing at 100% (platform/env/tx=${platform_missing}/${env_missing}/${tx_missing})"
  else
    record_step "Data-health bidstream coverage" "PASS" "state=${bidstream_state}, rows=${bidstream_rows}, missing_pct(platform/env/tx)=${platform_missing}/${env_missing}/${tx_missing}"
  fi
fi
rm -f "$dh_body" "$dh_err"

# 3) QPS page SLO rollup readiness
echo
echo "[3/4] QPS page SLO summary readiness"
qps_body="$(mktemp)"
qps_err="$(mktemp)"
set +e
qps_code="$(curl -sS \
  -H "X-Email: ${CANARY_EMAIL}" \
  -o "$qps_body" \
  -w '%{http_code}' \
  --max-time "$TIMEOUT_SECONDS" \
  "${API_BASE_URL%/}/system/ui-metrics/page-load/summary?page=qps_home&buyer_id=${BUYER_ID}&since_hours=${SINCE_HOURS}&latest_limit=10&api_rollup_limit=50" 2>"$qps_err")"
qps_curl_exit=$?
set -e
if (( qps_curl_exit != 0 )); then
  record_step "QPS page SLO summary readiness" "FAIL" "curl failed: $(tr '\n' ' ' < "$qps_err" | sed 's/[[:space:]]\+/ /g')"
elif [[ "$qps_code" != "200" ]]; then
  record_step "QPS page SLO summary readiness" "FAIL" "HTTP ${qps_code} from /system/ui-metrics/page-load/summary"
else
  sample_count="$(jq -r '.sample_count // 0' "$qps_body")"
  p95_first="$(jq -r '.p95_first_table_row_ms // "null"' "$qps_body")"
  p95_hydrated="$(jq -r '.p95_table_hydrated_ms // "null"' "$qps_body")"

  if (( sample_count < 1 )); then
    record_step "QPS page SLO summary readiness" "BLOCKED" "sample_count=${sample_count} (no page-load metrics recorded yet)"
  elif [[ "$p95_first" == "null" || "$p95_hydrated" == "null" ]]; then
    record_step "QPS page SLO summary readiness" "FAIL" "missing p95 fields (p95_first=${p95_first}, p95_hydrated=${p95_hydrated})"
  else
    qps_fail_reason=""
    qps_blocked_reason=""

    if ! awk -v a="$p95_first" -v b="$MAX_QPS_P95_FIRST_MS" 'BEGIN{exit !(a<=b)}'; then
      qps_fail_reason="p95_first_table_row_ms=${p95_first} exceeds ${MAX_QPS_P95_FIRST_MS}"
    elif ! awk -v a="$p95_hydrated" -v b="$MAX_QPS_P95_HYDRATED_MS" 'BEGIN{exit !(a<=b)}'; then
      qps_fail_reason="p95_table_hydrated_ms=${p95_hydrated} exceeds ${MAX_QPS_P95_HYDRATED_MS}"
    else
      missing_paths=()
      for path in "${REQUIRED_API_PATHS[@]}"; do
        count="$(jq -r --arg p "$path" '[.api_latency_rollup[]? | select(.api_path == $p)] | length' "$qps_body")"
        if (( count < 1 )); then
          missing_paths+=("$path")
        fi
      done
      if (( ${#missing_paths[@]} > 0 )); then
        qps_blocked_reason="missing api_latency_rollup paths: ${missing_paths[*]}"
      else
        over_budget=()
        for path in "${REQUIRED_API_PATHS[@]}"; do
          p95="$(jq -r --arg p "$path" '[.api_latency_rollup[]? | select(.api_path == $p)][0].p95_latency_ms // "null"' "$qps_body")"
          case "$path" in
            "/settings/endpoints") budget="$MAX_SETTINGS_ENDPOINTS_MS" ;;
            "/settings/pretargeting") budget="$MAX_SETTINGS_PRETARGETING_MS" ;;
            "/analytics/home/configs") budget="$MAX_HOME_CONFIGS_MS" ;;
            "/analytics/home/endpoint-efficiency") budget="$MAX_HOME_ENDPOINT_EFFICIENCY_MS" ;;
            *) budget="12000" ;;
          esac
          if [[ "$p95" != "null" ]] && ! awk -v a="$p95" -v b="$budget" 'BEGIN{exit !(a<=b)}'; then
            over_budget+=("${path}=${p95}>${budget}")
          fi
        done
        if (( ${#over_budget[@]} > 0 )); then
          qps_fail_reason="api rollup p95 over budget: ${over_budget[*]}"
        fi
      fi
    fi

    if [[ -n "$qps_fail_reason" ]]; then
      record_step "QPS page SLO summary readiness" "FAIL" "$qps_fail_reason"
    elif [[ -n "$qps_blocked_reason" ]]; then
      record_step "QPS page SLO summary readiness" "BLOCKED" "$qps_blocked_reason"
    else
      record_step "QPS page SLO summary readiness" "PASS" "sample_count=${sample_count}, p95_first=${p95_first}, p95_hydrated=${p95_hydrated}"
    fi
  fi
fi
rm -f "$qps_body" "$qps_err"

# 4) Runtime-health strict dispatch (optional)
echo
if (( RUN_STRICT == 0 )); then
  echo "[4/4] Runtime-health strict dispatch (skipped)"
  record_step "Runtime-health strict dispatch" "PASS" "skipped by --skip-strict"
else
  echo "[4/4] Runtime-health strict dispatch"
  strict_log="$(mktemp)"
  set +e
  scripts/run_v1_runtime_health_strict_dispatch.sh \
    --buyer-id "$BUYER_ID" \
    --api-base-url "$API_BASE_URL" \
    --profile "$PROFILE" >"$strict_log" 2>&1
  strict_exit=$?
  set -e
  cat "$strict_log"
  run_id="$(extract_run_id "$(cat "$strict_log")")"

  if (( strict_exit == 0 )); then
    record_step "Runtime-health strict dispatch" "PASS" "workflow success${run_id:+ (run_id=${run_id})}"
  else
    strict_note="workflow failed${run_id:+ (run_id=${run_id})}"
    strict_class="FAIL"

    if grep -q "exit code 2" "$strict_log" || grep -q "BLOCKED" "$strict_log"; then
      strict_class="BLOCKED"
    fi

    if (( AUTO_FETCH_EVIDENCE == 1 )) && [[ -n "$run_id" ]] && [[ -x scripts/fetch_v1_runtime_health_run_evidence.sh ]]; then
      echo
      echo "Auto-fetching runtime-health evidence for run ${run_id}..."
      evidence_log="$(mktemp)"
      set +e
      scripts/fetch_v1_runtime_health_run_evidence.sh --run-id "$run_id" >"$evidence_log" 2>&1
      evidence_exit=$?
      set -e
      cat "$evidence_log"
      first_signal="$(grep -E '^(FAIL|BLOCKED)[[:space:]]{2,}' "$evidence_log" | head -1 || true)"
      if [[ -n "$first_signal" ]]; then
        strict_note="$first_signal"
      elif (( evidence_exit != 0 )); then
        strict_note="${strict_note}; evidence fetch exit ${evidence_exit}"
      fi
      rm -f "$evidence_log"
    fi

    record_step "Runtime-health strict dispatch" "$strict_class" "$strict_note"
  fi

  rm -f "$strict_log"
fi

print_summary
exit $?
