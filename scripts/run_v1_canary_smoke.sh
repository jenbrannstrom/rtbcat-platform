#!/usr/bin/env bash
set -euo pipefail

# Wrapper around scripts/v1_canary_smoke.py with env-driven defaults.
# Required env:
#   CATSCAN_API_BASE_URL
# Optional env:
#   CATSCAN_BUYER_ID, CATSCAN_MODEL_ID, CATSCAN_PROPOSAL_ID, CATSCAN_BEARER_TOKEN, CATSCAN_SESSION_COOKIE,
#   CATSCAN_CANARY_RUN_WORKFLOW=1, CATSCAN_CANARY_RUN_LIFECYCLE=1, CATSCAN_ALLOW_NO_ACTIVE_MODEL=1,
#   CATSCAN_CANARY_RUN_PIXEL=1, CATSCAN_CANARY_PIXEL_SOURCE_TYPE=pixel,
#   CATSCAN_CANARY_PIXEL_EVENT_NAME=purchase, CATSCAN_CANARY_PIXEL_SECRET=<secret>,
#   CATSCAN_CANARY_PIXEL_EXPECTED_STATUS=accepted|rejected,
#   CATSCAN_CANARY_RUN_WEBHOOK_AUTH=1, CATSCAN_CANARY_WEBHOOK_SOURCE_TYPE=generic,
#   CATSCAN_CANARY_WEBHOOK_EVENT_NAME=purchase, CATSCAN_CANARY_WEBHOOK_SECRET=<secret>,
#   CATSCAN_CANARY_REQUIRE_CONVERSION_READY=1,
#   CATSCAN_CANARY_CONVERSION_DAYS=14, CATSCAN_CANARY_CONVERSION_FRESHNESS_HOURS=72,
#   CATSCAN_ROLLBACK_BILLING_ID, CATSCAN_ROLLBACK_SNAPSHOT_ID,
#   CATSCAN_CANARY_REQUIRE_HEALTHY_READINESS=1, CATSCAN_MAX_DIMENSION_MISSING_PCT=99.9,
#   CATSCAN_CANARY_PROFILE=safe|balanced|aggressive,
#   CATSCAN_CANARY_WORKFLOW_PROFILE=safe|balanced|aggressive,
#   CATSCAN_CANARY_WORKFLOW_DAYS=14, CATSCAN_CANARY_WORKFLOW_SCORE_LIMIT=1000,
#   CATSCAN_CANARY_WORKFLOW_PROPOSAL_LIMIT=200, CATSCAN_CANARY_WORKFLOW_MIN_CONFIDENCE=0.3,
#   CATSCAN_CANARY_WORKFLOW_MAX_DELTA_PCT=0.3

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${CATSCAN_API_BASE_URL:-http://127.0.0.1:8000}"
PROFILE="${CATSCAN_CANARY_PROFILE:-}"

case "${PROFILE,,}" in
  ""|"balanced")
    PROFILE_DAYS="14"
    PROFILE_SCORE_LIMIT="1000"
    PROFILE_PROPOSAL_LIMIT="200"
    PROFILE_MIN_CONFIDENCE="0.3"
    PROFILE_MAX_DELTA="0.3"
    ;;
  "safe")
    PROFILE_DAYS="14"
    PROFILE_SCORE_LIMIT="500"
    PROFILE_PROPOSAL_LIMIT="100"
    PROFILE_MIN_CONFIDENCE="0.45"
    PROFILE_MAX_DELTA="0.2"
    ;;
  "aggressive")
    PROFILE_DAYS="7"
    PROFILE_SCORE_LIMIT="2000"
    PROFILE_PROPOSAL_LIMIT="400"
    PROFILE_MIN_CONFIDENCE="0.2"
    PROFILE_MAX_DELTA="0.5"
    ;;
  *)
    echo "Unsupported CATSCAN_CANARY_PROFILE: ${PROFILE} (expected safe|balanced|aggressive)" >&2
    exit 2
    ;;
esac

: "${CATSCAN_CANARY_WORKFLOW_DAYS:=$PROFILE_DAYS}"
: "${CATSCAN_CANARY_WORKFLOW_SCORE_LIMIT:=$PROFILE_SCORE_LIMIT}"
: "${CATSCAN_CANARY_WORKFLOW_PROPOSAL_LIMIT:=$PROFILE_PROPOSAL_LIMIT}"
: "${CATSCAN_CANARY_WORKFLOW_MIN_CONFIDENCE:=$PROFILE_MIN_CONFIDENCE}"
: "${CATSCAN_CANARY_WORKFLOW_MAX_DELTA_PCT:=$PROFILE_MAX_DELTA}"
: "${CATSCAN_CANARY_WORKFLOW_DAYS:=14}"
: "${CATSCAN_CANARY_WORKFLOW_SCORE_LIMIT:=1000}"
: "${CATSCAN_CANARY_WORKFLOW_PROPOSAL_LIMIT:=200}"
: "${CATSCAN_CANARY_WORKFLOW_MIN_CONFIDENCE:=0.3}"
: "${CATSCAN_CANARY_WORKFLOW_MAX_DELTA_PCT:=0.3}"
WORKFLOW_PROFILE="${CATSCAN_CANARY_WORKFLOW_PROFILE:-${PROFILE,,}}"

args=(
  "--base-url" "$BASE_URL"
)

if [[ -n "${CATSCAN_BUYER_ID:-}" ]]; then
  args+=("--buyer-id" "$CATSCAN_BUYER_ID")
fi

if [[ -n "${CATSCAN_MODEL_ID:-}" ]]; then
  args+=("--model-id" "$CATSCAN_MODEL_ID")
