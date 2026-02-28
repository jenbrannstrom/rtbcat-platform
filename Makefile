.PHONY: help v1-canary-smoke v1-canary-workflow v1-canary-lifecycle v1-canary-safe v1-canary-balanced v1-canary-aggressive phase0-regression phase0-dashboard-build phase0-gate

help:
	@echo "Targets:"
	@echo "  make v1-canary-smoke     # Run canary smoke wrapper (env-driven)"
	@echo "  make v1-canary-workflow  # Run canary with score+propose workflow gate"
	@echo "  make v1-canary-lifecycle # Run canary with workflow + proposal lifecycle gate"
	@echo "  make v1-canary-safe      # Run workflow canary with safe preset"
	@echo "  make v1-canary-balanced  # Run workflow canary with balanced preset"
	@echo "  make v1-canary-aggressive # Run workflow canary with aggressive preset"
	@echo "  make phase0-regression   # Run core Phase 0 regression tests"
	@echo "  make phase0-dashboard-build  # Build dashboard production bundle"
	@echo "  make phase0-gate         # Run regression tests + dashboard build"
	@echo "Env presets: CATSCAN_CANARY_PROFILE=safe|balanced|aggressive"

v1-canary-smoke:
	bash scripts/run_v1_canary_smoke.sh

v1-canary-workflow:
	CATSCAN_CANARY_RUN_WORKFLOW=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-lifecycle:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_RUN_LIFECYCLE=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-safe:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_PROFILE=safe bash scripts/run_v1_canary_smoke.sh

v1-canary-balanced:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_PROFILE=balanced bash scripts/run_v1_canary_smoke.sh

v1-canary-aggressive:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_PROFILE=aggressive bash scripts/run_v1_canary_smoke.sh

phase0-regression:
	pytest -q \
	  tests/test_v1_canary_smoke.py \
	  tests/test_import_foundation_contracts.py \
	  tests/test_data_health_service.py \
	  tests/test_system_data_health_api.py

phase0-dashboard-build:
	npm --prefix dashboard run build -- --webpack

phase0-gate: phase0-regression phase0-dashboard-build
