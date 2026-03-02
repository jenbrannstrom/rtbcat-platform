#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-60}"
DAYS="${CATSCAN_COVERAGE_DAYS:-30}"
HISTORY_LIMIT="${CATSCAN_HISTORY_LIMIT:-25}"

usage() {
  cat <<'EOF'
Usage:
  scripts/diagnose_v1_buyer_report_coverage.sh --buyer-id <id> [options]

Diagnoses why a buyer has missing CSV coverage for runtime strict gate.

Checks:
1) /seats?active_only=true mapping (buyer_id -> bidder_id)
2) /uploads/import-matrix?buyer_id=... (pass/fail/not_imported by CSV type)
3) /uploads/data-freshness?buyer_id=... (imported/missing cell coverage)
4) /uploads/history?bidder_id=... (recent import rows for mapped bidder)
5) /gmail/status (unread + last reason + latest metric date)

Options:
  --buyer-id <id>          Buyer ID (required)
  --base-url <url>         API base URL (default: https://scan.rtb.cat/api)
  --email <email>          X-Email identity (default: CATSCAN_CANARY_EMAIL/CATSCAN_CANARY_BEARER_TOKEN)
  --days <n>               Lookback days for matrix/freshness (default: 30)
  --history-limit <n>      Import history rows to inspect (default: 25)
  --timeout <seconds>      Curl timeout per request (default: 60)
  -h, --help               Show help

Example:
  export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
  scripts/diagnose_v1_buyer_report_coverage.sh --buyer-id 1487810529
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
    --history-limit)
      HISTORY_LIMIT="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
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
  echo "Set CATSCAN_CANARY_EMAIL (or CATSCAN_CANARY_BEARER_TOKEN)." >&2
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
TMP_DIR="$(mktemp -d /tmp/v1-buyer-coverage.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

api_get() {
  local path="$1"
  local out_file="$2"
  local code_file="$3"
  : > "$out_file"
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
    if [[ ! -s "$out_file" ]]; then
      echo "curl failed for ${path} (exit ${rc})" > "$out_file"
    fi
    if [[ -s "${code_file}.stderr" ]]; then
      cat "${code_file}.stderr" >&2
    fi
  fi
}

echo "Buyer: ${BUYER_ID}"
echo "Base URL: ${BASE_URL}"
echo "X-Email: ${CANARY_EMAIL}"
echo

echo "[1/5] Seat mapping (buyer -> bidder)..."
seats_body="${TMP_DIR}/seats.json"
seats_code="${TMP_DIR}/seats.code"
api_get "/seats?active_only=true" "$seats_body" "$seats_code"
code_seats="$(cat "$seats_code")"
echo "seats_http=${code_seats}"
if [[ "$code_seats" != "200" ]]; then
  preview="$(head -c 400 "$seats_body" | tr '\n' ' ')"
  echo "seats_error_preview=${preview}"
  echo "Result: FAIL"
  exit 1
fi

seat_found="$(jq -r --arg b "$BUYER_ID" 'map(select(.buyer_id == $b)) | length' "$seats_body")"
bidder_id="$(jq -r --arg b "$BUYER_ID" 'map(select(.buyer_id == $b))[0].bidder_id // ""' "$seats_body")"
seat_name="$(jq -r --arg b "$BUYER_ID" 'map(select(.buyer_id == $b))[0].display_name // ""' "$seats_body")"
echo "seat_found=${seat_found} bidder_id=${bidder_id:-"(none)"} display_name=${seat_name:-"(none)"}"
echo

echo "[2/5] Import matrix for this buyer..."
matrix_body="${TMP_DIR}/import_matrix.json"
matrix_code="${TMP_DIR}/import_matrix.code"
api_get "/uploads/import-matrix?days=${DAYS}&buyer_id=${BUYER_ID}" "$matrix_body" "$matrix_code"
code_matrix="$(cat "$matrix_code")"
echo "import_matrix_http=${code_matrix}"
if [[ "$code_matrix" != "200" ]]; then
  preview="$(head -c 400 "$matrix_body" | tr '\n' ' ')"
  echo "import_matrix_error_preview=${preview}"
  echo "Result: FAIL"
  exit 1
fi

matrix_accounts="$(jq -r '.total_accounts // 0' "$matrix_body")"
pass_count="$(jq -r '.pass_count // 0' "$matrix_body")"
fail_count="$(jq -r '.fail_count // 0' "$matrix_body")"
not_imported_count="$(jq -r '.not_imported_count // 0' "$matrix_body")"
echo "matrix_total_accounts=${matrix_accounts} pass=${pass_count} fail=${fail_count} not_imported=${not_imported_count}"
echo "matrix_csv_statuses:"
jq -r '.accounts[]?.csv_types[]? | "  - \(.csv_type): \(.status) source=\(.source // "n/a") last=\(.last_imported_at // "n/a") err=\(.error_summary // "n/a")"' "$matrix_body"
echo

