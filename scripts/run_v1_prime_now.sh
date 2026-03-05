#!/usr/bin/env bash
set -euo pipefail

# One-command runner for optimizer signal priming with safe defaults.
# Avoids multiline paste issues in terminals.

BUYER_ID="${CATSCAN_BUYER_ID:-1111111111}"
BUYER_ID_SET=0
BILLING_ID="${CATSCAN_PRIME_BILLING_ID:-}"
BASE_URL="${CATSCAN_API_BASE_URL:-}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-}"
PRETARGETING_LIMIT="${CATSCAN_PRIME_PRETARGETING_LIMIT:-}"
DRY_RUN=0
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-60}"
REFRESH_TIMEOUT_SECONDS="${CATSCAN_PRIME_REFRESH_TIMEOUT_SECONDS:-600}"
REFRESH_DAYS="${CATSCAN_PRIME_REFRESH_DAYS:-1}"
EVENT_COUNT="${CATSCAN_PRIME_EVENT_COUNT:-20}"
WORKFLOW_PROFILE="${CATSCAN_CANARY_PROFILE:-aggressive}"
POST_REFRESH_WAIT_SECONDS="${CATSCAN_PRIME_POST_REFRESH_WAIT_SECONDS:-300}"
POLL_INTERVAL_SECONDS="${CATSCAN_PRIME_POLL_INTERVAL_SECONDS:-10}"
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/run_v1_prime_now.sh [buyer_id]
  scripts/run_v1_prime_now.sh --buyer-id <id> [options] [-- <extra args for prime script>]

Purpose:
  Run v1 optimizer signal priming with safe defaults and automatic billing_id
  resolution via scripts/run_v1_prime_with_billing_fallback.sh.

Options:
  --buyer-id <id>          Optional buyer_id override (default: 1111111111)
  --billing-id <id>        Optional explicit billing_id
  --api-base-url <url>     Optional API base URL override
  --email <email>          Optional X-Email override
  --pretargeting-limit <n> Optional pretargeting lookup limit
  --dry-run                Resolve/print command without executing prime workflow
  -h, --help               Show help

Examples:
  scripts/run_v1_prime_now.sh
  scripts/run_v1_prime_now.sh 1111111111
  scripts/run_v1_prime_now.sh --buyer-id 1111111111 --billing-id 555555555555 --dry-run
  scripts/run_v1_prime_now.sh --buyer-id 1111111111 -- --timeout 45 --event-count 30
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buyer-id)
      if (( BUYER_ID_SET == 1 )); then
        echo "Buyer ID provided more than once." >&2
        usage >&2
        exit 2
      fi
      BUYER_ID="${2:-}"
      BUYER_ID_SET=1
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
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if (( BUYER_ID_SET == 1 )); then
        echo "Buyer ID provided more than once." >&2
        usage >&2
        exit 2
      fi
      BUYER_ID="$1"
      BUYER_ID_SET=1
      shift
      ;;
  esac
done

if [[ -z "$BUYER_ID" ]]; then
  echo "--buyer-id is required." >&2
  exit 2
fi

if [[ -z "$CANARY_EMAIL" && -z "${CATSCAN_CANARY_BEARER_TOKEN:-}" ]]; then
  CANARY_EMAIL="user@example.com"
fi

if [[ ! -x "scripts/run_v1_prime_with_billing_fallback.sh" ]]; then
  echo "Missing helper script: scripts/run_v1_prime_with_billing_fallback.sh" >&2
  exit 1
fi

helper_cmd=(
  scripts/run_v1_prime_with_billing_fallback.sh
  --buyer-id "$BUYER_ID"
)
if [[ -n "$BILLING_ID" ]]; then
  helper_cmd+=(--billing-id "$BILLING_ID")
fi
if [[ -n "$BASE_URL" ]]; then
  helper_cmd+=(--api-base-url "$BASE_URL")
fi
if [[ -n "$CANARY_EMAIL" ]]; then
  helper_cmd+=(--email "$CANARY_EMAIL")
fi
if [[ -n "$PRETARGETING_LIMIT" ]]; then
  helper_cmd+=(--pretargeting-limit "$PRETARGETING_LIMIT")
fi
if (( DRY_RUN == 1 )); then
  helper_cmd+=(--dry-run)
fi
helper_cmd+=(
  --
  --timeout "$TIMEOUT_SECONDS"
  --refresh-timeout "$REFRESH_TIMEOUT_SECONDS"
  --refresh-days "$REFRESH_DAYS"
  --event-count "$EVENT_COUNT"
  --profile "$WORKFLOW_PROFILE"
  --post-refresh-wait "$POST_REFRESH_WAIT_SECONDS"
  --poll-interval "$POLL_INTERVAL_SECONDS"
)
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  helper_cmd+=("${EXTRA_ARGS[@]}")
fi

exec "${helper_cmd[@]}"
