#!/usr/bin/env bash
set -euo pipefail

BUYER_ID="${CATSCAN_BUYER_ID:-}"
SOURCE_TYPE="${CATSCAN_CONVERSION_SOURCE_TYPE:-appsflyer}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://your-deployment.example.com/api}"
INPUT_FORMAT="auto"
OUT_DIR="${CATSCAN_OUTPUT_DIR:-/tmp}"
DOC_OUT=""
MAPPING_PROFILE_PATH=""
FETCH_MAPPING="auto"
API_TOKEN="${CATSCAN_API_TOKEN:-}"
API_EMAIL="${CATSCAN_CANARY_EMAIL:-}"
FROM_DB="false"
DB_SINCE_DAYS="${CATSCAN_APPSFLYER_DB_SINCE_DAYS:-30}"
DB_LIMIT="${CATSCAN_APPSFLYER_DB_LIMIT:-500000}"
DB_DSN="${CATSCAN_POSTGRES_DSN:-}"

declare -a INPUT_FILES=()

usage() {
  cat <<'EOF'
Usage:
  scripts/run_appsflyer_phase_a_audit.sh --buyer-id <id> [--input <file> ...] [options]

Purpose:
  Executes AppsFlyer Phase-A buyer audit in one command:
    1) resolves mapping profile (file or API),
    2) runs export coverage audit,
    3) writes a contract-style markdown report.

Required:
  --buyer-id <id>                 Buyer ID
  One of:
    --input <path>                AppsFlyer export file (CSV/JSONL); repeatable
    --from-db                     Export raw AppsFlyer payloads from conversion_events first

Options:
  --source-type <name>            Conversion source type (default: appsflyer)
  --input-format <auto|csv|jsonl> Input parser mode (default: auto)
  --from-db                       Use conversion_events.raw_payload export as audit input
  --db-since-days <n>             DB export lookback days (default: 30)
  --db-limit <n>                  DB export row limit (default: 500000)
  --db-dsn <dsn>                  Postgres DSN override for --from-db path
  --mapping-profile <path>        Mapping profile JSON file (skip API fetch)
  --fetch-mapping <auto|true|false>
                                  Fetch mapping via API when no --mapping-profile (default: auto)
  --api-base-url <url>            API base URL (default: https://your-deployment.example.com/api)
  --token <value>                 Bearer token for mapping API
  --email <value>                 X-Email for mapping API (if no token)
  --out-dir <dir>                 Output root (default: /tmp)
  --doc-out <path>                Optional final markdown path to write
  -h, --help                      Show help

Examples:
  scripts/run_appsflyer_phase_a_audit.sh \
    --buyer-id 1111111111 \
    --input ~/Downloads/appsflyer_raw_2026-03-01.csv

  scripts/run_appsflyer_phase_a_audit.sh \
    --buyer-id 1111111111 \
    --from-db \
    --db-since-days 14 \
    --email user@example.com

  scripts/run_appsflyer_phase_a_audit.sh \
    --buyer-id 1111111111 \
    --input /data/af_day1.csv --input /data/af_day2.csv \
    --fetch-mapping true \
    --email user@example.com \
    --doc-out docs/review/2026-03-03/APPSFLYER_PHASE_A_BUYER_1111111111.md
EOF
}

normalize_bool() {
  case "${1,,}" in
    1|true|yes|y) echo "true" ;;
    0|false|no|n) echo "false" ;;
    *)
      echo "Invalid boolean-like value '${1}' (expected true/false)." >&2
      exit 2
      ;;
  esac
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
    --input)
      INPUT_FILES+=("${2:-}")
      shift 2
      ;;
    --input-format)
      INPUT_FORMAT="${2:-}"
      shift 2
      ;;
    --from-db)
      FROM_DB="true"
      shift
      ;;
    --db-since-days)
      DB_SINCE_DAYS="${2:-}"
      shift 2
      ;;
    --db-limit)
      DB_LIMIT="${2:-}"
      shift 2
      ;;
    --db-dsn)
      DB_DSN="${2:-}"
      shift 2
      ;;
    --mapping-profile)
      MAPPING_PROFILE_PATH="${2:-}"
      shift 2
      ;;
    --fetch-mapping)
      FETCH_MAPPING="${2:-}"
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
if [[ "$FROM_DB" != "true" && "${#INPUT_FILES[@]}" -eq 0 ]]; then
  echo "Provide at least one --input or use --from-db." >&2
  exit 2
fi
case "$INPUT_FORMAT" in
  auto|csv|jsonl) ;;
  *)
    echo "Invalid --input-format '${INPUT_FORMAT}' (expected auto|csv|jsonl)." >&2
    exit 2
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "'python3' is required." >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "'jq' is required." >&2
  exit 2
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "'curl' is required." >&2
  exit 2