fi

if [[ -n "${CATSCAN_PROPOSAL_ID:-}" ]]; then
  args+=("--proposal-id" "$CATSCAN_PROPOSAL_ID")
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

if [[ "${CATSCAN_CANARY_RUN_LIFECYCLE:-0}" == "1" ]]; then
  args+=("--run-lifecycle")
fi

if [[ "${CATSCAN_CANARY_REQUIRE_CONVERSION_READY:-0}" == "1" ]]; then
  args+=("--require-conversion-ready")
fi

if [[ "${CATSCAN_CANARY_RUN_PIXEL:-0}" == "1" ]]; then
  args+=("--run-pixel")
fi

if [[ "${CATSCAN_CANARY_RUN_WEBHOOK_AUTH:-0}" == "1" ]]; then
  args+=("--run-webhook-auth-check")
fi

if [[ -n "${CATSCAN_CANARY_CONVERSION_DAYS:-}" ]]; then
  args+=("--conversion-readiness-days" "$CATSCAN_CANARY_CONVERSION_DAYS")
fi

if [[ -n "${CATSCAN_CANARY_CONVERSION_FRESHNESS_HOURS:-}" ]]; then
  args+=("--conversion-readiness-freshness-hours" "$CATSCAN_CANARY_CONVERSION_FRESHNESS_HOURS")
fi

if [[ -n "${CATSCAN_CANARY_PIXEL_SOURCE_TYPE:-}" ]]; then
  args+=("--pixel-source-type" "$CATSCAN_CANARY_PIXEL_SOURCE_TYPE")
fi

if [[ -n "${CATSCAN_CANARY_PIXEL_EVENT_NAME:-}" ]]; then
  args+=("--pixel-event-name" "$CATSCAN_CANARY_PIXEL_EVENT_NAME")
fi

if [[ -n "${CATSCAN_CANARY_PIXEL_SECRET:-}" ]]; then
  args+=("--pixel-secret" "$CATSCAN_CANARY_PIXEL_SECRET")
fi

if [[ -n "${CATSCAN_CANARY_PIXEL_EXPECTED_STATUS:-}" ]]; then
  args+=("--pixel-expected-status" "$CATSCAN_CANARY_PIXEL_EXPECTED_STATUS")
fi

if [[ -n "${CATSCAN_CANARY_WEBHOOK_SOURCE_TYPE:-}" ]]; then
  args+=("--webhook-source-type" "$CATSCAN_CANARY_WEBHOOK_SOURCE_TYPE")
fi

if [[ -n "${CATSCAN_CANARY_WEBHOOK_EVENT_NAME:-}" ]]; then
  args+=("--webhook-event-name" "$CATSCAN_CANARY_WEBHOOK_EVENT_NAME")
fi

if [[ -n "${CATSCAN_CANARY_WEBHOOK_SECRET:-}" ]]; then
  args+=("--webhook-secret" "$CATSCAN_CANARY_WEBHOOK_SECRET")
fi

if [[ -n "${WORKFLOW_PROFILE:-}" ]]; then
  args+=("--workflow-profile" "${WORKFLOW_PROFILE,,}")
fi

if [[ -n "${CATSCAN_CANARY_WORKFLOW_DAYS:-}" ]]; then
  args+=("--workflow-days" "$CATSCAN_CANARY_WORKFLOW_DAYS")
fi

if [[ -n "${CATSCAN_CANARY_WORKFLOW_SCORE_LIMIT:-}" ]]; then
  args+=("--workflow-score-limit" "$CATSCAN_CANARY_WORKFLOW_SCORE_LIMIT")
fi

if [[ -n "${CATSCAN_CANARY_WORKFLOW_PROPOSAL_LIMIT:-}" ]]; then
  args+=("--workflow-proposal-limit" "$CATSCAN_CANARY_WORKFLOW_PROPOSAL_LIMIT")
fi

if [[ -n "${CATSCAN_CANARY_WORKFLOW_MIN_CONFIDENCE:-}" ]]; then
  args+=("--workflow-min-confidence" "$CATSCAN_CANARY_WORKFLOW_MIN_CONFIDENCE")
fi

if [[ -n "${CATSCAN_CANARY_WORKFLOW_MAX_DELTA_PCT:-}" ]]; then
  args+=("--workflow-max-delta-pct" "$CATSCAN_CANARY_WORKFLOW_MAX_DELTA_PCT")
fi

if [[ "${CATSCAN_ALLOW_NO_ACTIVE_MODEL:-0}" == "1" ]]; then
  args+=("--allow-no-active-model")
fi

if [[ "${CATSCAN_CANARY_REQUIRE_HEALTHY_READINESS:-0}" == "1" ]]; then
  args+=("--require-healthy-readiness")
fi

if [[ -n "${CATSCAN_MAX_DIMENSION_MISSING_PCT:-}" ]]; then
  args+=("--max-dimension-missing-pct" "$CATSCAN_MAX_DIMENSION_MISSING_PCT")
fi

if [[ -n "${CATSCAN_ROLLBACK_BILLING_ID:-}" ]]; then
  args+=("--billing-id" "$CATSCAN_ROLLBACK_BILLING_ID")
fi

if [[ -n "${CATSCAN_ROLLBACK_SNAPSHOT_ID:-}" ]]; then
  args+=("--snapshot-id" "$CATSCAN_ROLLBACK_SNAPSHOT_ID")
fi

exec python3 "$ROOT_DIR/scripts/v1_canary_smoke.py" "${args[@]}" "$@"
