#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-}"
SOURCE_TYPE="${CATSCAN_CONVERSION_SOURCE_TYPE:-appsflyer}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-90}"
DAYS="${CATSCAN_ATTRIBUTION_DAYS:-14}"
FRESHNESS_HOURS="${CATSCAN_CONVERSION_FRESHNESS_HOURS:-72}"
SCAN_LIMIT="${CATSCAN_CLICK_MACRO_SCAN_LIMIT:-3000}"
FALLBACK_WINDOW_DAYS="${CATSCAN_ATTRIBUTION_FALLBACK_WINDOW_DAYS:-1}"
LIMIT="${CATSCAN_ATTRIBUTION_REPORT_LIMIT:-50}"
OUT_DIR="${CATSCAN_OUTPUT_DIR:-/tmp}"
DOC_OUT=""

API_TOKEN="${CATSCAN_API_TOKEN:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
API_EMAIL="${CATSCAN_CANARY_EMAIL:-}"

RUN_PHASE_A=1
ALLOW_PHASE_A_FAILURE=1
PHASE_A_DB_SINCE_DAYS="${CATSCAN_APPSFLYER_DB_SINCE_DAYS:-30}"
PHASE_A_DB_LIMIT="${CATSCAN_APPSFLYER_DB_LIMIT:-500000}"
PHASE_A_DB_DSN="${CATSCAN_POSTGRES_DSN:-}"
PHASE_A_MAPPING_PROFILE=""
PHASE_A_FETCH_MAPPING="auto"

STRICT_PHASE_B_REFRESH=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_appsflyer_pilot_live_validation.sh --buyer-id <id> [options]

Purpose:
  Runs a single end-to-end AppsFlyer pilot live validation:
  1) Readiness snapshot (click macros + readiness + attribution endpoint health)
  2) Phase A contract audit (optional/advisory)
  3) Phase B attribution report (required)
  4) Consolidated PASS/BLOCKED/FAIL report

Required:
  --buyer-id <id>
  Auth via one of:
    --token <bearer>
    --email <x-email identity>

Options:
  --source-type <name>             Conversion source type (default: appsflyer)
  --api-base-url <url>             API base URL (default: https://scan.rtb.cat/api)
  --timeout <seconds>              Readiness request timeout (default: 90)
  --days <n>                       Lookback days (default: 14)
  --freshness-hours <n>            Readiness freshness threshold (default: 72)
  --scan-limit <n>                 Click-macro scan limit (default: 3000)
  --fallback-window-days <n>       Phase B fallback window days (default: 1)
  --limit <n>                      Phase B sample limit (default: 50)
  --token <value>                  Bearer token
  --email <value>                  X-Email identity
  --out-dir <dir>                  Output root (default: /tmp)
  --doc-out <path>                 Optional copy path for markdown report

  Phase A options:
  --skip-phase-a                   Skip Phase A (advisory step)
  --phase-a-allow-failure <bool>   Continue when Phase A fails (default: true)
  --phase-a-db-since-days <n>      DB lookback for --from-db (default: 30)
  --phase-a-db-limit <n>           DB export row limit (default: 500000)
  --phase-a-db-dsn <dsn>           DSN override for --from-db
  --phase-a-mapping-profile <path> Mapping profile JSON file
  --phase-a-fetch-mapping <mode>   auto|true|false (default: auto)

  Phase B options:
  --strict-phase-b-refresh         Fail if refresh endpoint is non-200

  -h, --help                       Show help

Examples:
  export CATSCAN_API_TOKEN="..."
  scripts/run_appsflyer_pilot_live_validation.sh --buyer-id 299038253

  export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
  scripts/run_appsflyer_pilot_live_validation.sh \
    --buyer-id 299038253 \
    --strict-phase-b-refresh
EOF
}

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

extract_kv() {
  local key="$1"
  local file="$2"
  awk -F= -v key="$key" '$1 == key { print substr($0, index($0, "=") + 1) }' "$file" | tail -n1
}

