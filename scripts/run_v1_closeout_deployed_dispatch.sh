#!/usr/bin/env bash
set -euo pipefail

REPO="${CATSCAN_GH_REPO:-jenbrannstrom/rtbcat-platform}"
REF="${CATSCAN_GH_REF:-unified-platform}"
DEPLOYED_WORKFLOW="v1-closeout-deployed.yml"
BYOM_WORKFLOW="v1-byom-api-regression.yml"

API_BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
BUYER_ID="${CATSCAN_BUYER_ID:-}"
MODEL_ID="${CATSCAN_MODEL_ID:-}"
CANARY_PROFILE="${CATSCAN_CANARY_PROFILE:-balanced}"
QPS_PAGE_SLO_SINCE_HOURS="${CATSCAN_CANARY_QPS_PAGE_SLO_SINCE_HOURS:-168}"
ALLOW_BLOCKED_RAW="${CATSCAN_CLOSEOUT_ALLOW_BLOCKED:-false}"

WATCH_RUN=1
DOWNLOAD_ARTIFACT=1
RUN_BYOM=0
POLL_TIMEOUT_SECONDS="${CATSCAN_CLOSEOUT_POLL_TIMEOUT_SECONDS:-180}"
ARTIFACT_ROOT="${CATSCAN_CLOSEOUT_ARTIFACT_ROOT:-/tmp}"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_v1_closeout_deployed_dispatch.sh [options]

Options:
  --buyer-id <id>                 Buyer scope for deployed closeout (recommended)
  --api-base-url <url>            API base URL (default: https://scan.rtb.cat/api)
  --model-id <id>                 Optional model ID override
  --profile <safe|balanced|aggressive>
                                  Canary profile (default: balanced)
  --since-hours <n>               QPS page SLO lookback hours (default: 168)
  --allow-blocked <true|false>    Treat blocked checks as non-fatal (default: false)
  --repo <owner/repo>             GitHub repo (default: jenbrannstrom/rtbcat-platform)
  --ref <branch>                  Git ref/branch (default: unified-platform)
  --poll-timeout <seconds>        Wait for run registration (default: 180)
  --run-byom                      Also dispatch/watch BYOM API regression workflow
  --no-watch                      Dispatch only (don't live-watch run)
  --no-download                   Skip artifact download
  --artifact-root <dir>           Root dir for downloaded artifacts (default: /tmp)
  -h, --help                      Show this help

Examples:
  scripts/run_v1_closeout_deployed_dispatch.sh --buyer-id 1487810529
  scripts/run_v1_closeout_deployed_dispatch.sh --buyer-id 1487810529 --run-byom
EOF
}

lower() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

normalize_bool() {
  local raw
  raw="$(lower "${1:-}")"
  case "$raw" in
    1|true|yes|y) echo "true" ;;
    0|false|no|n|"") echo "false" ;;
    *)
      echo "Invalid boolean value: ${1}. Expected true|false." >&2
      exit 2
      ;;
  esac
}

get_latest_run_id() {
  local workflow="$1"
  gh run list \
    --repo "$REPO" \
    --workflow "$workflow" \
    --branch "$REF" \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId // ""' 2>/dev/null || true
}

wait_for_new_run_id() {
  local workflow="$1"
  local previous_id="$2"
  local deadline=$((SECONDS + POLL_TIMEOUT_SECONDS))
  local current_id=""
  while (( SECONDS < deadline )); do
    current_id="$(get_latest_run_id "$workflow")"
    if [[ -n "$current_id" && "$current_id" != "$previous_id" ]]; then
      echo "$current_id"
      return 0
    fi
    sleep 3
  done
  echo "Timed out waiting for workflow run registration: ${workflow}" >&2
  return 1
}

print_run_summary() {
  local run_id="$1"
  gh run view \
    "$run_id" \
    --repo "$REPO" \
    --json url,workflowName,status,conclusion,createdAt,updatedAt,displayTitle \
    --jq '"Run summary:\n  workflow:   \(.workflowName // "")\n  title:      \(.displayTitle // "")\n  status:     \(.status // "")\n  conclusion: \(.conclusion // "")\n  createdAt:  \(.createdAt // "")\n  updatedAt:  \(.updatedAt // "")\n  url:        \(.url // "")"'
}

get_run_conclusion() {
  local run_id="$1"
  gh run view "$run_id" --repo "$REPO" --json conclusion --jq '.conclusion // ""'
}

download_deployed_artifact() {
  local run_id="$1"
  local out_dir="${ARTIFACT_ROOT%/}/v1-closeout-${run_id}"
  mkdir -p "$out_dir"
  gh run download \
    "$run_id" \
    --repo "$REPO" \
    -n v1-closeout-deployed-report \
    -D "$out_dir"
  echo "Downloaded deployed closeout artifact to: ${out_dir}"

  local report_json="${out_dir}/v1_closeout_last_run.json"
  if [[ -f "$report_json" ]]; then
    python3 - "$report_json" <<'PY'
import json
import sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    payload = json.load(f)
print(f"Closeout report: {path}")
print(f"  profile: {payload.get('profile')}")
for step in payload.get("steps", []):
    name = str(step.get("step", "")).strip()
    status = str(step.get("status", "")).strip()
    notes = str(step.get("notes", "")).strip()
    print(f"  - {name}: {status} ({notes})")
PY
  fi
}

