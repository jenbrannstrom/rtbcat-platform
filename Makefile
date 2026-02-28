.PHONY: help v1-canary-smoke v1-canary-workflow v1-canary-lifecycle phase0-regression phase0-dashboard-build phase0-gate

help:
	@echo "Targets:"
	@echo "  make v1-canary-smoke     # Run canary smoke wrapper (env-driven)"
	@echo "  make v1-canary-workflow  # Run canary with score+propose workflow gate"
	@echo "  make v1-canary-lifecycle # Run canary with workflow + proposal lifecycle gate"
	@echo "  make phase0-regression   # Run core Phase 0 regression tests"
	@echo "  make phase0-dashboard-build  # Build dashboard production bundle"
	@echo "  make phase0-gate         # Run regression tests + dashboard build"

v1-canary-smoke:
	bash scripts/run_v1_canary_smoke.sh

v1-canary-workflow:
	CATSCAN_CANARY_RUN_WORKFLOW=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-lifecycle:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_RUN_LIFECYCLE=1 bash scripts/run_v1_canary_smoke.sh

phase0-regression:
	pytest -q \
	  tests/test_v1_canary_smoke.py \
	  tests/test_import_foundation_contracts.py \
	  tests/test_data_health_service.py \
	  tests/test_system_data_health_api.py

phase0-dashboard-build:
	npm --prefix dashboard run build -- --webpack

phase0-gate: phase0-regression phase0-dashboard-build
