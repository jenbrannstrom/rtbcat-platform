#!/usr/bin/env bash
set -euo pipefail

REPO="${CATSCAN_GH_REPO:-jenbrannstrom/rtbcat-platform}"
REF="${CATSCAN_GH_REF:-unified-platform}"
WORKFLOW="v1-runtime-health-strict.yml"

API_BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
BUYER_ID="${CATSCAN_BUYER_ID:-}"
MODEL_ID="${CATSCAN_MODEL_ID:-}"
CANARY_PROFILE="${CATSCAN_CANARY_PROFILE:-balanced}"
QPS_PAGE_SLO_SINCE_HOURS="${CATSCAN_CANARY_QPS_PAGE_SLO_SINCE_HOURS:-168}"
CANARY_TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-240}"
POLL_TIMEOUT_SECONDS="${CATSCAN_CLOSEOUT_POLL_TIMEOUT_SECONDS:-180}"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_v1_runtime_health_strict_dispatch.sh [options]

Options:
  --buyer-id <id>                 Buyer scope for runtime-health canary
  --api-base-url <url>            API base URL (default: https://scan.rtb.cat/api)
  --model-id <id>                 Optional model ID override
  --profile <safe|balanced|aggressive>
                                  Canary profile (default: balanced)
  --since-hours <n>               QPS page SLO lookback hours (default: 168)
  --canary-timeout <seconds>      Per-request canary HTTP timeout (default: 240)
  --repo <owner/repo>             GitHub repo (default: jenbrannstrom/rtbcat-platform)
  --ref <branch>                  Git ref/branch (default: unified-platform)
  --poll-timeout <seconds>        Wait for run registration (default: 180)
  -h, --help                      Show help

Example:
  scripts/run_v1_runtime_health_strict_dispatch.sh --buyer-id 1487810529 --profile balanced
EOF
}

get_latest_run_id() {
  gh run list \
    --repo "$REPO" \
    --workflow "$WORKFLOW" \
    --branch "$REF" \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId // ""' 2>/dev/null || true
}

wait_for_new_run_id() {
  local previous_id="$1"
  local deadline=$((SECONDS + POLL_TIMEOUT_SECONDS))
  local current_id=""
  while (( SECONDS < deadline )); do
    current_id="$(get_latest_run_id)"
    if [[ -n "$current_id" && "$current_id" != "$previous_id" ]]; then
      echo "$current_id"
      return 0
    fi
    sleep 3
  done
  echo "Timed out waiting for workflow run registration: ${WORKFLOW}" >&2
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buyer-id)
      BUYER_ID="${2:-}"
      shift 2
      ;;
    --api-base-url)
      API_BASE_URL="${2:-}"
      shift 2
      ;;
    --model-id)
      MODEL_ID="${2:-}"
      shift 2
      ;;
    --profile)
      CANARY_PROFILE="${2:-}"
      shift 2
      ;;
    --since-hours)
      QPS_PAGE_SLO_SINCE_HOURS="${2:-}"
      shift 2
      ;;
    --canary-timeout)
      CANARY_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --ref)
      REF="${2:-}"
      shift 2
      ;;
    --poll-timeout)
      POLL_TIMEOUT_SECONDS="${2:-}"
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

previous_run_id="$(get_latest_run_id)"

echo "Dispatching ${WORKFLOW} on ref=${REF} repo=${REPO}"
gh api "repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches" \
  -X POST \
  -f ref="$REF" \
  -f inputs[api_base_url]="$API_BASE_URL" \
  -f inputs[buyer_id]="$BUYER_ID" \
  -f inputs[model_id]="$MODEL_ID" \
  -f inputs[canary_profile]="$CANARY_PROFILE" \
  -f inputs[qps_page_slo_since_hours]="$QPS_PAGE_SLO_SINCE_HOURS" \
  -f inputs[canary_timeout_seconds]="$CANARY_TIMEOUT_SECONDS"

run_id="$(wait_for_new_run_id "$previous_run_id")"
echo "Detected runtime-health strict run: ${run_id}"
echo "Run URL: https://github.com/${REPO}/actions/runs/${run_id}"

gh run watch "$run_id" --repo "$REPO"
gh run view "$run_id" --repo "$REPO" --json url,workflowName,status,conclusion,createdAt,updatedAt,displayTitle \
  --jq '"Run summary:\n  workflow:   \(.workflowName // "")\n  title:      \(.displayTitle // "")\n  status:     \(.status // "")\n  conclusion: \(.conclusion // "")\n  createdAt:  \(.createdAt // "")\n  updatedAt:  \(.updatedAt // "")\n  url:        \(.url // "")"'

conclusion="$(gh run view "$run_id" --repo "$REPO" --json conclusion --jq '.conclusion // ""' 2>/dev/null || true)"

out_dir="/tmp/v1-runtime-health-${run_id}"
mkdir -p "$out_dir"
set +e
gh run download "$run_id" --repo "$REPO" -n v1-runtime-health-strict-report -D "$out_dir"
download_status=$?
set -e
if [[ "$download_status" -eq 0 ]]; then
  echo "Downloaded runtime-health artifact to: ${out_dir}"
  if [[ -f "${out_dir}/v1_runtime_health_last_run.json" ]]; then
    jq '.steps' "${out_dir}/v1_runtime_health_last_run.json"
  fi
else
  echo "Artifact download failed (run may still be in progress or report missing)." >&2
fi

if [[ "$conclusion" != "success" ]]; then
  echo "Runtime-health strict workflow failed (conclusion='${conclusion}')." >&2
  echo "Diagnostic helper: scripts/fetch_v1_runtime_health_run_evidence.sh --run-id ${run_id} --full-log" >&2
  exit 1
fi