fi
if [[ "$FROM_DB" == "true" && ! "$DB_SINCE_DAYS" =~ ^[0-9]+$ ]]; then
  echo "Invalid --db-since-days '${DB_SINCE_DAYS}' (expected integer)." >&2
  exit 2
fi
if [[ "$FROM_DB" == "true" && ! "$DB_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "Invalid --db-limit '${DB_LIMIT}' (expected integer)." >&2
  exit 2
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${OUT_DIR%/}/appsflyer-phase-a-${BUYER_ID}-${STAMP}"
mkdir -p "$RUN_DIR"

BASE_URL="${BASE_URL%/}"
MAPPING_SCOPE="builtin_default"
MAPPING_SETTING_KEY=""
MAPPING_FALLBACK_KEY=""
DB_EXPORT_PATH=""

if [[ -n "$MAPPING_PROFILE_PATH" ]]; then
  MAPPING_PROFILE_PATH="$(realpath "$MAPPING_PROFILE_PATH")"
  if [[ ! -f "$MAPPING_PROFILE_PATH" ]]; then
    echo "Mapping profile not found: $MAPPING_PROFILE_PATH" >&2
    exit 2
  fi
  MAPPING_SCOPE="file"
else
  case "${FETCH_MAPPING,,}" in
    auto)
      if [[ -n "$API_TOKEN" || -n "$API_EMAIL" ]]; then
        FETCH_MAPPING="true"
      else
        FETCH_MAPPING="false"
      fi
      ;;
    true|false|yes|no|1|0|y|n)
      FETCH_MAPPING="$(normalize_bool "$FETCH_MAPPING")"
      ;;
    *)
      echo "Invalid --fetch-mapping '${FETCH_MAPPING}' (expected auto|true|false)." >&2
      exit 2
      ;;
  esac

  if [[ "$FETCH_MAPPING" == "true" ]]; then
    MAP_RESPONSE_JSON="${RUN_DIR}/mapping_profile_response.json"
    MAP_RESPONSE_BODY="${RUN_DIR}/mapping_profile_body.json"

    declare -a AUTH_HEADER=()
    if [[ -n "$API_TOKEN" ]]; then
      AUTH_HEADER=(-H "Authorization: Bearer ${API_TOKEN}")
    elif [[ -n "$API_EMAIL" ]]; then
      AUTH_HEADER=(-H "X-Email: ${API_EMAIL}")
    else
      echo "Mapping fetch requested but no --token or --email provided." >&2
      exit 2
    fi

    HTTP_CODE="$(
      curl -sS \
        "${AUTH_HEADER[@]}" \
        -o "$MAP_RESPONSE_BODY" \
        -w "%{http_code}" \
        "${BASE_URL}/conversions/mapping-profile?source_type=${SOURCE_TYPE}&buyer_id=${BUYER_ID}"
    )"

    if [[ "$HTTP_CODE" != "200" ]]; then
      echo "Failed to fetch mapping profile (http=${HTTP_CODE})." >&2
      head -c 500 "$MAP_RESPONSE_BODY" >&2 || true
      exit 1
    fi

    jq '.' "$MAP_RESPONSE_BODY" > "$MAP_RESPONSE_JSON"
    MAPPING_SCOPE="$(jq -r '.scope // "unknown"' "$MAP_RESPONSE_JSON")"
    MAPPING_SETTING_KEY="$(jq -r '.setting_key // ""' "$MAP_RESPONSE_JSON")"
    MAPPING_FALLBACK_KEY="$(jq -r '.fallback_setting_key // ""' "$MAP_RESPONSE_JSON")"
    MAPPING_PROFILE_PATH="${RUN_DIR}/mapping_profile.json"
    jq -c '{field_map: (.field_map // {})}' "$MAP_RESPONSE_JSON" > "$MAPPING_PROFILE_PATH"
  fi
fi

if [[ "$FROM_DB" == "true" ]]; then
  DB_EXPORT_PATH="${RUN_DIR}/appsflyer_events_from_db.jsonl"
  DB_EXPORT_CMD=(
    python3 scripts/export_appsflyer_events_jsonl.py
    --buyer-id "$BUYER_ID"
    --source-type "$SOURCE_TYPE"
    --since-days "$DB_SINCE_DAYS"
    --limit "$DB_LIMIT"
    --out "$DB_EXPORT_PATH"
  )
  if [[ -n "$DB_DSN" ]]; then
    DB_EXPORT_CMD+=(--dsn "$DB_DSN")
  fi
  echo "Exporting AppsFlyer events from DB..."
  "${DB_EXPORT_CMD[@]}"
  INPUT_FILES+=("$DB_EXPORT_PATH")
fi