safe_int_or_zero() {
  local value="${1:-0}"
  if [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "$value"
  else
    echo "0"
  fi
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
    --api-base-url)
      BASE_URL="${2:-}"
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
    --fallback-window-days)
      FALLBACK_WINDOW_DAYS="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
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
    --skip-phase-a)
      RUN_PHASE_A=0
      shift
      ;;
    --phase-a-allow-failure)
      ALLOW_PHASE_A_FAILURE="$(parse_bool "${2:-}")"
      shift 2
      ;;
    --phase-a-db-since-days)
      PHASE_A_DB_SINCE_DAYS="${2:-}"
      shift 2
      ;;
    --phase-a-db-limit)
      PHASE_A_DB_LIMIT="${2:-}"
      shift 2
      ;;
    --phase-a-db-dsn)
      PHASE_A_DB_DSN="${2:-}"
      shift 2
      ;;
    --phase-a-mapping-profile)
      PHASE_A_MAPPING_PROFILE="${2:-}"
      shift 2
      ;;
    --phase-a-fetch-mapping)
      PHASE_A_FETCH_MAPPING="${2:-}"
      shift 2
      ;;
    --strict-phase-b-refresh)
      STRICT_PHASE_B_REFRESH=1
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
if [[ -z "$API_TOKEN" && -z "$API_EMAIL" ]]; then
  echo "Provide --token or --email (or set CATSCAN_API_TOKEN/CATSCAN_CANARY_EMAIL)." >&2
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
if ! [[ "$FALLBACK_WINDOW_DAYS" =~ ^[0-9]+$ ]] || (( FALLBACK_WINDOW_DAYS < 0 || FALLBACK_WINDOW_DAYS > 7 )); then
  echo "Invalid --fallback-window-days '${FALLBACK_WINDOW_DAYS}' (expected 0..7)." >&2
  exit 2
fi
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || (( LIMIT < 1 || LIMIT > 1000 )); then
  echo "Invalid --limit '${LIMIT}' (expected 1..1000)." >&2
  exit 2
fi
if ! [[ "$PHASE_A_DB_SINCE_DAYS" =~ ^[0-9]+$ ]] || (( PHASE_A_DB_SINCE_DAYS < 1 || PHASE_A_DB_SINCE_DAYS > 3650 )); then
  echo "Invalid --phase-a-db-since-days '${PHASE_A_DB_SINCE_DAYS}' (expected 1..3650)." >&2
  exit 2
fi
if ! [[ "$PHASE_A_DB_LIMIT" =~ ^[0-9]+$ ]] || (( PHASE_A_DB_LIMIT < 1 )); then
  echo "Invalid --phase-a-db-limit '${PHASE_A_DB_LIMIT}' (expected >=1)." >&2
  exit 2
fi
case "${PHASE_A_FETCH_MAPPING,,}" in
  auto|true|false) ;;
  *)
    echo "Invalid --phase-a-fetch-mapping '${PHASE_A_FETCH_MAPPING}' (expected auto|true|false)." >&2
    exit 2
    ;;
esac
if [[ -n "$PHASE_A_MAPPING_PROFILE" && ! -f "$PHASE_A_MAPPING_PROFILE" ]]; then
  echo "Mapping profile file not found: ${PHASE_A_MAPPING_PROFILE}" >&2
  exit 2
fi

if ! command -v bash >/dev/null 2>&1; then
  echo "'bash' is required." >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "'jq' is required." >&2
  exit 2
fi

BASE_URL="${BASE_URL%/}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${OUT_DIR%/}/appsflyer-pilot-live-validation-${BUYER_ID}-${STAMP}"
mkdir -p "$RUN_DIR"

PILOT_LOG="${RUN_DIR}/step1_pilot_check.log"
PHASE_A_LOG="${RUN_DIR}/step2_phase_a.log"
PHASE_B_LOG="${RUN_DIR}/step3_phase_b.log"
REPORT_MD="${RUN_DIR}/live_validation_report.md"
REPORT_JSON="${RUN_DIR}/live_validation_report.json"

echo "Run dir: ${RUN_DIR}"
echo "Buyer: ${BUYER_ID}"
echo "Source type: ${SOURCE_TYPE}"
echo "Base URL: ${BASE_URL}"
echo

declare -a AUTH_ARGS=()
if [[ -n "$API_TOKEN" ]]; then
  AUTH_ARGS=(--token "$API_TOKEN")
else
  AUTH_ARGS=(--email "$API_EMAIL")
fi

pilot_rc=0
phase_a_rc=0
phase_b_rc=0
phase_a_state="SKIPPED"
phase_a_note="phase_a_skipped"
phase_a_decision_mode="n/a"
phase_a_contract_report=""

exact_ready="0"
exact_join_live="0"
pilot_report=""
phase_b_report=""
phase_b_summary_json=""
total_events="0"
exact_matched="0"
exact_total="0"
fallback_matched="0"
fallback_unmatched="0"

