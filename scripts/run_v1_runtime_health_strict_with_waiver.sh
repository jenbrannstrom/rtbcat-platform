#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BUYER_ID="${CATSCAN_BUYER_ID:-1111111111}"
PROFILE="${CATSCAN_CANARY_PROFILE:-balanced}"
EXPIRES_ON="${CATSCAN_CANARY_BIDSTREAM_WAIVER_EXPIRES_ON:-2026-06-30}"
NOTE="${CATSCAN_CANARY_BIDSTREAM_WAIVER_NOTE:-Google RTB source for this buyer does not provide platform/environment/transaction_type dimensions}"
ALLOW_UNAVAILABLE="${CATSCAN_CANARY_BIDSTREAM_WAIVER_ALLOW_UNAVAILABLE:-1}"
ALLOW_ZERO_ROWS="${CATSCAN_CANARY_BIDSTREAM_WAIVER_ALLOW_ZERO_ROWS:-1}"
ALLOW_ALL_DIMENSIONS_MISSING="${CATSCAN_CANARY_BIDSTREAM_WAIVER_ALLOW_ALL_DIMENSIONS_MISSING:-1}"
ALLOW_REPORT_COMPLETENESS_DEGRADED="${CATSCAN_CANARY_BIDSTREAM_WAIVER_ALLOW_REPORT_COMPLETENESS_DEGRADED:-1}"
ALLOW_SEAT_DAY_COMPLETENESS_DEGRADED="${CATSCAN_CANARY_BIDSTREAM_WAIVER_ALLOW_SEAT_DAY_COMPLETENESS_DEGRADED:-1}"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_v1_runtime_health_strict_with_waiver.sh [options]

Options:
  --buyer-id <id>      Buyer ID (default: 1111111111)
  --profile <name>     safe|balanced|aggressive (default: balanced)
  --expires-on <date>  Waiver expiry YYYY-MM-DD (default: 2026-06-30)
  --note <text>        Waiver note (default: Google dimension source gap note)
  --allow-unavailable <0|1>
                       Allow bidstream availability_state=unavailable (default: 1)
  --allow-zero-rows <0|1>
                       Allow bidstream total_rows=0 (default: 1)
  --allow-all-missing <0|1>
                       Allow all 3 bidstream dimension missing%%=100 (default: 1)
  --allow-report-completeness-degraded <0|1>
                       Allow data-health report_completeness=degraded/unavailable (default: 1)
  --allow-seat-day-completeness-degraded <0|1>
                       Allow data-health seat_day_completeness=degraded/unavailable (default: 1)
  -h, --help           Show help

Example:
  scripts/run_v1_runtime_health_strict_with_waiver.sh --buyer-id 1111111111 --profile balanced
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buyer-id)
      BUYER_ID="${2:-}"
      shift 2
      ;;
    --profile)
      PROFILE="${2:-}"
      shift 2
      ;;
    --expires-on)
      EXPIRES_ON="${2:-}"
      shift 2
      ;;
    --note)
      NOTE="${2:-}"
      shift 2
      ;;
    --allow-unavailable)
      ALLOW_UNAVAILABLE="${2:-}"
      shift 2
      ;;
    --allow-zero-rows)
      ALLOW_ZERO_ROWS="${2:-}"
      shift 2
      ;;
    --allow-all-missing)
      ALLOW_ALL_DIMENSIONS_MISSING="${2:-}"
      shift 2
      ;;
    --allow-report-completeness-degraded)
      ALLOW_REPORT_COMPLETENESS_DEGRADED="${2:-}"
      shift 2
      ;;
    --allow-seat-day-completeness-degraded)
      ALLOW_SEAT_DAY_COMPLETENESS_DEGRADED="${2:-}"
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
if ! [[ "$EXPIRES_ON" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "--expires-on must be YYYY-MM-DD." >&2
  exit 2
fi
for flag in "$ALLOW_UNAVAILABLE" "$ALLOW_ZERO_ROWS" "$ALLOW_ALL_DIMENSIONS_MISSING" "$ALLOW_REPORT_COMPLETENESS_DEGRADED" "$ALLOW_SEAT_DAY_COMPLETENESS_DEGRADED"; do
  if [[ "$flag" != "0" && "$flag" != "1" ]]; then
    echo "allow flags must be 0 or 1." >&2
    exit 2
  fi
done

WAIVER_JSON="$(
  python3 - "$BUYER_ID" "$EXPIRES_ON" "$NOTE" "$ALLOW_UNAVAILABLE" "$ALLOW_ZERO_ROWS" "$ALLOW_ALL_DIMENSIONS_MISSING" "$ALLOW_REPORT_COMPLETENESS_DEGRADED" "$ALLOW_SEAT_DAY_COMPLETENESS_DEGRADED" <<'PY'
import json
import sys

buyer_id = sys.argv[1]
expires_on = sys.argv[2]
note = sys.argv[3]
allow_unavailable = sys.argv[4] == "1"
allow_zero_rows = sys.argv[5] == "1"
allow_all_dimensions_missing = sys.argv[6] == "1"
allow_report_completeness_degraded = sys.argv[7] == "1"
allow_seat_day_completeness_degraded = sys.argv[8] == "1"
print(json.dumps([{
    "buyer_id": buyer_id,
    "expires_on": expires_on,
    "note": note,
    "allow_unavailable": allow_unavailable,
    "allow_zero_rows": allow_zero_rows,
    "allow_all_dimensions_missing": allow_all_dimensions_missing,
    "allow_report_completeness_degraded": allow_report_completeness_degraded,
    "allow_seat_day_completeness_degraded": allow_seat_day_completeness_degraded,
}], separators=(",", ":")))
PY
)"

echo "buyer_id=${BUYER_ID}"
echo "profile=${PROFILE}"
echo "waiver_expires_on=${EXPIRES_ON}"
echo "waiver_note=${NOTE}"
echo "waiver_allow_unavailable=${ALLOW_UNAVAILABLE}"
echo "waiver_allow_zero_rows=${ALLOW_ZERO_ROWS}"
echo "waiver_allow_all_dimensions_missing=${ALLOW_ALL_DIMENSIONS_MISSING}"
echo "waiver_allow_report_completeness_degraded=${ALLOW_REPORT_COMPLETENESS_DEGRADED}"
echo "waiver_allow_seat_day_completeness_degraded=${ALLOW_SEAT_DAY_COMPLETENESS_DEGRADED}"

exec scripts/run_v1_runtime_health_strict_dispatch.sh \
  --buyer-id "$BUYER_ID" \
  --profile "$PROFILE" \
  --bidstream-waiver-json "$WAIVER_JSON"