COVERAGE_MD="${RUN_DIR}/coverage.md"
COVERAGE_JSON="${RUN_DIR}/coverage.json"
CONTRACT_MD="${RUN_DIR}/phase_a_contract.md"

CMD=(python3 scripts/audit_appsflyer_export_coverage.py --input-format "$INPUT_FORMAT")
for input_file in "${INPUT_FILES[@]}"; do
  CMD+=(--input "$input_file")
done
if [[ -n "$MAPPING_PROFILE_PATH" ]]; then
  CMD+=(--mapping-profile "$MAPPING_PROFILE_PATH")
fi
CMD+=(--out "$COVERAGE_MD" --json-out "$COVERAGE_JSON")

echo "Run dir: ${RUN_DIR}"
echo "Buyer: ${BUYER_ID}"
echo "Source type: ${SOURCE_TYPE}"
echo "Input files: ${#INPUT_FILES[@]}"
echo "Mapping scope: ${MAPPING_SCOPE}"
if [[ -n "$DB_EXPORT_PATH" ]]; then
  echo "DB export: ${DB_EXPORT_PATH}"
fi
echo
echo "Running coverage audit..."
"${CMD[@]}"

TOTAL_ROWS="$(jq -r '.combined.rows // 0' "$COVERAGE_JSON")"
CLICKID_PCT="$(jq -r '.combined.click_id_present_pct // 0' "$COVERAGE_JSON")"
EXACT_PCT="$(jq -r '.combined.exact_ready_pct // 0' "$COVERAGE_JSON")"
FALLBACK_PCT="$(jq -r '.combined.fallback_ready_pct // 0' "$COVERAGE_JSON")"
DECISION_MODE="$(jq -r '.decision.mode // "unknown"' "$COVERAGE_JSON")"
DECISION_MESSAGE="$(jq -r '.decision.message // ""' "$COVERAGE_JSON")"

{
  echo "# AppsFlyer Phase-A Buyer Contract"
  echo
  echo "- generated_utc: ${STAMP}"
  echo "- buyer_id: \`${BUYER_ID}\`"
  echo "- source_type: \`${SOURCE_TYPE}\`"
  echo "- total_rows_scanned: \`${TOTAL_ROWS}\`"
  echo "- mapping_scope: \`${MAPPING_SCOPE}\`"
  if [[ -n "$MAPPING_SETTING_KEY" ]]; then
    echo "- mapping_setting_key: \`${MAPPING_SETTING_KEY}\`"
  fi
  if [[ -n "$MAPPING_FALLBACK_KEY" ]]; then
    echo "- mapping_fallback_key: \`${MAPPING_FALLBACK_KEY}\`"
  fi
  echo
  echo "## Coverage Summary"
  echo
  echo "- clickid_present_pct: \`${CLICKID_PCT}\`"
  echo "- exact_ready_pct: \`${EXACT_PCT}\`"
  echo "- fallback_ready_pct: \`${FALLBACK_PCT}\`"
  echo "- decision_mode: \`${DECISION_MODE}\`"
  echo "- decision_message: ${DECISION_MESSAGE}"
  echo
  echo "## Inputs"
  echo
  for input_file in "${INPUT_FILES[@]}"; do
    echo "- \`$(realpath "$input_file")\`"
  done
  echo
  echo "## Artifacts"
  echo
  echo "- coverage_markdown: \`${COVERAGE_MD}\`"
  echo "- coverage_json: \`${COVERAGE_JSON}\`"
  if [[ -n "$MAPPING_PROFILE_PATH" ]]; then
    echo "- mapping_profile_used: \`${MAPPING_PROFILE_PATH}\`"
  else
    echo "- mapping_profile_used: \`builtin default\`"
  fi
  if [[ -n "$DB_EXPORT_PATH" ]]; then
    echo "- db_export_input: \`${DB_EXPORT_PATH}\`"
  fi
  echo
  echo "## Next Action Gate"
  echo
  case "$DECISION_MODE" in
    exact_ready)
      echo "- Proceed to Phase B with exact-join path as primary."
      ;;
    mixed_mode)
      echo "- Proceed to Phase B with mixed-mode joins and explicit confidence gating."
      ;;
    *)
      echo "- Hold strict automation; prioritize clickid propagation before Phase B hard actions."
      ;;
  esac
  echo
  echo "## Raw Coverage Report"
  echo
  cat "$COVERAGE_MD"
} > "$CONTRACT_MD"

echo
echo "Contract report: ${CONTRACT_MD}"
if [[ -n "$DOC_OUT" ]]; then
  DOC_OUT="$(realpath -m "$DOC_OUT")"
  mkdir -p "$(dirname "$DOC_OUT")"
  cp "$CONTRACT_MD" "$DOC_OUT"
  echo "Copied contract report to: ${DOC_OUT}"
fi
