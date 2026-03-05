#!/usr/bin/env bash
set -euo pipefail

BUYER_ID=""
BILLING_ID="${CATSCAN_PRIME_BILLING_ID:-}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
PRETARGETING_LIMIT="${CATSCAN_PRIME_PRETARGETING_LIMIT:-500}"
DRY_RUN=0
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/run_v1_prime_with_billing_fallback.sh --buyer-id <id> [options] [-- <extra args to prime script>]

Purpose:
  Resolve a valid billing_id for a buyer (if not provided), then run
  scripts/prime_v1_optimizer_workflow_signal.sh with that billing_id.

Options:
  --buyer-id <id>            Required buyer_id
  --billing-id <id>          Optional explicit billing_id (skips auto-resolution)
  --api-base-url <url>       API base URL (default: https://scan.rtb.cat/api)
  --email <email>            X-Email identity (default: CATSCAN_CANARY_EMAIL)
  --pretargeting-limit <n>   Query limit for pretargeting lookup (default: 500)
  --dry-run                  Print resolved command without executing
  -h, --help                 Show help

Examples:
  export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
  scripts/run_v1_prime_with_billing_fallback.sh --buyer-id 1487810529 -- --timeout 60 --refresh-timeout 600 --event-count 20 --profile aggressive

  scripts/run_v1_prime_with_billing_fallback.sh --buyer-id 1487810529 --billing-id 194605230430 -- --timeout 60
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buyer-id)
      BUYER_ID="${2:-}"
      shift 2
      ;;
    --billing-id)
      BILLING_ID="${2:-}"
      shift 2
      ;;
    --api-base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --email)
      CANARY_EMAIL="${2:-}"
      shift 2
      ;;
    --pretargeting-limit)
      PRETARGETING_LIMIT="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        EXTRA_ARGS+=("$1")
        shift
      done
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$BUYER_ID" ]]; then
  echo "--buyer-id is required." >&2
  exit 2
fi
if [[ -z "$CANARY_EMAIL" ]]; then
  echo "Provide --email or set CATSCAN_CANARY_EMAIL/CATSCAN_CANARY_BEARER_TOKEN." >&2
  exit 2
fi
if ! [[ "$PRETARGETING_LIMIT" =~ ^[0-9]+$ ]] || (( PRETARGETING_LIMIT < 1 || PRETARGETING_LIMIT > 5000 )); then
  echo "Invalid --pretargeting-limit '${PRETARGETING_LIMIT}' (expected 1..5000)." >&2
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

if [[ -z "$BILLING_ID" ]]; then
  lookup_file="$(mktemp /tmp/prime_pretargeting_lookup.XXXXXX.json)"
  cleanup() { rm -f "$lookup_file"; }
  trap cleanup EXIT

  lookup_http="$(
    curl -sS -m 60 \
      -H "X-Email: ${CANARY_EMAIL}" \
      -o "$lookup_file" \
      -w "%{http_code}" \
      "${BASE_URL}/settings/pretargeting?buyer_id=${BUYER_ID}&limit=${PRETARGETING_LIMIT}&summary_only=true"
  )"
  if [[ "$lookup_http" != "200" ]]; then
    echo "Failed to resolve billing_id from pretargeting (http=${lookup_http})." >&2
    head -c 500 "$lookup_file" >&2 || true
    echo >&2
    exit 1
  fi

  BILLING_ID="$(
    jq -r '
      (
        [.[]? | select(((.billing_id // "") | tostring) != "" and (((.state // "ACTIVE") | tostring | ascii_upcase) == "ACTIVE"))]
        | .[0].billing_id
      ) // (
        [.[]? | select(((.billing_id // "") | tostring) != "")]
        | .[0].billing_id
      ) // ""
    ' "$lookup_file" 2>/dev/null || true
  )"
fi

if [[ -z "$BILLING_ID" ]]; then
  echo "Could not resolve non-empty billing_id for buyer '${BUYER_ID}'." >&2
  echo "Pass one explicitly with --billing-id." >&2
  exit 1
fi

echo "buyer_id=${BUYER_ID}"
echo "resolved_billing_id=${BILLING_ID}"
echo "base_url=${BASE_URL}"
echo "email=${CANARY_EMAIL}"

cmd=(
  scripts/prime_v1_optimizer_workflow_signal.sh
  --buyer-id "$BUYER_ID"
  --billing-id "$BILLING_ID"
)
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  cmd+=("${EXTRA_ARGS[@]}")
fi

echo "command=${cmd[*]}"
if (( DRY_RUN == 1 )); then
  exit 0
fi

export CATSCAN_API_BASE_URL="$BASE_URL"
export CATSCAN_CANARY_EMAIL="$CANARY_EMAIL"
"${cmd[@]}"
