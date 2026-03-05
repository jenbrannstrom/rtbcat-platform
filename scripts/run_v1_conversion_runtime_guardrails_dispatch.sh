#!/usr/bin/env bash
set -euo pipefail

REPO="${CATSCAN_GH_REPO:-jenbrannstrom/rtbcat-platform}"
REF="${CATSCAN_GH_REF:-unified-platform}"
WORKFLOW="v1-conversion-runtime-guardrails.yml"

API_BASE_URL="${CATSCAN_API_BASE_URL:-https://your-deployment.example.com/api}"
STRICT_SECURITY="${CATSCAN_GUARDRAIL_STRICT_SECURITY:-true}"
RUN_RETENTION="${CATSCAN_GUARDRAIL_RUN_RETENTION:-true}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-60}"
POLL_TIMEOUT_SECONDS="${CATSCAN_CLOSEOUT_POLL_TIMEOUT_SECONDS:-180}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_v1_conversion_runtime_guardrails_dispatch.sh [options]

Dispatches v1-conversion-runtime-guardrails workflow, waits for completion,
and downloads artifact when available.

Options:
  --api-base-url <url>      API base URL (default: https://your-deployment.example.com/api)
  --strict-security <bool>  true|false (default: true)
  --run-retention <bool>    true|false (default: true)
  --timeout <seconds>       Per-request timeout for API checks (default: 60)
  --repo <owner/repo>       GitHub repo (default: jenbrannstrom/rtbcat-platform)
  --ref <branch>            Git ref/branch (default: unified-platform)
  --poll-timeout <seconds>  Wait for run registration (default: 180)
  -h, --help                Show help

Example:
  scripts/run_v1_conversion_runtime_guardrails_dispatch.sh --strict-security true
USAGE
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
    --api-base-url)
      API_BASE_URL="${2:-}"
      shift 2
      ;;
    --strict-security)
      STRICT_SECURITY="${2:-}"
      shift 2
      ;;
    --run-retention)
      RUN_RETENTION="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
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

if [[ "$STRICT_SECURITY" != "true" && "$STRICT_SECURITY" != "false" ]]; then
  echo "--strict-security must be true|false" >&2
  exit 2
fi
if [[ "$RUN_RETENTION" != "true" && "$RUN_RETENTION" != "false" ]]; then
  echo "--run-retention must be true|false" >&2
  exit 2
fi
if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 5 || TIMEOUT_SECONDS > 600 )); then
  echo "--timeout must be an integer in [5, 600]" >&2
  exit 2
fi

previous_run_id="$(get_latest_run_id)"

echo "Dispatching ${WORKFLOW} on ref=${REF} repo=${REPO}"
gh api "repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches" \
  -X POST \
  -f ref="$REF" \
  -f inputs[api_base_url]="$API_BASE_URL" \
  -f inputs[strict_security]="$STRICT_SECURITY" \
  -f inputs[run_retention]="$RUN_RETENTION" \
  -f inputs[timeout_seconds]="$TIMEOUT_SECONDS"

run_id="$(wait_for_new_run_id "$previous_run_id")"
echo "Detected conversion runtime guardrail run: ${run_id}"
echo "Run URL: https://github.com/${REPO}/actions/runs/${run_id}"

set +e
gh run watch "$run_id" --repo "$REPO"
watch_status=$?
set -e
if [[ "$watch_status" -ne 0 ]]; then
  echo "Warning: gh run watch returned ${watch_status}; continuing with run summary." >&2
fi

gh run view "$run_id" --repo "$REPO" --json url,workflowName,status,conclusion,createdAt,updatedAt,displayTitle \
  --jq '"Run summary:\n  workflow:   \(.workflowName // \"\")\n  title:      \(.displayTitle // \"\")\n  status:     \(.status // \"\")\n  conclusion: \(.conclusion // \"\")\n  createdAt:  \(.createdAt // \"\")\n  updatedAt:  \(.updatedAt // \"\")\n  url:        \(.url // \"\")"'

out_dir="/tmp/v1-conversion-runtime-guardrails-${run_id}"
mkdir -p "$out_dir"
set +e
gh run download "$run_id" --repo "$REPO" -n v1-conversion-runtime-guardrails-report -D "$out_dir"
download_status=$?
set -e
if [[ "$download_status" -eq 0 ]]; then
  echo "Downloaded guardrail artifact to: ${out_dir}"
  if [[ -f "${out_dir}/guardrail_report.md" ]]; then
    echo "Guardrail report: ${out_dir}/guardrail_report.md"
    sed -n '1,120p' "${out_dir}/guardrail_report.md"
  fi
else
  echo "Artifact download failed (run may still be in progress or report missing)." >&2
fi
