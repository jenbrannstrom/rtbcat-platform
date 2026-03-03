#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-60}"
OUT_DIR="${CATSCAN_OUTPUT_DIR:-/tmp}"
RUN_RETENTION=1
STRICT_SECURITY=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/check_conversion_runtime_guardrails.sh [options]

Runs conversion runtime guardrail checks in one command:
1) GET  /conversions/security/status
2) GET  /retention/stats (before)
3) POST /retention/run
4) GET  /retention/stats (after)

Options:
  --base-url <url>         API base URL (default: https://scan.rtb.cat/api)
  --email <email>          X-Email identity (default: CATSCAN_CANARY_EMAIL/CATSCAN_CANARY_BEARER_TOKEN)
  --timeout <seconds>      Curl timeout per request (default: 60)
  --out-dir <dir>          Output root (default: /tmp)
  --skip-retention-run     Do not call POST /retention/run
  --strict-security        Exit non-zero if security posture is not fully hardened
  -h, --help               Show help

Examples:
  export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
  scripts/check_conversion_runtime_guardrails.sh

  scripts/check_conversion_runtime_guardrails.sh --strict-security
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --skip-retention-run)
      RUN_RETENTION=0
      shift
      ;;
    --strict-security)
      STRICT_SECURITY=1
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

if [[ -z "$CANARY_EMAIL" ]]; then
  echo "Set CATSCAN_CANARY_EMAIL (or CATSCAN_CANARY_BEARER_TOKEN), or pass --email." >&2
  exit 2
fi
if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 5 || TIMEOUT_SECONDS > 600 )); then
  echo "Invalid --timeout value: ${TIMEOUT_SECONDS} (expected 5..600)." >&2
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
RUN_DIR="${OUT_DIR%/}/conversion-runtime-guardrails-${STAMP}"
mkdir -p "$RUN_DIR"

api_request() {
  local method="$1"
  local path="$2"
  local body_file="$3"
  local code_file="$4"
  local data="${5:-}"
  : > "$body_file"

  local -a data_args=()
  if [[ -n "$data" ]]; then
    data_args=(-H "Content-Type: application/json" -d "$data")
  fi

  set +e
  curl -sS -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    "${data_args[@]}" \
    -o "$body_file" \
    -w "%{http_code}\n" \
    -X "$method" \
    "${BASE_URL}${path}" > "$code_file" 2> "${code_file}.stderr"
  local rc=$?
  set -e

  if [[ "$rc" -ne 0 ]]; then
    echo "curl_exit_${rc}" > "$code_file"
    if [[ ! -s "$body_file" ]]; then
      echo "curl failed for ${path} (exit ${rc})" > "$body_file"
    fi
    if [[ -s "${code_file}.stderr" ]]; then
      cat "${code_file}.stderr" >&2
    fi
  fi
}

security_body="${RUN_DIR}/security_status.json"
security_code="${RUN_DIR}/security_status.http"
stats_before_body="${RUN_DIR}/retention_stats_before.json"
stats_before_code="${RUN_DIR}/retention_stats_before.http"
run_body="${RUN_DIR}/retention_run.json"
run_code="${RUN_DIR}/retention_run.http"
stats_after_body="${RUN_DIR}/retention_stats_after.json"
stats_after_code="${RUN_DIR}/retention_stats_after.http"
report_md="${RUN_DIR}/guardrail_report.md"

fail=0

printf 'Run dir: %s\n' "$RUN_DIR"
printf 'Base URL: %s\n' "$BASE_URL"
printf 'X-Email: %s\n\n' "$CANARY_EMAIL"

echo "[1/4] Checking conversion webhook security posture..."
api_request "GET" "/conversions/security/status" "$security_body" "$security_code"
security_http="$(cat "$security_code")"
echo "security_status_http=${security_http}"
if [[ "$security_http" != "200" ]]; then
  echo "security_status_error=$(head -c 400 "$security_body" | tr '\n' ' ')"
  fail=1
