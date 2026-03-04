#!/usr/bin/env bash
set -euo pipefail

REPO="${CATSCAN_GH_REPO:-jenbrannstrom/rtbcat-platform}"
WORKFLOW="${CATSCAN_RUNTIME_HEALTH_WORKFLOW_FILE:-v1-runtime-health-strict.yml}"
BRANCH="${CATSCAN_GH_REF:-unified-platform}"
BUYER_ID="${CATSCAN_BUYER_ID:-}"
WINDOW="${CATSCAN_RUNTIME_HEALTH_STABILITY_WINDOW:-3}"
LIMIT="${CATSCAN_RUNTIME_HEALTH_STABILITY_LIMIT:-20}"

usage() {
  cat <<'EOF'
Usage:
  scripts/check_v1_runtime_health_stability.sh [options]

Checks whether the most recent completed runtime-health strict runs are stable
(`conclusion=success`) for the selected branch/workflow.

Options:
  --repo <owner/repo>      GitHub repo (default: jenbrannstrom/rtbcat-platform)
  --workflow <file.yml>    Workflow file name (default: v1-runtime-health-strict.yml)
  --branch <name>          Branch/ref filter (default: unified-platform)
  --buyer-id <id>          Optional buyer filter via run title token `buyer=<id>`
  --window <n>             Required consecutive successful runs (default: 3)
  --limit <n>              Number of recent runs to inspect (default: 20)
  -h, --help               Show help

Exit codes:
  0 = stable
  1 = unstable
  2 = usage/config error
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --workflow)
      WORKFLOW="${2:-}"
      shift 2
      ;;
    --branch)
      BRANCH="${2:-}"
      shift 2
      ;;
    --buyer-id)
      BUYER_ID="${2:-}"
      shift 2
      ;;
    --window)
      WINDOW="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
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

if ! [[ "$WINDOW" =~ ^[0-9]+$ ]] || (( WINDOW < 1 || WINDOW > 20 )); then
  echo "--window must be an integer between 1 and 20." >&2
  exit 2
fi
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || (( LIMIT < WINDOW || LIMIT > 200 )); then
  echo "--limit must be an integer between --window and 200." >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "'gh' CLI is required." >&2
  exit 2
fi

run_json="$(mktemp)"
trap 'rm -f "$run_json"' EXIT

gh run list \
  --repo "$REPO" \
  --workflow "$WORKFLOW" \
  --branch "$BRANCH" \
  --limit "$LIMIT" \
  --json databaseId,displayTitle,status,conclusion,createdAt,updatedAt,url,headSha \
  > "$run_json"

python3 - "$run_json" "$WINDOW" "$BUYER_ID" <<'PY'
import json
import sys

path = sys.argv[1]
window = int(sys.argv[2])
buyer = (sys.argv[3] or "").strip()

with open(path, "r", encoding="utf-8") as f:
    runs = json.load(f)

completed = [r for r in runs if str(r.get("status") or "").lower() == "completed"]
if buyer:
    token = f"buyer={buyer}"
    completed = [r for r in completed if token in str(r.get("displayTitle") or "")]

print(f"workflow_runs_completed={len(completed)}")
if buyer:
    print(f"buyer_filter={buyer}")

if len(completed) < window:
    print(
        f"stability=UNSTABLE (need {window} completed run(s), found {len(completed)})"
    )
    sys.exit(1)

window_runs = completed[:window]
all_success = all(str(r.get("conclusion") or "").lower() == "success" for r in window_runs)
for idx, run in enumerate(window_runs, start=1):
    print(
        f"[{idx}] run_id={run.get('databaseId')} conclusion={run.get('conclusion')} "
        f"createdAt={run.get('createdAt')} headSha={run.get('headSha')} "
        f"url={run.get('url')}"
    )

if all_success:
    print(f"stability=STABLE (last {window} completed run(s) are success)")
    sys.exit(0)

print(f"stability=UNSTABLE (one or more of last {window} completed run(s) not success)")
sys.exit(1)
PY
