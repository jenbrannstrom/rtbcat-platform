#!/usr/bin/env bash
set -euo pipefail

RUN_ID=""
REPO="${CATSCAN_GH_REPO:-jenbrannstrom/rtbcat-platform}"
OUT_ROOT="${CATSCAN_RUNTIME_HEALTH_ARTIFACT_ROOT:-/tmp}"
WORKFLOW_ARTIFACT_NAME="${CATSCAN_RUNTIME_HEALTH_ARTIFACT_NAME:-v1-runtime-health-strict-report}"
SHOW_FULL_LOG=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/fetch_v1_runtime_health_run_evidence.sh --run-id <id> [options]

Fetches runtime-health strict evidence for a GitHub Actions run:
1) Run metadata
2) Artifact download (v1_runtime_health_last_run.json/.md)
3) Step summary from JSON
4) PASS/FAIL/BLOCKED lines extracted from full logs

Options:
  --run-id <id>           Required GitHub Actions run ID
  --repo <owner/repo>     Repo (default: jenbrannstrom/rtbcat-platform)
  --out-root <dir>        Output root (default: /tmp)
  --artifact <name>       Artifact name (default: v1-runtime-health-strict-report)
  --full-log              Print full log path and tail
  -h, --help              Show help

Examples:
  scripts/fetch_v1_runtime_health_run_evidence.sh --run-id 22647382211
  scripts/fetch_v1_runtime_health_run_evidence.sh --run-id 22647382211 --full-log
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id)
      RUN_ID="${2:-}"
      shift 2
      ;;
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --out-root)
      OUT_ROOT="${2:-}"
      shift 2
      ;;
    --artifact)
      WORKFLOW_ARTIFACT_NAME="${2:-}"
      shift 2
      ;;
    --full-log)
      SHOW_FULL_LOG=1
      shift
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

if [[ -z "$RUN_ID" ]]; then
  echo "--run-id is required." >&2
  usage
  exit 2
fi
if ! [[ "$RUN_ID" =~ ^[0-9]+$ ]]; then
  echo "--run-id must be numeric." >&2
  exit 2
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "'gh' CLI is required." >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "'jq' is required." >&2
  exit 2
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI auth not ready. Run: gh auth login -h github.com" >&2
  exit 2
fi

OUT_DIR="${OUT_ROOT%/}/v1-runtime-health-${RUN_ID}"
LOG_FILE="${OUT_DIR}/run.log"
STATUS_FILE="${OUT_DIR}/status_lines.txt"
REPORT_JSON="${OUT_DIR}/v1_runtime_health_last_run.json"
REPORT_MD="${OUT_DIR}/v1_runtime_health_last_run.md"

# Avoid gh artifact unzip collisions when re-running against the same RUN_ID.
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

echo "Repo: ${REPO}"
echo "Run:  ${RUN_ID}"
echo "Out:  ${OUT_DIR}"
echo

echo "== Run metadata =="
gh run view "$RUN_ID" --repo "$REPO" \
  --json displayTitle,workflowName,status,conclusion,createdAt,updatedAt,url,headSha \
  --jq '"workflow=\(.workflowName // "")\ntitle=\(.displayTitle // "")\nstatus=\(.status // "")\nconclusion=\(.conclusion // "")\ncreatedAt=\(.createdAt // "")\nupdatedAt=\(.updatedAt // "")\nheadSha=\(.headSha // "")\nurl=\(.url // "")"'
echo

echo "== Artifact download =="
set +e
gh run download "$RUN_ID" --repo "$REPO" -n "$WORKFLOW_ARTIFACT_NAME" -D "$OUT_DIR"
download_status=$?
set -e
if [[ "$download_status" -ne 0 ]]; then
  echo "artifact_download=missing_or_failed (name=${WORKFLOW_ARTIFACT_NAME})"
else
  echo "artifact_download=ok"
fi

if [[ -f "$REPORT_JSON" ]]; then
  echo "report_json=${REPORT_JSON}"
  echo "report_md=${REPORT_MD}"
  echo
  echo "== Runtime-health steps =="
  jq -r '
    .steps // []
    | if length == 0 then
        "no_steps_found"
      else
        .[] | "- " + (.step // "unknown") + ": " + (.status // "unknown") + " (" + (.notes // "") + ")"
      end
  ' "$REPORT_JSON"
else
  echo "report_json=missing"
fi
echo

echo "== Log extraction =="
set +e
gh run view "$RUN_ID" --repo "$REPO" --log > "$LOG_FILE"
log_status=$?
set -e
if [[ "$log_status" -ne 0 ]]; then
  echo "log_fetch=failed"
  exit 0
fi

grep -E 'PASS[[:space:]]{2,}|FAIL[[:space:]]{2,}|BLOCKED[[:space:]]{2,}' "$LOG_FILE" \
  | sed -E 's/^.*(PASS[[:space:]]{2,}|FAIL[[:space:]]{2,}|BLOCKED[[:space:]]{2,})/\1/' \
  > "$STATUS_FILE" || true
if [[ -s "$STATUS_FILE" ]]; then
  cat "$STATUS_FILE"
else
  echo "no PASS/FAIL/BLOCKED lines found in logs"
fi

if [[ "$SHOW_FULL_LOG" == "1" ]]; then
  echo
  echo "full_log=${LOG_FILE}"
  echo
  echo "== Log tail (last 80 lines) =="
  tail -n 80 "$LOG_FILE"
fi