echo "[3/5] Data freshness grid for this buyer..."
fresh_body="${TMP_DIR}/data_freshness.json"
fresh_code="${TMP_DIR}/data_freshness.code"
imported_count="-1"
missing_count="-1"
coverage_pct="-1"
api_get "/uploads/data-freshness?days=14&buyer_id=${BUYER_ID}" "$fresh_body" "$fresh_code"
code_fresh="$(cat "$fresh_code")"
echo "data_freshness_http=${code_fresh}"
if [[ "$code_fresh" == "200" ]]; then
  imported_count="$(jq -r '.summary.imported_count // 0' "$fresh_body")"
  missing_count="$(jq -r '.summary.missing_count // 0' "$fresh_body")"
  coverage_pct="$(jq -r '.summary.coverage_pct // 0' "$fresh_body")"
  echo "freshness imported=${imported_count} missing=${missing_count} coverage_pct=${coverage_pct}"
else
  preview="$(head -c 400 "$fresh_body" | tr '\n' ' ')"
  echo "data_freshness_error_preview=${preview}"
fi
echo

echo "[4/5] Recent import history for mapped bidder..."
code_hist="skipped_no_bidder_id"
if [[ -n "$bidder_id" ]]; then
  hist_body="${TMP_DIR}/import_history.json"
  hist_code="${TMP_DIR}/import_history.code"
  api_get "/uploads/history?limit=${HISTORY_LIMIT}&offset=0&bidder_id=${bidder_id}" "$hist_body" "$hist_code"
  code_hist="$(cat "$hist_code")"
  echo "import_history_http=${code_hist}"
  if [[ "$code_hist" == "200" ]]; then
    hist_count="$(jq -r 'length' "$hist_body")"
    quality_like="$(jq -r '[.[] | select((.filename // "" | ascii_downcase | test("quality")))] | length' "$hist_body")"
    echo "history_rows=${hist_count} quality_like_filenames=${quality_like}"
    echo "history_latest_rows:"
    jq -r '.[] | "  - imported_at=\(.imported_at) status=\(.status) rows=\(.rows_imported) trigger=\(.import_trigger // "n/a") file=\(.filename // "n/a")"' "$hist_body" | head -n 10
  else
    preview="$(head -c 400 "$hist_body" | tr '\n' ' ')"
    echo "import_history_error_preview=${preview}"
  fi
else
  echo "skipped: no bidder_id mapping found for buyer."
fi
echo

echo "[5/5] Gmail status snapshot..."
gmail_body="${TMP_DIR}/gmail_status.json"
gmail_code="${TMP_DIR}/gmail_status.code"
api_get "/gmail/status" "$gmail_body" "$gmail_code"
code_gmail="$(cat "$gmail_code")"
echo "gmail_status_http=${code_gmail}"
if [[ "$code_gmail" == "200" ]]; then
  last_reason="$(jq -r '.last_reason // ""' "$gmail_body")"
  latest_metric_date="$(jq -r '.latest_metric_date // ""' "$gmail_body")"
  rows_latest="$(jq -r '.rows_on_latest_metric_date // 0' "$gmail_body")"
  unread="$(jq -r '.last_unread_report_emails // 0' "$gmail_body")"
  echo "gmail last_reason=${last_reason:-"(none)"} latest_metric_date=${latest_metric_date:-"(none)"} rows_latest=${rows_latest} unread=${unread}"
else
  preview="$(head -c 400 "$gmail_body" | tr '\n' ' ')"
  echo "gmail_status_error_preview=${preview}"
fi
echo

echo "=== Diagnosis Summary ==="
if [[ "$seat_found" == "0" ]]; then
  echo "FAIL: buyer_id is not present in active seats -> seat mapping/RBAC scope issue."
  echo "Result: FAIL"
  exit 1
fi

if [[ "$matrix_accounts" == "0" ]]; then
  echo "BLOCKED: buyer seat exists, but no import matrix account returned for this buyer."
  echo "Likely cause: no ingested files mapped to this buyer/bidder in lookback."
  echo "Result: BLOCKED"
  exit 2
fi

all_not_imported="$(jq -r '[.accounts[]?.csv_types[]? | select(.status == "not_imported")] | length' "$matrix_body")"
total_cells="$(jq -r '[.accounts[]?.csv_types[]?] | length' "$matrix_body")"
if [[ "$total_cells" != "0" && "$all_not_imported" == "$total_cells" ]]; then
  echo "BLOCKED: all CSV types are not_imported for this buyer."
  echo "Likely cause: Gmail unread reports belong to other seats or report exports for this buyer are not configured."
  echo "Result: BLOCKED"
  exit 2
fi

if [[ "$code_fresh" != "200" || "$code_hist" != "200" || "$code_gmail" != "200" ]]; then
  echo "BLOCKED: buyer has import coverage, but required diagnostics endpoints are failing."
  echo "endpoint_statuses data_freshness=${code_fresh} import_history=${code_hist} gmail_status=${code_gmail}"
  echo "Likely cause: runtime API/query instability (e.g., nginx 502/upstream timeout), not missing Google report scheduling."
  echo "Result: BLOCKED"
  exit 2
fi

if [[ "$imported_count" == "0" && "$pass_count" != "0" ]]; then
  echo "BLOCKED: import matrix shows pass, but freshness grid has zero imported cells."
  echo "Likely cause: importer-history vs serving-table inconsistency or stalled downstream write path."
  echo "Result: BLOCKED"
  exit 2
fi

echo "PASS: buyer has partial report coverage and diagnostics endpoints are responsive."
echo "Result: PASS"
