#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://your-deployment.example.com/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-60}"
DAYS="${CATSCAN_CANARY_DATA_HEALTH_DAYS:-14}"
TRIGGER_IMPORT=1
POLL_SECONDS="${CATSCAN_IMPORT_POLL_SECONDS:-15}"
MAX_WAIT_SECONDS="${CATSCAN_IMPORT_MAX_WAIT_SECONDS:-900}"

usage() {
  cat <<'EOF'
Usage:
  scripts/remediate_v1_quality_freshness_blocker.sh --buyer-id <id> [options]

Checks and remediates runtime blocker:
  rtb_quality_freshness unavailable in /system/data-health

Flow:
1) Check data health readiness for buyer.
2) If quality freshness is unavailable, trigger POST /gmail/import (optional).
3) Poll /gmail/status until import run completes.
4) Re-check data health and print next actions.

Options:
  --buyer-id <id>            Buyer ID (required)
  --base-url <url>           API base URL (default: https://your-deployment.example.com/api)
  --email <email>            X-Email identity (default: CATSCAN_CANARY_EMAIL or CATSCAN_CANARY_BEARER_TOKEN)
  --days <n>                 Data-health lookback days (default: 14)
  --timeout <seconds>        Curl timeout per request (default: 60)
  --poll-seconds <n>         /gmail/status poll interval (default: 15)
  --max-wait-seconds <n>     Max wait for import completion (default: 900)
  --no-import                Do not trigger /gmail/import; check-only mode
  -h, --help                 Show help

Example:
  export CATSCAN_CANARY_EMAIL="user@example.com"
  scripts/remediate_v1_quality_freshness_blocker.sh --buyer-id 1111111111
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
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --poll-seconds)
      POLL_SECONDS="${2:-}"
      shift 2
      ;;
    --max-wait-seconds)
      MAX_WAIT_SECONDS="${2:-}"
      shift 2
      ;;
    --no-import)
      TRIGGER_IMPORT=0
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
  exit 2
fi
if [[ -z "$CANARY_EMAIL" ]]; then
  echo "Set CATSCAN_CANARY_EMAIL (or CATSCAN_CANARY_BEARER_TOKEN) for X-Email auth." >&2
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
TMP_DIR="$(mktemp -d /tmp/v1-quality-remediate.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

api_get() {
  local path="$1"
  local out_file="$2"
  local code_file="$3"
  set +e
  curl -sS -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    -o "$out_file" \
    -w "%{http_code}\n" \
    "${BASE_URL}${path}" > "$code_file" 2> "${code_file}.stderr"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    echo "curl_exit_${rc}" > "$code_file"
    if [[ -s "${code_file}.stderr" ]]; then
      cat "${code_file}.stderr" >&2
    fi
  fi
}

api_post() {
  local path="$1"
  local out_file="$2"
  local code_file="$3"
  set +e
  curl -sS -m "$TIMEOUT_SECONDS" \
    -H "X-Email: ${CANARY_EMAIL}" \
    -X POST \
    -o "$out_file" \
    -w "%{http_code}\n" \
    "${BASE_URL}${path}" > "$code_file" 2> "${code_file}.stderr"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    echo "curl_exit_${rc}" > "$code_file"
    if [[ -s "${code_file}.stderr" ]]; then
      cat "${code_file}.stderr" >&2
    fi
  fi
}

print_data_health_summary() {
  local payload="$1"
  local state quality_state quality_rows quality_max missing_types
  state="$(jq -r '.state // "unknown"' "$payload")"
  quality_state="$(jq -r '.optimizer_readiness.rtb_quality_freshness.availability_state // "unknown"' "$payload")"
  quality_rows="$(jq -r '.optimizer_readiness.rtb_quality_freshness.rows // 0' "$payload")"
  quality_max="$(jq -r '.optimizer_readiness.rtb_quality_freshness.max_metric_date // "null"' "$payload")"
  missing_types="$(jq -r '.optimizer_readiness.report_completeness.missing_report_types // [] | join(",")' "$payload")"
  echo "data_health_state=${state}"
  echo "rtb_quality_freshness_state=${quality_state}"
  echo "rtb_quality_rows=${quality_rows}"
  echo "rtb_quality_max_metric_date=${quality_max}"
  echo "missing_report_types=${missing_types:-"(none)"}"
}

echo "Buyer: ${BUYER_ID}"
echo "Base URL: ${BASE_URL}"
echo "X-Email: ${CANARY_EMAIL}"
echo

echo "[1/4] Checking data-health quality freshness..."
dh1_body="${TMP_DIR}/data_health_before.json"
dh1_code="${TMP_DIR}/data_health_before.code"
api_get "/system/data-health?buyer_id=${BUYER_ID}&days=${DAYS}&limit=10" "$dh1_body" "$dh1_code"
code1="$(cat "$dh1_code")"
echo "data_health_http_before=${code1}"
if [[ "$code1" != "200" ]]; then
  preview="$(head -c 500 "$dh1_body" | tr '\n' ' ')"
  echo "data_health_error_preview=${preview}"
  echo "Result: FAIL"
  exit 1