echo "[1/3] Pilot readiness snapshot..."
set +e
bash scripts/run_tuky_appsflyer_pilot_check.sh \
  --buyer-id "$BUYER_ID" \
  --source-type "$SOURCE_TYPE" \
  --base-url "$BASE_URL" \
  --timeout "$TIMEOUT_SECONDS" \
  --days "$DAYS" \
  --freshness-hours "$FRESHNESS_HOURS" \
  --scan-limit "$SCAN_LIMIT" \
  --out-dir "$RUN_DIR" \
  "${AUTH_ARGS[@]}" \
  > "$PILOT_LOG" 2>&1
pilot_rc=$?
set -e
cat "$PILOT_LOG"
if (( pilot_rc != 0 )); then
  echo "Pilot readiness step failed (rc=${pilot_rc})." >&2
fi
pilot_report="$(extract_kv "report_md" "$PILOT_LOG" || true)"
exact_ready="$(extract_kv "exact_ready_for_ingestion" "$PILOT_LOG" || true)"
exact_join_live="$(extract_kv "exact_join_live" "$PILOT_LOG" || true)"
exact_ready="$(safe_int_or_zero "$exact_ready")"
exact_join_live="$(safe_int_or_zero "$exact_join_live")"

echo
echo "[2/3] Phase A contract audit (advisory)..."
if (( RUN_PHASE_A == 0 )); then
  echo "phase_a=skipped (--skip-phase-a)"
else
  run_phase_a_now=1
  if [[ -z "$PHASE_A_DB_DSN" && -z "${POSTGRES_DSN:-}" && -z "${DATABASE_URL:-}" ]]; then
    run_phase_a_now=0
    phase_a_state="BLOCKED"
    phase_a_note="phase_a_from_db_missing_dsn"
      echo "phase_a=blocked (missing DSN for Phase A DB export)"
    if (( ALLOW_PHASE_A_FAILURE == 0 )); then
      echo "Phase A DSN is required when --phase-a-allow-failure=false." >&2
      exit 1
    fi
  fi

  if (( run_phase_a_now == 1 )); then
    declare -a phase_a_cmd=(
      bash scripts/run_appsflyer_phase_a_audit.sh
      --buyer-id "$BUYER_ID"
      --source-type "$SOURCE_TYPE"
      --input-format auto
      --fetch-mapping "$PHASE_A_FETCH_MAPPING"
      --api-base-url "$BASE_URL"
      --out-dir "$RUN_DIR"
      "${AUTH_ARGS[@]}"
    )
    phase_a_cmd+=(--from-db --db-since-days "$PHASE_A_DB_SINCE_DAYS" --db-limit "$PHASE_A_DB_LIMIT")
    if [[ -n "$PHASE_A_DB_DSN" ]]; then
      phase_a_cmd+=(--db-dsn "$PHASE_A_DB_DSN")
    fi
    if [[ -n "$PHASE_A_MAPPING_PROFILE" ]]; then
      phase_a_cmd+=(--mapping-profile "$PHASE_A_MAPPING_PROFILE")
    fi

    set +e
    "${phase_a_cmd[@]}" > "$PHASE_A_LOG" 2>&1
    phase_a_rc=$?
    set -e
    cat "$PHASE_A_LOG"

    if (( phase_a_rc == 0 )); then
      phase_a_state="PASS"
      phase_a_note="phase_a_ok"
      phase_a_contract_report="$(sed -n 's/^Contract report: //p' "$PHASE_A_LOG" | tail -n1)"
      if [[ -n "$phase_a_contract_report" && -f "$phase_a_contract_report" ]]; then
        phase_a_decision_mode="$(sed -n 's/^- decision_mode: `\(.*\)`/\1/p' "$phase_a_contract_report" | head -n1)"
        if [[ -z "$phase_a_decision_mode" ]]; then
          phase_a_decision_mode="unknown"
        fi
      else
        phase_a_decision_mode="unknown"
      fi
    else
      phase_a_state="BLOCKED"
      phase_a_note="phase_a_failed_rc_${phase_a_rc}"
      phase_a_decision_mode="n/a"
      if (( ALLOW_PHASE_A_FAILURE == 0 )); then
        echo "Phase A failed (rc=${phase_a_rc}) and --phase-a-allow-failure=false." >&2
        exit 1
      fi
      echo "phase_a=blocked (continuing: advisory step failed rc=${phase_a_rc})"
    fi
  fi
