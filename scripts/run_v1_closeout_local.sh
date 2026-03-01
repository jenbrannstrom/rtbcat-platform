#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_PATH="${CATSCAN_CLOSEOUT_REPORT_PATH:-/tmp/v1_closeout_last_run.md}"
REPORT_JSON_PATH="${CATSCAN_CLOSEOUT_REPORT_JSON_PATH:-/tmp/v1_closeout_last_run.json}"
RUN_DEPLOYED="${CATSCAN_CLOSEOUT_RUN_DEPLOYED:-0}"
ALLOW_DEPLOYED_BLOCKED="${CATSCAN_CLOSEOUT_ALLOW_DEPLOYED_BLOCKED:-1}"
CLOSEOUT_PROFILE="${CATSCAN_CLOSEOUT_PROFILE:-full}"

if [[ "${CLOSEOUT_PROFILE}" == "deployed_only" ]]; then
  RUN_DEPLOYED=1
fi

STEP_NAMES=()
STEP_STATUSES=()
STEP_NOTES=()
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
  local timestamp
  local branch
  local commit
  timestamp="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
  commit="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"

  mkdir -p "$(dirname "$REPORT_PATH")"
  {
    echo "# V1 Closeout Last Run"
    echo
    echo "- timestamp: ${timestamp}"
    echo "- branch: \`${branch}\`"
    echo "- commit: \`${commit}\`"
    echo "- run_deployed: \`${RUN_DEPLOYED}\`"
    echo "- allow_deployed_blocked: \`${ALLOW_DEPLOYED_BLOCKED}\`"
    echo "- profile: \`${CLOSEOUT_PROFILE}\`"
    echo
    echo "| Step | Status | Notes |"
    echo "|---|---|---|"
    local i
    for i in "${!STEP_NAMES[@]}"; do
      echo "| ${STEP_NAMES[$i]} | ${STEP_STATUSES[$i]} | ${STEP_NOTES[$i]} |"
    done
  } > "$REPORT_PATH"

  python3 - "$REPORT_JSON_PATH" "$timestamp" "$branch" "$commit" "$RUN_DEPLOYED" "$ALLOW_DEPLOYED_BLOCKED" "$CLOSEOUT_PROFILE" \
    "${STEP_NAMES[@]}" -- "${STEP_STATUSES[@]}" -- "${STEP_NOTES[@]}" <<'PY'
import json
import sys

args = sys.argv[1:]
out_path = args[0]
timestamp = args[1]
branch = args[2]
commit = args[3]
run_deployed = args[4]
allow_blocked = args[5]
profile = args[6]

cursor = 7
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
    step = {
        "step": name,
        "status": statuses[i] if i < len(statuses) else "",
        "notes": notes[i] if i < len(notes) else "",
    }
    steps.append(step)

payload = {
    "timestamp_utc": timestamp,
    "branch": branch,
    "commit": commit,
    "run_deployed": run_deployed == "1",
    "allow_deployed_blocked": allow_blocked == "1",
    "profile": profile,
    "steps": steps,
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, sort_keys=True)
    f.write("\n")
PY

  REPORT_WRITTEN=1
  echo "==> Wrote closeout report: ${REPORT_PATH}"
  echo "==> Wrote closeout report JSON: ${REPORT_JSON_PATH}"
}

on_exit() {
  write_report
}

trap on_exit EXIT

run_step() {
  local name="$1"
  shift
  echo "==> ${name}"
  set +e
  "$@"
  local status=$?
  set -e
  if [[ ${status} -eq 0 ]]; then
    record_step "${name}" "PASS" "command succeeded"
    echo "==> ${name} (ok)"
    return 0
  fi
  record_step "${name}" "FAIL" "exit ${status}"
  echo "==> ${name} (failed: exit ${status})" >&2
  return "${status}"
}

if [[ "${CLOSEOUT_PROFILE}" == "quick" ]]; then
  run_step "Phase 0 regression (quick profile)" make phase0-regression
  run_step "Conversion regression (quick profile)" make v1-conversion-regression
elif [[ "${CLOSEOUT_PROFILE}" == "full" ]]; then
  run_step "Core gate" make v1-gate
elif [[ "${CLOSEOUT_PROFILE}" == "deployed_only" ]]; then
  record_step "Local test suites" "SKIPPED" "profile=deployed_only (run deployed canaries only)"
  echo "==> Local test suites skipped (profile=deployed_only)."