fi

echo
echo "[2/4] Getting retention stats (before)..."
api_request "GET" "/retention/stats" "$stats_before_body" "$stats_before_code"
stats_before_http="$(cat "$stats_before_code")"
echo "retention_stats_before_http=${stats_before_http}"
if [[ "$stats_before_http" != "200" ]]; then
  echo "retention_stats_before_error=$(head -c 400 "$stats_before_body" | tr '\n' ' ')"
  fail=1
fi

echo
if [[ "$RUN_RETENTION" == "1" ]]; then
  echo "[3/4] Running retention job..."
  api_request "POST" "/retention/run" "$run_body" "$run_code"
  run_http="$(cat "$run_code")"
  echo "retention_run_http=${run_http}"
  if [[ "$run_http" != "200" ]]; then
    echo "retention_run_error=$(head -c 400 "$run_body" | tr '\n' ' ')"
    fail=1
  fi
else
  echo "[3/4] Skipping retention job (--skip-retention-run)."
  echo "skipped" > "$run_code"
  echo "{}" > "$run_body"
  run_http="skipped"
fi

echo
echo "[4/4] Getting retention stats (after)..."
api_request "GET" "/retention/stats" "$stats_after_body" "$stats_after_code"
stats_after_http="$(cat "$stats_after_code")"
echo "retention_stats_after_http=${stats_after_http}"
if [[ "$stats_after_http" != "200" ]]; then
  echo "retention_stats_after_error=$(head -c 400 "$stats_after_body" | tr '\n' ' ')"
  fail=1
fi

if [[ "$fail" != "0" ]]; then
  echo
  echo "Result: FAIL (HTTP/curl errors). Inspect ${RUN_DIR}" >&2
  exit 1
fi

shared_secret_enabled="$(jq -r '.shared_secret_enabled // false' "$security_body")"
shared_hmac_enabled="$(jq -r '.shared_hmac_enabled // false' "$security_body")"
freshness_enforced="$(jq -r '.freshness_enforced // false' "$security_body")"
rate_limit_enabled="$(jq -r '.rate_limit_enabled // false' "$security_body")"
appsflyer_secret_enabled="$(jq -r '(.sources // [] | map(select(.source_type=="appsflyer"))[0].secret_enabled) // false' "$security_body")"
appsflyer_hmac_enabled="$(jq -r '(.sources // [] | map(select(.source_type=="appsflyer"))[0].hmac_enabled) // false' "$security_body")"

conv_before_events="$(jq -r '.conversion_event_rows // 0' "$stats_before_body")"
conv_before_failures="$(jq -r '.conversion_failure_rows // 0' "$stats_before_body")"
conv_before_joins="$(jq -r '.conversion_join_rows // 0' "$stats_before_body")"
raw_before_rows="$(jq -r '.raw_rows // 0' "$stats_before_body")"
summary_before_rows="$(jq -r '.summary_rows // 0' "$stats_before_body")"

conv_after_events="$(jq -r '.conversion_event_rows // 0' "$stats_after_body")"
conv_after_failures="$(jq -r '.conversion_failure_rows // 0' "$stats_after_body")"
conv_after_joins="$(jq -r '.conversion_join_rows // 0' "$stats_after_body")"
raw_after_rows="$(jq -r '.raw_rows // 0' "$stats_after_body")"
summary_after_rows="$(jq -r '.summary_rows // 0' "$stats_after_body")"

deleted_raw_rows="$(jq -r '.deleted_raw_rows // 0' "$run_body")"
deleted_summary_rows="$(jq -r '.deleted_summary_rows // 0' "$run_body")"
deleted_conv_events="$(jq -r '.deleted_conversion_event_rows // 0' "$run_body")"
deleted_conv_failures="$(jq -r '.deleted_conversion_failure_rows // 0' "$run_body")"
deleted_conv_joins="$(jq -r '.deleted_conversion_join_rows // 0' "$run_body")"

