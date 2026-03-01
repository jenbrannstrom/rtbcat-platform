#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_PATH="${CATSCAN_CLOSEOUT_REPORT_PATH:-/tmp/v1_closeout_last_run.md}"
RUN_DEPLOYED="${CATSCAN_CLOSEOUT_RUN_DEPLOYED:-0}"
ALLOW_DEPLOYED_BLOCKED="${CATSCAN_CLOSEOUT_ALLOW_DEPLOYED_BLOCKED:-1}"
CLOSEOUT_PROFILE="${CATSCAN_CLOSEOUT_PROFILE:-full}"

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
  REPORT_WRITTEN=1
  echo "==> Wrote closeout report: ${REPORT_PATH}"
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
else
  record_step "Closeout profile validation" "FAIL" "unsupported profile '${CLOSEOUT_PROFILE}'"
  echo "Unsupported CATSCAN_CLOSEOUT_PROFILE='${CLOSEOUT_PROFILE}' (expected full|quick)" >&2
  exit 2
fi
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

  run_deployed_check "Deployed canary go/no-go" "make v1-canary-go-no-go"
  run_deployed_check "Deployed QPS strict SLO canary" "make v1-canary-qps-page-slo-strict"
else
  record_step "Deployed canaries" "SKIPPED" "set CATSCAN_CLOSEOUT_RUN_DEPLOYED=1 to run"
  echo "==> Deployed canaries skipped (set CATSCAN_CLOSEOUT_RUN_DEPLOYED=1 to run)."
fi

echo "Local closeout checks complete."