else
  record_step "Closeout profile validation" "FAIL" "unsupported profile '${CLOSEOUT_PROFILE}'"
  echo "Unsupported CATSCAN_CLOSEOUT_PROFILE='${CLOSEOUT_PROFILE}' (expected full|quick|deployed_only)" >&2
  exit 2
fi

if [[ "${CLOSEOUT_PROFILE}" != "deployed_only" ]]; then
  run_step "Phase 4 targeted suites" \
    pytest -q \
      tests/test_system_ui_metrics_api.py \
      tests/test_pretargeting_repo_query_shapes.py \
      tests/test_pretargeting_service_cache.py \
      tests/test_endpoints_service_cache.py \
      tests/test_analytics_service_cache.py

  run_step "BYOM/optimizer service suites" \
    pytest -q \
      tests/test_optimizer_models_service.py \
      tests/test_optimizer_scoring_service.py \
      tests/test_optimizer_proposals_service.py \
      tests/test_optimizer_economics_service.py \
      tests/test_response_model_regressions.py

  run_step "Optimizer syntax compile checks" \
    python3 -m py_compile \
      api/routers/optimizer_models.py \
      api/routers/optimizer_scoring.py \
      api/routers/optimizer_proposals.py \
      api/routers/optimizer_workflows.py \
      api/routers/optimizer_economics.py \
      services/optimizer_models_service.py \
      services/optimizer_scoring_service.py \
      services/optimizer_proposals_service.py \
      services/optimizer_economics_service.py
fi

if [[ "${RUN_DEPLOYED}" == "1" ]]; then
  allow_blocked="${ALLOW_DEPLOYED_BLOCKED}"

  run_deployed_check() {
    local name="$1"
    local cmd="$2"

    if [[ "${allow_blocked}" != "1" ]]; then
      run_step "${name}" bash -lc "${cmd}"
      return
    fi

    echo "==> ${name}"
    set +e
    bash -lc "${cmd}"
    local status=$?
    set -e
    if [[ ${status} -eq 0 ]]; then
      record_step "${name}" "PASS" "command succeeded"
      echo "==> ${name} (ok)"
      return
    fi
    if [[ ${status} -eq 2 ]]; then
      record_step "${name}" "BLOCKED" "exit 2 (environment/network policy)"
      echo "==> ${name} (blocked: env/network policy)"
      return
    fi
    record_step "${name}" "FAIL" "exit ${status}"
    echo "==> ${name} (failed: exit ${status})" >&2
    exit "${status}"
  }

  run_deployed_check \
    "Deployed canary go/no-go" \
    "CATSCAN_CANARY_RUN_WORKFLOW=1 \
CATSCAN_CANARY_RUN_LIFECYCLE=1 \
CATSCAN_CANARY_REQUIRE_HEALTHY_READINESS=1 \
CATSCAN_CANARY_REQUIRE_CONVERSION_READY=1 \
bash scripts/run_v1_canary_smoke.sh"
  run_deployed_check \
    "Deployed QPS strict SLO canary" \
    "CATSCAN_CANARY_RUN_QPS_PAGE_SLO=1 \
CATSCAN_CANARY_QPS_PAGE_SLO_SINCE_HOURS=\${CATSCAN_CANARY_QPS_PAGE_SLO_SINCE_HOURS:-24} \
CATSCAN_CANARY_QPS_PAGE_SLO_MIN_SAMPLES=\${CATSCAN_CANARY_QPS_PAGE_SLO_MIN_SAMPLES:-1} \
CATSCAN_CANARY_MAX_QPS_PAGE_P95_FIRST_ROW_MS=\${CATSCAN_CANARY_MAX_QPS_PAGE_P95_FIRST_ROW_MS:-6000} \
CATSCAN_CANARY_MAX_QPS_PAGE_P95_HYDRATED_MS=\${CATSCAN_CANARY_MAX_QPS_PAGE_P95_HYDRATED_MS:-8000} \
CATSCAN_CANARY_QPS_PAGE_REQUIRE_API_ROLLUP=1 \
bash scripts/run_v1_canary_smoke.sh"
else
  record_step "Deployed canaries" "SKIPPED" "set CATSCAN_CLOSEOUT_RUN_DEPLOYED=1 to run"
  echo "==> Deployed canaries skipped (set CATSCAN_CLOSEOUT_RUN_DEPLOYED=1 to run)."
fi

echo "Local closeout checks complete."
