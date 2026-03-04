#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BUYER_ID="${CATSCAN_BUYER_ID:-1487810529}"
PROFILE="${CATSCAN_CANARY_PROFILE:-balanced}"
EXPIRES_ON="${CATSCAN_CANARY_BIDSTREAM_WAIVER_EXPIRES_ON:-2026-06-30}"
NOTE="${CATSCAN_CANARY_BIDSTREAM_WAIVER_NOTE:-Google RTB source for this buyer does not provide platform/environment/transaction_type dimensions}"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_v1_runtime_health_strict_with_waiver.sh [options]

Options:
  --buyer-id <id>      Buyer ID (default: 1487810529)
  --profile <name>     safe|balanced|aggressive (default: balanced)
  --expires-on <date>  Waiver expiry YYYY-MM-DD (default: 2026-06-30)
  --note <text>        Waiver note (default: Google dimension source gap note)
  -h, --help           Show help

Example:
  scripts/run_v1_runtime_health_strict_with_waiver.sh --buyer-id 1487810529 --profile balanced
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

WAIVER_JSON="$(
  python3 - "$BUYER_ID" "$EXPIRES_ON" "$NOTE" <<'PY'
import json
import sys

buyer_id, expires_on, note = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps([{
    "buyer_id": buyer_id,
    "expires_on": expires_on,
    "note": note,
}], separators=(",", ":")))
PY
)"

echo "buyer_id=${BUYER_ID}"
echo "profile=${PROFILE}"
echo "waiver_expires_on=${EXPIRES_ON}"
echo "waiver_note=${NOTE}"

exec scripts/run_v1_runtime_health_strict_dispatch.sh \
  --buyer-id "$BUYER_ID" \
  --profile "$PROFILE" \
  --bidstream-waiver-json "$WAIVER_JSON"

