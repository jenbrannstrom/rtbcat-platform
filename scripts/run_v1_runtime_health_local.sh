#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_PATH="${CATSCAN_RUNTIME_HEALTH_REPORT_PATH:-/tmp/v1_runtime_health_last_run.md}"
REPORT_JSON_PATH="${CATSCAN_RUNTIME_HEALTH_REPORT_JSON_PATH:-/tmp/v1_runtime_health_last_run.json}"
CANARY_TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-240}"

STEP_NAMES=()
STEP_STATUSES=()
STEP_NOTES=()
HAS_FAIL=0
HAS_BLOCKED=0
REPORT_WRITTEN=0

record_step() {
  STEP_NAMES+=("$1")
  STEP_STATUSES+=("$2")
  STEP_NOTES+=("$3")
}

write_report() {
  if [[ "${REPORT_WRITTEN}" == "1" ]]; then
    return
  fi

  local timestamp branch commit
  timestamp="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
  commit="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"

  mkdir -p "$(dirname "$REPORT_PATH")"
  {
    echo "# V1 Runtime Health Strict (Last Run)"
    echo
    echo "- timestamp: \`${timestamp}\`"
    echo "- branch: \`${branch}\`"
    echo "- commit: \`${commit}\`"
    echo "- canary_timeout_seconds: \`${CANARY_TIMEOUT_SECONDS}\`"
    echo
    echo "| Step | Status | Notes |"
    echo "|---|---|---|"
    local i
    for i in "${!STEP_NAMES[@]}"; do
      echo "| ${STEP_NAMES[$i]} | ${STEP_STATUSES[$i]} | ${STEP_NOTES[$i]} |"
    done
  } > "$REPORT_PATH"

  python3 - "$REPORT_JSON_PATH" "$timestamp" "$branch" "$commit" "$CANARY_TIMEOUT_SECONDS" \
    "${STEP_NAMES[@]}" -- "${STEP_STATUSES[@]}" -- "${STEP_NOTES[@]}" <<'PY'
import json
import sys

args = sys.argv[1:]
out_path = args[0]
timestamp = args[1]
branch = args[2]
commit = args[3]
canary_timeout = args[4]

cursor = 5
names = []
while cursor < len(args) and args[cursor] != "--":
    names.append(args[cursor])
    cursor += 1
cursor += 1

statuses = []
while cursor < len(args) and args[cursor] != "--":
    statuses.append(args[cursor])
    cursor += 1
cursor += 1

notes = args[cursor:]
steps = []
for i, name in enumerate(names):
    steps.append(
        {
            "step": name,
            "status": statuses[i] if i < len(statuses) else "",
            "notes": notes[i] if i < len(notes) else "",
        }
    )

payload = {
    "timestamp_utc": timestamp,
    "branch": branch,
    "commit": commit,
    "canary_timeout_seconds": canary_timeout,
    "steps": steps,
}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, sort_keys=True)
    f.write("\n")
PY

  REPORT_WRITTEN=1
  echo "==> Wrote runtime health report: ${REPORT_PATH}"
  echo "==> Wrote runtime health report JSON: ${REPORT_JSON_PATH}"
}

on_exit() {
  write_report
}
trap on_exit EXIT

run_runtime_check() {
  local name="$1"
  local cmd="$2"

  echo "==> ${name}"
  set +e
  bash -lc "${cmd}"
  local status=$?
  set -e

  if [[ "${status}" -eq 0 ]]; then
    record_step "${name}" "PASS" "command succeeded"
    echo "==> ${name} (ok)"
    return
  fi

  if [[ "${status}" -eq 2 ]]; then
    HAS_BLOCKED=1
    record_step "${name}" "BLOCKED" "exit 2 (environment/data blocked)"
    echo "==> ${name} (blocked: environment/data)" >&2
    return
  fi

  HAS_FAIL=1
  record_step "${name}" "FAIL" "exit ${status}"
  echo "==> ${name} (failed: exit ${status})" >&2
}

run_runtime_check \
  "Deployed canary go/no-go" \
  "CATSCAN_CANARY_TIMEOUT_SECONDS=\${CATSCAN_CANARY_TIMEOUT_SECONDS:-240} \
CATSCAN_CANARY_DATA_HEALTH_DAYS=\${CATSCAN_CANARY_DATA_HEALTH_DAYS:-7} \
CATSCAN_CANARY_OPTIMIZER_ECONOMICS_DAYS=\${CATSCAN_CANARY_OPTIMIZER_ECONOMICS_DAYS:-7} \
CATSCAN_CANARY_RUN_WORKFLOW=1 \
CATSCAN_CANARY_RUN_LIFECYCLE=1 \
CATSCAN_CANARY_REQUIRE_HEALTHY_READINESS=1 \
CATSCAN_CANARY_REQUIRE_CONVERSION_READY=1 \
bash scripts/run_v1_canary_smoke.sh"

run_runtime_check \
  "Deployed QPS strict SLO canary" \
  "CATSCAN_CANARY_TIMEOUT_SECONDS=\${CATSCAN_CANARY_TIMEOUT_SECONDS:-45} \
CATSCAN_CANARY_RUN_QPS_PAGE_SLO=1 \
CATSCAN_CANARY_QPS_PAGE_SLO_SINCE_HOURS=\${CATSCAN_CANARY_QPS_PAGE_SLO_SINCE_HOURS:-24} \
CATSCAN_CANARY_QPS_PAGE_SLO_MIN_SAMPLES=\${CATSCAN_CANARY_QPS_PAGE_SLO_MIN_SAMPLES:-1} \
CATSCAN_CANARY_MAX_QPS_PAGE_P95_FIRST_ROW_MS=\${CATSCAN_CANARY_MAX_QPS_PAGE_P95_FIRST_ROW_MS:-6000} \
CATSCAN_CANARY_MAX_QPS_PAGE_P95_HYDRATED_MS=\${CATSCAN_CANARY_MAX_QPS_PAGE_P95_HYDRATED_MS:-8000} \
CATSCAN_CANARY_QPS_PAGE_REQUIRE_API_ROLLUP=1 \
bash scripts/run_v1_canary_smoke.sh"

if [[ "${HAS_FAIL}" == "1" ]]; then
  echo "Runtime strict gate failed: at least one check returned FAIL."
  exit 1
fi

if [[ "${HAS_BLOCKED}" == "1" ]]; then
  echo "Runtime strict gate failed: checks are BLOCKED (environment/data)."
  exit 2
fi

echo "Runtime strict gate passed."