fi

echo
echo "[3/3] Phase B attribution validation..."
declare -a phase_b_cmd=(
  bash scripts/run_conversion_attribution_phase_b_report.sh
  --buyer-id "$BUYER_ID"
  --source-type "$SOURCE_TYPE"
  --days "$DAYS"
  --fallback-window-days "$FALLBACK_WINDOW_DAYS"
  --limit "$LIMIT"
  --api-base-url "$BASE_URL"
  --out-dir "$RUN_DIR"
  "${AUTH_ARGS[@]}"
)
if (( STRICT_PHASE_B_REFRESH == 1 )); then
  phase_b_cmd+=(--strict-refresh)
fi

set +e
"${phase_b_cmd[@]}" > "$PHASE_B_LOG" 2>&1
phase_b_rc=$?
set -e
cat "$PHASE_B_LOG"

phase_b_report="$(extract_kv "report_md" "$PHASE_B_LOG" || true)"
if [[ -n "$phase_b_report" ]]; then
  phase_b_summary_json="$(dirname "$phase_b_report")/summary.json"
  if [[ -f "$phase_b_summary_json" ]]; then
    total_events="$(jq -r '.total_events // 0' "$phase_b_summary_json" 2>/dev/null || echo "0")"
    exact_matched="$(jq -r '([.modes[]? | select(.mode=="exact_clickid") | .matched] | first) // 0' "$phase_b_summary_json" 2>/dev/null || echo "0")"
    exact_total="$(jq -r '([.modes[]? | select(.mode=="exact_clickid") | .total] | first) // 0' "$phase_b_summary_json" 2>/dev/null || echo "0")"
    fallback_matched="$(jq -r '([.modes[]? | select(.mode=="fallback_creative_time") | .matched] | first) // 0' "$phase_b_summary_json" 2>/dev/null || echo "0")"
    fallback_unmatched="$(jq -r '([.modes[]? | select(.mode=="fallback_creative_time") | .unmatched] | first) // 0' "$phase_b_summary_json" 2>/dev/null || echo "0")"
  fi
fi

total_events="$(safe_int_or_zero "$total_events")"
exact_matched="$(safe_int_or_zero "$exact_matched")"
exact_total="$(safe_int_or_zero "$exact_total")"
fallback_matched="$(safe_int_or_zero "$fallback_matched")"
fallback_unmatched="$(safe_int_or_zero "$fallback_unmatched")"

gate_exact_ready="BLOCKED"
gate_postbacks_live="BLOCKED"
gate_exact_join_live="BLOCKED"

if (( exact_ready > 0 )); then
  gate_exact_ready="PASS"
fi
if (( total_events > 0 )); then
  gate_postbacks_live="PASS"
fi
if (( exact_matched > 0 )); then
  gate_exact_join_live="PASS"
fi

overall_status="PASS"
if (( pilot_rc != 0 || phase_b_rc != 0 )); then
  overall_status="FAIL"
elif [[ "$gate_exact_ready" != "PASS" || "$gate_postbacks_live" != "PASS" || "$gate_exact_join_live" != "PASS" ]]; then
  overall_status="BLOCKED"
fi

{
  echo "# AppsFlyer Pilot Live Validation"
  echo
  echo "- generated_utc: ${STAMP}"
  echo "- buyer_id: \`${BUYER_ID}\`"
  echo "- source_type: \`${SOURCE_TYPE}\`"
  echo "- overall_status: \`${overall_status}\`"
  echo
  echo "## Step Results"
  echo
  echo "- step1_pilot_check_rc: \`${pilot_rc}\`"
  echo "- step2_phase_a_state: \`${phase_a_state}\`"
  echo "- step2_phase_a_note: \`${phase_a_note}\`"
  echo "- step2_phase_a_decision_mode: \`${phase_a_decision_mode}\`"
  echo "- step3_phase_b_rc: \`${phase_b_rc}\`"
  echo
  echo "## Live Gates"
  echo
  echo "- exact_ready_for_ingestion: \`${gate_exact_ready}\` (signal=${exact_ready})"
  echo "- postbacks_live: \`${gate_postbacks_live}\` (total_events=${total_events})"
  echo "- exact_join_live: \`${gate_exact_join_live}\` (exact_matched=${exact_matched}, exact_total=${exact_total})"
  echo
  echo "## Attribution Summary"
  echo
  echo "- total_events: \`${total_events}\`"
  echo "- exact_matched: \`${exact_matched}\`"
  echo "- exact_total: \`${exact_total}\`"
  echo "- fallback_matched: \`${fallback_matched}\`"
  echo "- fallback_unmatched: \`${fallback_unmatched}\`"
  echo
  echo "## Artifacts"
  echo
  echo "- pilot_log: \`${PILOT_LOG}\`"
  echo "- pilot_report: \`${pilot_report:-missing}\`"
  echo "- phase_a_log: \`${PHASE_A_LOG}\`"
  echo "- phase_a_contract_report: \`${phase_a_contract_report:-missing}\`"
  echo "- phase_b_log: \`${PHASE_B_LOG}\`"
  echo "- phase_b_report: \`${phase_b_report:-missing}\`"
  echo "- phase_b_summary_json: \`${phase_b_summary_json:-missing}\`"
} > "$REPORT_MD"