security_hardened=1
if [[ "$appsflyer_secret_enabled" != "true" || "$appsflyer_hmac_enabled" != "true" || "$freshness_enforced" != "true" || "$rate_limit_enabled" != "true" ]]; then
  security_hardened=0
fi

raw_delta=$(( raw_after_rows - raw_before_rows ))
summary_delta=$(( summary_after_rows - summary_before_rows ))
conv_event_delta=$(( conv_after_events - conv_before_events ))
conv_failure_delta=$(( conv_after_failures - conv_before_failures ))
conv_join_delta=$(( conv_after_joins - conv_before_joins ))

cat > "$report_md" <<REPORT
# Conversion Runtime Guardrail Report

- generated_utc: ${STAMP}
- base_url: ${BASE_URL}
- run_retention: ${RUN_RETENTION}

## Security posture

- shared_secret_enabled: ${shared_secret_enabled}
- shared_hmac_enabled: ${shared_hmac_enabled}
- appsflyer_secret_enabled: ${appsflyer_secret_enabled}
- appsflyer_hmac_enabled: ${appsflyer_hmac_enabled}
- freshness_enforced: ${freshness_enforced}
- rate_limit_enabled: ${rate_limit_enabled}
- security_hardened: ${security_hardened}

## Retention stats

- before_raw_rows: ${raw_before_rows}
- after_raw_rows: ${raw_after_rows}
- delta_raw_rows: ${raw_delta}
- before_summary_rows: ${summary_before_rows}
- after_summary_rows: ${summary_after_rows}
- delta_summary_rows: ${summary_delta}

- before_conversion_event_rows: ${conv_before_events}
- after_conversion_event_rows: ${conv_after_events}
- delta_conversion_event_rows: ${conv_event_delta}

- before_conversion_failure_rows: ${conv_before_failures}
- after_conversion_failure_rows: ${conv_after_failures}
- delta_conversion_failure_rows: ${conv_failure_delta}

- before_conversion_join_rows: ${conv_before_joins}
- after_conversion_join_rows: ${conv_after_joins}
- delta_conversion_join_rows: ${conv_join_delta}

## Retention run response

- deleted_raw_rows: ${deleted_raw_rows}
- deleted_summary_rows: ${deleted_summary_rows}
- deleted_conversion_event_rows: ${deleted_conv_events}
- deleted_conversion_failure_rows: ${deleted_conv_failures}
- deleted_conversion_join_rows: ${deleted_conv_joins}
REPORT

echo
echo "=== Guardrail Summary ==="
printf 'security_hardened=%s (strict=%s)\n' "$security_hardened" "$STRICT_SECURITY"
printf 'raw_rows before=%s after=%s delta=%s\n' "$raw_before_rows" "$raw_after_rows" "$raw_delta"
printf 'summary_rows before=%s after=%s delta=%s\n' "$summary_before_rows" "$summary_after_rows" "$summary_delta"
printf 'conversion_event_rows before=%s after=%s delta=%s\n' "$conv_before_events" "$conv_after_events" "$conv_event_delta"
printf 'conversion_failure_rows before=%s after=%s delta=%s\n' "$conv_before_failures" "$conv_after_failures" "$conv_failure_delta"
printf 'conversion_join_rows before=%s after=%s delta=%s\n' "$conv_before_joins" "$conv_after_joins" "$conv_join_delta"
printf 'retention_run deleted raw=%s summary=%s conv_events=%s conv_failures=%s conv_joins=%s\n' \
  "$deleted_raw_rows" "$deleted_summary_rows" "$deleted_conv_events" "$deleted_conv_failures" "$deleted_conv_joins"
echo "report_md=${report_md}"

if [[ "$STRICT_SECURITY" == "1" && "$security_hardened" != "1" ]]; then
  echo "Result: FAIL (strict security mode: webhook security posture not fully hardened)." >&2
  exit 1
fi

echo "Result: PASS"
