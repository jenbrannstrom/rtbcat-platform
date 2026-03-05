#!/usr/bin/env bash
set -euo pipefail

REPO="${CATSCAN_GH_REPO:-YOUR_ORG/rtbcat-platform}"
BRANCH="${CATSCAN_GH_REF:-unified-platform}"
DEPLOYED_WORKFLOW="${CATSCAN_DEPLOYED_WORKFLOW:-v1-closeout-deployed.yml}"
BYOM_WORKFLOW="${CATSCAN_BYOM_WORKFLOW:-v1-byom-api-regression.yml}"
LIMIT="${CATSCAN_AUDIT_LIMIT:-20}"
OUT_PATH=""
INCLUDE_LOG_SNIPPETS=0

usage() {
  cat <<'EOF'
Usage:
  scripts/audit_v1_closeout_remote.sh [options]

Options:
  --repo <owner/repo>         GitHub repo (default: YOUR_ORG/rtbcat-platform)
  --branch <name>             Branch to inspect (default: unified-platform)
  --limit <n>                 Max runs per workflow (default: 20)
  --out <path>                Output markdown file path (default: /tmp/v1_closeout_remote_audit_<ts>.md)
  --include-log-snippets      Include short FAIL/BLOCKED snippets from workflow logs
  -h, --help                  Show this help

Examples:
  scripts/audit_v1_closeout_remote.sh
  scripts/audit_v1_closeout_remote.sh --branch unified-platform --limit 30
  scripts/audit_v1_closeout_remote.sh --include-log-snippets
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --branch)
      BRANCH="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --out)
      OUT_PATH="${2:-}"
      shift 2
      ;;
    --include-log-snippets)
      INCLUDE_LOG_SNIPPETS=1
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

if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || (( LIMIT < 1 || LIMIT > 100 )); then
  echo "Invalid --limit value: ${LIMIT} (expected integer 1..100)" >&2
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
  echo "GitHub CLI auth is not ready. Run: gh auth login -h github.com" >&2
  exit 2
fi

ts="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -z "$OUT_PATH" ]]; then
  OUT_PATH="/tmp/v1_closeout_remote_audit_${ts}.md"
fi

tmp_root="$(mktemp -d /tmp/v1-closeout-audit.XXXXXX)"
trap 'rm -rf "$tmp_root"' EXIT

deployed_runs_json="${tmp_root}/deployed_runs.json"
byom_runs_json="${tmp_root}/byom_runs.json"

gh run list \
  --repo "$REPO" \
  --workflow "$DEPLOYED_WORKFLOW" \
  --branch "$BRANCH" \
  --limit "$LIMIT" \
  --json databaseId,displayTitle,headSha,status,conclusion,createdAt,updatedAt,url \
  > "$deployed_runs_json"

gh run list \
  --repo "$REPO" \
  --workflow "$BYOM_WORKFLOW" \
  --branch "$BRANCH" \
  --limit "$LIMIT" \
  --json databaseId,displayTitle,headSha,status,conclusion,createdAt,updatedAt,url \
  > "$byom_runs_json"

