#!/usr/bin/env bash
set -euo pipefail

# Wrapper around scripts/v1_canary_smoke.py with env-driven defaults.
# Required env:
#   CATSCAN_API_BASE_URL
# Optional env:
#   CATSCAN_BUYER_ID, CATSCAN_MODEL_ID, CATSCAN_BEARER_TOKEN, CATSCAN_SESSION_COOKIE,
#   CATSCAN_CANARY_RUN_WORKFLOW=1, CATSCAN_ALLOW_NO_ACTIVE_MODEL=1,
#   CATSCAN_ROLLBACK_BILLING_ID, CATSCAN_ROLLBACK_SNAPSHOT_ID

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${CATSCAN_API_BASE_URL:-http://127.0.0.1:8000}"

args=(
  "--base-url" "$BASE_URL"
)

if [[ -n "${CATSCAN_BUYER_ID:-}" ]]; then
  args+=("--buyer-id" "$CATSCAN_BUYER_ID")
fi

if [[ -n "${CATSCAN_MODEL_ID:-}" ]]; then
  args+=("--model-id" "$CATSCAN_MODEL_ID")
fi

if [[ -n "${CATSCAN_BEARER_TOKEN:-}" ]]; then
  args+=("--token" "$CATSCAN_BEARER_TOKEN")
fi

if [[ -n "${CATSCAN_SESSION_COOKIE:-}" ]]; then
  args+=("--cookie" "$CATSCAN_SESSION_COOKIE")
fi

if [[ "${CATSCAN_CANARY_RUN_WORKFLOW:-0}" == "1" ]]; then
  args+=("--run-workflow")
fi

if [[ "${CATSCAN_ALLOW_NO_ACTIVE_MODEL:-0}" == "1" ]]; then
  args+=("--allow-no-active-model")
fi

if [[ -n "${CATSCAN_ROLLBACK_BILLING_ID:-}" ]]; then
  args+=("--billing-id" "$CATSCAN_ROLLBACK_BILLING_ID")
fi

if [[ -n "${CATSCAN_ROLLBACK_SNAPSHOT_ID:-}" ]]; then
  args+=("--snapshot-id" "$CATSCAN_ROLLBACK_SNAPSHOT_ID")
fi

exec python3 "$ROOT_DIR/scripts/v1_canary_smoke.py" "${args[@]}" "$@"