jq -n \
  --arg generated_utc "$STAMP" \
  --arg buyer_id "$BUYER_ID" \
  --arg source_type "$SOURCE_TYPE" \
  --arg overall_status "$overall_status" \
  --argjson pilot_rc "$pilot_rc" \
  --arg phase_a_state "$phase_a_state" \
  --arg phase_a_note "$phase_a_note" \
  --arg phase_a_decision_mode "$phase_a_decision_mode" \
  --argjson phase_b_rc "$phase_b_rc" \
  --arg gate_exact_ready "$gate_exact_ready" \
  --arg gate_postbacks_live "$gate_postbacks_live" \
  --arg gate_exact_join_live "$gate_exact_join_live" \
  --argjson exact_ready "$exact_ready" \
  --argjson total_events "$total_events" \
  --argjson exact_matched "$exact_matched" \
  --argjson exact_total "$exact_total" \
  --argjson fallback_matched "$fallback_matched" \
  --argjson fallback_unmatched "$fallback_unmatched" \
  --arg pilot_log "$PILOT_LOG" \
  --arg pilot_report "${pilot_report:-}" \
  --arg phase_a_log "$PHASE_A_LOG" \
  --arg phase_a_contract_report "${phase_a_contract_report:-}" \
  --arg phase_b_log "$PHASE_B_LOG" \
  --arg phase_b_report "${phase_b_report:-}" \
  --arg phase_b_summary_json "${phase_b_summary_json:-}" \
  '
  {
    generated_utc: $generated_utc,
    buyer_id: $buyer_id,
    source_type: $source_type,
    overall_status: $overall_status,
    steps: {
      pilot_check_rc: $pilot_rc,
      phase_a_state: $phase_a_state,
      phase_a_note: $phase_a_note,
      phase_a_decision_mode: $phase_a_decision_mode,
      phase_b_rc: $phase_b_rc
    },
    gates: {
      exact_ready_for_ingestion: {status: $gate_exact_ready, signal: $exact_ready},
      postbacks_live: {status: $gate_postbacks_live, total_events: $total_events},
      exact_join_live: {status: $gate_exact_join_live, exact_matched: $exact_matched, exact_total: $exact_total}
    },
    attribution_summary: {
      total_events: $total_events,
      exact_matched: $exact_matched,
      exact_total: $exact_total,
      fallback_matched: $fallback_matched,
      fallback_unmatched: $fallback_unmatched
    },
    artifacts: {
      pilot_log: $pilot_log,
      pilot_report: $pilot_report,
      phase_a_log: $phase_a_log,
      phase_a_contract_report: $phase_a_contract_report,
      phase_b_log: $phase_b_log,
      phase_b_report: $phase_b_report,
      phase_b_summary_json: $phase_b_summary_json
    }
  }' > "$REPORT_JSON"

if [[ -n "$DOC_OUT" ]]; then
  DOC_OUT="$(realpath -m "$DOC_OUT")"
  mkdir -p "$(dirname "$DOC_OUT")"
  cp "$REPORT_MD" "$DOC_OUT"
  echo "report_md_copy=${DOC_OUT}"
fi

echo
echo "report_md=${REPORT_MD}"
echo "report_json=${REPORT_JSON}"

case "$overall_status" in
  PASS)
    echo "Result: PASS"
    exit 0
    ;;
  BLOCKED)
    echo "Result: BLOCKED (waiting on live postback/join gates)"
    exit 2
    ;;
  *)
    echo "Result: FAIL"
    exit 1
    ;;
esac