{
  echo "# V1 Closeout Remote Audit"
  echo
  echo "- generated_utc: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
  echo "- repo: \`${REPO}\`"
  echo "- branch: \`${BRANCH}\`"
  echo "- deployed_workflow: \`${DEPLOYED_WORKFLOW}\`"
  echo "- byom_workflow: \`${BYOM_WORKFLOW}\`"
  echo "- limit_per_workflow: \`${LIMIT}\`"
  echo
  echo "## Deployed Closeout Runs"
  echo
  echo "| run_id | conclusion | created_at | head_sha | profile | allow_blocked | go/no-go | qps_slo | pass/fail/blocked | artifact |"
  echo "|---|---|---|---|---|---|---|---|---|---|"

  while IFS= read -r row; do
    run_id="$(jq -r '.databaseId' <<<"$row")"
    conclusion="$(jq -r '.conclusion // "unknown"' <<<"$row")"
    created_at="$(jq -r '.createdAt // ""' <<<"$row")"
    head_sha="$(jq -r '.headSha // ""' <<<"$row" | cut -c1-7)"
    url="$(jq -r '.url // ""' <<<"$row")"

    run_dir="${tmp_root}/run-${run_id}"
    mkdir -p "$run_dir"

    profile="n/a"
    allow_blocked="n/a"
    go_status="n/a"
    slo_status="n/a"
    counts="n/a"
    artifact_state="missing"
    log_snippet=""

    if gh run download "$run_id" --repo "$REPO" -n v1-closeout-deployed-report -D "$run_dir" >/dev/null 2>&1; then
      report_json="${run_dir}/v1_closeout_last_run.json"
      if [[ -f "$report_json" ]]; then
        artifact_state="ok"
        profile="$(jq -r '.profile // "n/a"' "$report_json")"
        allow_blocked="$(jq -r 'if has("allow_deployed_blocked") then (.allow_deployed_blocked|tostring) else "n/a" end' "$report_json")"
        go_status="$(jq -r '.steps[]? | select(.step=="Deployed canary go/no-go") | (.status + " (" + .notes + ")")' "$report_json" | head -n 1)"
        slo_status="$(jq -r '.steps[]? | select(.step=="Deployed QPS strict SLO canary") | (.status + " (" + .notes + ")")' "$report_json" | head -n 1)"
        if [[ -z "$go_status" ]]; then
          go_status="n/a"
        fi
        if [[ -z "$slo_status" ]]; then
          slo_status="n/a"
        fi
        pass_count="$(jq '[.steps[]? | select(.status=="PASS")] | length' "$report_json")"
        fail_count="$(jq '[.steps[]? | select(.status=="FAIL")] | length' "$report_json")"
        blocked_count="$(jq '[.steps[]? | select(.status=="BLOCKED")] | length' "$report_json")"
        counts="${pass_count}/${fail_count}/${blocked_count}"
      else
        artifact_state="downloaded_no_json"
      fi
    fi

    if [[ "$INCLUDE_LOG_SNIPPETS" == "1" ]]; then
      set +e
      log_snippet="$(
        gh run view "$run_id" --repo "$REPO" --log 2>/dev/null \
          | grep -E '^(FAIL|BLOCKED)[[:space:]]{2,}' \
          | head -n 3 \
          | sed 's/|/%7C/g'
      )"
      set -e
    fi

    safe_go="$(printf '%s' "$go_status" | sed 's/|/%7C/g')"
    safe_slo="$(printf '%s' "$slo_status" | sed 's/|/%7C/g')"
    echo "| [${run_id}](${url}) | ${conclusion} | ${created_at} | \`${head_sha}\` | ${profile} | ${allow_blocked} | ${safe_go} | ${safe_slo} | ${counts} | ${artifact_state} |"

    if [[ -n "$log_snippet" ]]; then
      echo ""
      echo "<details><summary>run ${run_id} log snippets</summary>"
      echo ""
      echo '```text'
      printf '%s\n' "$log_snippet"
      echo '```'
      echo ""
      echo "</details>"
      echo ""
    fi
  done < <(jq -c '.[]' "$deployed_runs_json")

  echo
  echo "## BYOM Regression Runs"
  echo
  echo "| run_id | conclusion | created_at | head_sha | title |"
  echo "|---|---|---|---|---|"

  while IFS= read -r row; do
    run_id="$(jq -r '.databaseId' <<<"$row")"
    conclusion="$(jq -r '.conclusion // "unknown"' <<<"$row")"
    created_at="$(jq -r '.createdAt // ""' <<<"$row")"
    head_sha="$(jq -r '.headSha // ""' <<<"$row" | cut -c1-7)"
    title="$(jq -r '.displayTitle // ""' <<<"$row" | sed 's/|/%7C/g')"
    url="$(jq -r '.url // ""' <<<"$row")"
    echo "| [${run_id}](${url}) | ${conclusion} | ${created_at} | \`${head_sha}\` | ${title} |"
  done < <(jq -c '.[]' "$byom_runs_json")

  echo
  echo "## Local Commit Snapshot"
  echo
  echo '```text'
  git log --oneline -n 12
  echo '```'
} > "$OUT_PATH"

echo "Wrote audit report: $OUT_PATH"
echo
echo "Preview:"
sed -n '1,80p' "$OUT_PATH"
