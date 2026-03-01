#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_step() {
  local name="$1"
  shift
  echo "==> ${name}"
  "$@"
  echo "==> ${name} (ok)"
}

run_step "Core gate" make v1-gate

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

if [[ "${CATSCAN_CLOSEOUT_RUN_DEPLOYED:-0}" == "1" ]]; then
  run_step "Deployed canary go/no-go" make v1-canary-go-no-go
  run_step "Deployed QPS strict SLO canary" make v1-canary-qps-page-slo-strict
else
  echo "==> Deployed canaries skipped (set CATSCAN_CLOSEOUT_RUN_DEPLOYED=1 to run)."
fi

echo "Local closeout checks complete."
