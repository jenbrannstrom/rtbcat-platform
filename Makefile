.PHONY: help v1-canary-smoke v1-canary-workflow v1-canary-lifecycle v1-canary-go-no-go v1-canary-conversion-ready v1-canary-pixel v1-canary-webhook-auth v1-canary-webhook-hmac v1-canary-webhook-freshness v1-canary-webhook-rate-limit v1-canary-webhook-security-status v1-canary-webhook-security v1-canary-safe v1-canary-balanced v1-canary-aggressive v1-conversion-regression v1-gate phase0-regression phase0-dashboard-build phase0-gate

help:
	@echo "Targets:"
	@echo "  make v1-canary-smoke     # Run canary smoke wrapper (env-driven)"
	@echo "  make v1-canary-workflow  # Run canary with score+propose workflow gate"
	@echo "  make v1-canary-lifecycle # Run canary with workflow + proposal lifecycle gate"
	@echo "  make v1-canary-go-no-go  # Strict go/no-go canary profile"
	@echo "  make v1-canary-conversion-ready # Require conversion readiness=ready"
	@echo "  make v1-canary-pixel     # Run canary with conversion pixel gate"
	@echo "  make v1-canary-webhook-auth # Run canary with conversion webhook auth gate"
	@echo "  make v1-canary-webhook-hmac # Run canary with conversion webhook HMAC gate"
	@echo "  make v1-canary-webhook-freshness # Run canary with conversion webhook freshness gate"
	@echo "  make v1-canary-webhook-rate-limit # Run canary with conversion webhook rate-limit gate"
	@echo "  make v1-canary-webhook-security-status # Run canary with webhook security-status gate"
	@echo "  make v1-canary-webhook-security # Run bundled webhook security gate suite"
	@echo "  make v1-canary-safe      # Run workflow canary with safe preset"
	@echo "  make v1-canary-balanced  # Run workflow canary with balanced preset"
	@echo "  make v1-canary-aggressive # Run workflow canary with aggressive preset"
	@echo "  make v1-conversion-regression # Run conversion/readiness regression tests"
	@echo "  make v1-gate             # Run phase0 gate + conversion regression"
	@echo "  make phase0-regression   # Run core Phase 0 regression tests"
	@echo "  make phase0-dashboard-build  # Build dashboard production bundle"
	@echo "  make phase0-gate         # Run regression tests + dashboard build"
	@echo "Env presets: CATSCAN_CANARY_PROFILE=safe|balanced|aggressive, CATSCAN_CANARY_RUN_PIXEL=1, CATSCAN_CANARY_REQUIRE_CONVERSION_READY=1, CATSCAN_CANARY_RUN_WEBHOOK_AUTH=1, CATSCAN_CANARY_RUN_WEBHOOK_HMAC=1"

v1-canary-smoke:
	bash scripts/run_v1_canary_smoke.sh

v1-canary-workflow:
	CATSCAN_CANARY_RUN_WORKFLOW=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-lifecycle:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_RUN_LIFECYCLE=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-go-no-go:
	CATSCAN_CANARY_RUN_WORKFLOW=1 \
	CATSCAN_CANARY_RUN_LIFECYCLE=1 \
	CATSCAN_CANARY_REQUIRE_HEALTHY_READINESS=1 \
	CATSCAN_CANARY_REQUIRE_CONVERSION_READY=1 \
	bash scripts/run_v1_canary_smoke.sh

v1-canary-conversion-ready:
	CATSCAN_CANARY_REQUIRE_CONVERSION_READY=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-pixel:
	CATSCAN_CANARY_RUN_PIXEL=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-webhook-auth:
	CATSCAN_CANARY_RUN_WEBHOOK_AUTH=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-webhook-hmac:
	CATSCAN_CANARY_RUN_WEBHOOK_HMAC=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-webhook-freshness:
	CATSCAN_CANARY_RUN_WEBHOOK_FRESHNESS=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-webhook-rate-limit:
	CATSCAN_CANARY_RUN_WEBHOOK_RATE_LIMIT=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-webhook-security-status:
	CATSCAN_CANARY_RUN_WEBHOOK_SECURITY_STATUS=1 bash scripts/run_v1_canary_smoke.sh

v1-canary-webhook-security:
	CATSCAN_CANARY_RUN_WEBHOOK_AUTH=1 \
	CATSCAN_CANARY_RUN_WEBHOOK_HMAC=1 \
	CATSCAN_CANARY_RUN_WEBHOOK_FRESHNESS=1 \
	CATSCAN_CANARY_RUN_WEBHOOK_RATE_LIMIT=1 \
	CATSCAN_CANARY_RUN_WEBHOOK_SECURITY_STATUS=1 \
	CATSCAN_CANARY_WEBHOOK_RATE_LIMIT_PER_WINDOW=$${CATSCAN_CANARY_WEBHOOK_RATE_LIMIT_PER_WINDOW:-1} \
	CATSCAN_CANARY_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS=$${CATSCAN_CANARY_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS:-60} \
	CATSCAN_CANARY_MIN_SECURED_WEBHOOK_SOURCES=$${CATSCAN_CANARY_MIN_SECURED_WEBHOOK_SOURCES:-1} \
	bash scripts/run_v1_canary_smoke.sh

v1-canary-safe:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_PROFILE=safe bash scripts/run_v1_canary_smoke.sh

v1-canary-balanced:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_PROFILE=balanced bash scripts/run_v1_canary_smoke.sh

v1-canary-aggressive:
	CATSCAN_CANARY_RUN_WORKFLOW=1 CATSCAN_CANARY_PROFILE=aggressive bash scripts/run_v1_canary_smoke.sh

v1-conversion-regression:
	pytest -q \
	  tests/test_conversion_readiness.py \
	  tests/test_conversions_service.py \
	  tests/test_conversions_api.py \
	  tests/test_conversion_ingestion_service.py \
	  tests/test_conversion_connector_fixtures.py \
	  tests/test_v1_canary_smoke.py

phase0-regression:
	pytest -q \
	  tests/test_v1_canary_smoke.py \
	  tests/test_import_foundation_contracts.py \
	  tests/test_data_health_service.py \
	  tests/test_system_data_health_api.py

phase0-dashboard-build:
	npm --prefix dashboard run build -- --webpack

phase0-gate: phase0-regression phase0-dashboard-build

v1-gate: phase0-gate v1-conversion-regression