dispatch_deployed_workflow() {
  local previous_run_id
  previous_run_id="$(get_latest_run_id "$DEPLOYED_WORKFLOW")"

  echo "Dispatching ${DEPLOYED_WORKFLOW} on ref=${REF} repo=${REPO}"
  gh api "repos/${REPO}/actions/workflows/${DEPLOYED_WORKFLOW}/dispatches" \
    -X POST \
    -f ref="$REF" \
    -f inputs[api_base_url]="$API_BASE_URL" \
    -f inputs[buyer_id]="$BUYER_ID" \
    -f inputs[model_id]="$MODEL_ID" \
    -f inputs[canary_profile]="$CANARY_PROFILE" \
    -f inputs[qps_page_slo_since_hours]="$QPS_PAGE_SLO_SINCE_HOURS" \
    -f inputs[allow_blocked]="$ALLOW_BLOCKED"

  local run_id
  run_id="$(wait_for_new_run_id "$DEPLOYED_WORKFLOW" "$previous_run_id")"
  echo "Detected deployed closeout run: ${run_id}"
  echo "Run URL: https://github.com/${REPO}/actions/runs/${run_id}"

  if [[ "$WATCH_RUN" == "1" ]]; then
    set +e
    gh run watch "$run_id" --repo "$REPO"
    local watch_status=$?
    set -e
    if [[ "$watch_status" -ne 0 ]]; then
      echo "Warning: gh run watch returned ${watch_status}; continuing with run summary." >&2
    fi
  fi

  print_run_summary "$run_id"
  local conclusion
  conclusion="$(get_run_conclusion "$run_id")"

  if [[ "$DOWNLOAD_ARTIFACT" == "1" ]]; then
    if [[ "$conclusion" == "success" ]]; then
      set +e
      download_deployed_artifact "$run_id"
      local artifact_status=$?
      set -e
      if [[ "$artifact_status" -ne 0 ]]; then
        echo "Warning: artifact download failed with exit ${artifact_status}." >&2
      fi
    else
      echo "Skipping artifact download because run conclusion='${conclusion}'." >&2
    fi
  fi

  if [[ "$conclusion" != "success" ]]; then
    echo "Deployed closeout workflow failed (conclusion='${conclusion}')." >&2
    echo "Common cause: missing repo secrets CATSCAN_CANARY_BEARER_TOKEN or CATSCAN_CANARY_SESSION_COOKIE." >&2
    return 1
  fi
}

dispatch_byom_workflow() {
  local previous_run_id
  previous_run_id="$(get_latest_run_id "$BYOM_WORKFLOW")"

  echo "Dispatching ${BYOM_WORKFLOW} on ref=${REF} repo=${REPO}"
  gh api "repos/${REPO}/actions/workflows/${BYOM_WORKFLOW}/dispatches" \
    -X POST \
    -f ref="$REF"

  local run_id
  run_id="$(wait_for_new_run_id "$BYOM_WORKFLOW" "$previous_run_id")"
  echo "Detected BYOM regression run: ${run_id}"
  echo "Run URL: https://github.com/${REPO}/actions/runs/${run_id}"

  if [[ "$WATCH_RUN" == "1" ]]; then
    set +e
    gh run watch "$run_id" --repo "$REPO"
    local watch_status=$?
    set -e
    if [[ "$watch_status" -ne 0 ]]; then
      echo "Warning: gh run watch returned ${watch_status}; continuing with run summary." >&2
    fi
  fi

  print_run_summary "$run_id"
  local conclusion
  conclusion="$(get_run_conclusion "$run_id")"
  if [[ "$conclusion" != "success" ]]; then
    echo "BYOM workflow failed (conclusion='${conclusion}')." >&2
    return 1
  fi
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
    --allow-blocked)
      ALLOW_BLOCKED_RAW="${2:-}"
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
    --run-byom)
      RUN_BYOM=1
      shift
      ;;
    --no-watch)
      WATCH_RUN=0
      shift
      ;;
    --no-download)
      DOWNLOAD_ARTIFACT=0
      shift
      ;;
    --artifact-root)
      ARTIFACT_ROOT="${2:-}"
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

ALLOW_BLOCKED="$(normalize_bool "$ALLOW_BLOCKED_RAW")"

case "$(lower "$CANARY_PROFILE")" in
  safe|balanced|aggressive) ;;
  *)
    echo "Invalid --profile value: ${CANARY_PROFILE} (expected safe|balanced|aggressive)" >&2
    exit 2
    ;;
esac

if ! [[ "$QPS_PAGE_SLO_SINCE_HOURS" =~ ^[0-9]+$ ]] || (( QPS_PAGE_SLO_SINCE_HOURS < 1 || QPS_PAGE_SLO_SINCE_HOURS > 168 )); then
  echo "Invalid --since-hours value: ${QPS_PAGE_SLO_SINCE_HOURS} (expected integer 1..168)" >&2
  exit 2
fi

if ! [[ "$POLL_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( POLL_TIMEOUT_SECONDS < 15 )); then
  echo "Invalid --poll-timeout value: ${POLL_TIMEOUT_SECONDS} (expected integer >=15)" >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "'gh' CLI is required. Install GitHub CLI first." >&2
  exit 2
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI auth is not ready. Run: gh auth login -h github.com" >&2
  exit 2
fi

dispatch_deployed_workflow

if [[ "$RUN_BYOM" == "1" ]]; then
  dispatch_byom_workflow
fi