fi
print_data_health_summary "$dh1_body"
quality_before="$(jq -r '.optimizer_readiness.rtb_quality_freshness.availability_state // "unknown"' "$dh1_body")"
echo

if [[ "$quality_before" == "healthy" ]]; then
  echo "Quality freshness is already healthy; no remediation needed."
  echo "Result: PASS"
  exit 0
fi

if [[ "$TRIGGER_IMPORT" != "1" ]]; then
  echo "Quality freshness not healthy and --no-import was set."
  echo "Result: BLOCKED"
  exit 2
fi

echo "[2/4] Triggering Gmail import (/gmail/import)..."
import_body="${TMP_DIR}/gmail_import.json"
import_code="${TMP_DIR}/gmail_import.code"
api_post "/gmail/import" "$import_body" "$import_code"
code_import="$(cat "$import_code")"
echo "gmail_import_http=${code_import}"
if [[ "$code_import" != "200" ]]; then
  preview="$(head -c 500 "$import_body" | tr '\n' ' ')"
  echo "gmail_import_error_preview=${preview}"
  echo "Result: BLOCKED"
  exit 2
fi

queued="$(jq -r '.queued // false' "$import_body")"
job_id="$(jq -r '.job_id // ""' "$import_body")"
no_new_mail="$(jq -r '.no_new_mail // false' "$import_body")"
no_new_mail_reason="$(jq -r '.no_new_mail_reason // ""' "$import_body")"
files_imported="$(jq -r '.files_imported // 0' "$import_body")"
emails_processed="$(jq -r '.emails_processed // 0' "$import_body")"

echo "gmail_import_queued=${queued} job_id=${job_id:-"(none)"}"
echo "gmail_import_files_imported=${files_imported} emails_processed=${emails_processed}"
if [[ "$no_new_mail" == "true" ]]; then
  echo "gmail_import_no_new_mail_reason=${no_new_mail_reason:-"(none)"}"
fi
echo

echo "[3/4] Polling /gmail/status until import run completes..."
status_body="${TMP_DIR}/gmail_status.json"
status_code="${TMP_DIR}/gmail_status.code"
deadline=$((SECONDS + MAX_WAIT_SECONDS))
while (( SECONDS < deadline )); do
  api_get "/gmail/status" "$status_body" "$status_code"
  code_status="$(cat "$status_code")"
  if [[ "$code_status" != "200" ]]; then
    echo "gmail_status_http=${code_status}"
    sleep "$POLL_SECONDS"
    continue
  fi
  running="$(jq -r '.running // false' "$status_body")"
  last_reason="$(jq -r '.last_reason // ""' "$status_body")"
  latest_metric_date="$(jq -r '.latest_metric_date // ""' "$status_body")"
  rows_latest="$(jq -r '.rows_on_latest_metric_date // 0' "$status_body")"
  unread="$(jq -r '.last_unread_report_emails // 0' "$status_body")"
  echo "gmail_status running=${running} last_reason=${last_reason:-"(none)"} latest_metric_date=${latest_metric_date:-"(none)"} rows_latest=${rows_latest} unread=${unread}"
  if [[ "$running" != "true" ]]; then
    break
  fi
  sleep "$POLL_SECONDS"
done
echo

echo "[4/4] Re-checking data-health quality freshness..."
dh2_body="${TMP_DIR}/data_health_after.json"
dh2_code="${TMP_DIR}/data_health_after.code"
api_get "/system/data-health?buyer_id=${BUYER_ID}&days=${DAYS}&limit=10" "$dh2_body" "$dh2_code"
code2="$(cat "$dh2_code")"
echo "data_health_http_after=${code2}"
if [[ "$code2" != "200" ]]; then
  preview="$(head -c 500 "$dh2_body" | tr '\n' ' ')"
  echo "data_health_error_preview_after=${preview}"
  echo "Result: BLOCKED"
  exit 2
fi
print_data_health_summary "$dh2_body"
quality_after="$(jq -r '.optimizer_readiness.rtb_quality_freshness.availability_state // "unknown"' "$dh2_body")"
echo

if [[ "$quality_after" == "healthy" ]]; then
  echo "Quality freshness remediation succeeded."
  echo "Next: rerun runtime strict gate:"
  echo "  scripts/run_v1_runtime_health_strict_dispatch.sh --buyer-id ${BUYER_ID} --profile balanced"
  echo "Result: PASS"
  exit 0
fi

echo "Quality freshness is still not healthy."
echo "Next actions:"
echo "  1) Confirm RTB Quality report is scheduled/exported for this buyer in Google Authorized Buyers."
echo "  2) Verify recent imports include RTB Quality CSVs for this seat/account."
echo "  3) Re-run this script after new quality CSVs arrive."
echo "Result: BLOCKED"
exit 2
