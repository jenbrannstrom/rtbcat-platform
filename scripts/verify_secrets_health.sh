#!/usr/bin/env bash
# verify_secrets_health.sh — Deterministic secrets-health verifier for deploy pipelines.
#
# Exit codes:
#   0 — healthy (all required secrets for enabled features are present)
#   2 — probe unavailable (container unreachable or health check could not run)
#   3 — unhealthy (one or more required secrets missing for enabled features)
#
# This script runs INSIDE the VM (not from a GitHub runner) and invokes the
# secrets-health check directly inside the container, bypassing HTTP auth
# entirely.  This eliminates the false-negative instability caused by endpoint
# auth requirements and network timeouts.
#
# Usage:
#   scripts/verify_secrets_health.sh [--container NAME] [--strict] [--json-out PATH]
#
# The --strict flag is informational only (printed in output).  The CALLER
# (deploy.yml) decides whether to hard-fail based on SECRETS_HEALTH_STRICT.
#
# SECURITY: This script never prints secret values.  Only key names and
# boolean configured/missing status are shown.
set -euo pipefail

CONTAINER_NAME="${VERIFY_SECRETS_CONTAINER:-catscan-api}"
STRICT_MODE=""
JSON_OUT=""

usage() {
  cat <<'EOF'
Usage: scripts/verify_secrets_health.sh [options]

Options:
  --container NAME   Docker container name (default: catscan-api)
  --strict           Mark output as strict-mode (informational)
  --json-out PATH    Write raw JSON to file
  -h, --help         Show help

Exit codes:
  0  healthy
  2  probe unavailable
  3  unhealthy
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --container) CONTAINER_NAME="${2:-}"; shift 2 ;;
    --strict)    STRICT_MODE="true"; shift ;;
    --json-out)  JSON_OUT="${2:-}"; shift 2 ;;
    -h|--help)   usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

# ---------------------------------------------------------------------------
# Probe: run secrets-health check inside the container
# ---------------------------------------------------------------------------
PROBE_JSON=""

if ! docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo "PROBE_UNAVAILABLE: container '${CONTAINER_NAME}' not found"
  exit 2
fi

CONTAINER_STATUS="$(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || true)"
if [[ "$CONTAINER_STATUS" != "running" ]]; then
  echo "PROBE_UNAVAILABLE: container '${CONTAINER_NAME}' status is '${CONTAINER_STATUS}'"
  exit 2
fi

# Execute the health check inside the container.  Use python3 (the venv
# python) to import the service and dump JSON.  This avoids any HTTP auth
# or network dependency.
PROBE_JSON="$(docker exec "$CONTAINER_NAME" python3 -c '
import json
from services.secrets_health_service import get_secrets_health
print(json.dumps(get_secrets_health()))
' 2>&1)" || {
  echo "PROBE_UNAVAILABLE: in-container health check failed"
  echo "  detail: ${PROBE_JSON}"
  exit 2
}

# Validate we got parseable JSON
if ! echo "$PROBE_JSON" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
  echo "PROBE_UNAVAILABLE: container returned non-JSON output"
  exit 2
fi

# ---------------------------------------------------------------------------
# Write JSON artifact if requested
# ---------------------------------------------------------------------------
if [[ -n "$JSON_OUT" ]]; then
  echo "$PROBE_JSON" > "$JSON_OUT"
fi

# ---------------------------------------------------------------------------
# Parse and report (never print secret values)
# ---------------------------------------------------------------------------
_PROBE_JSON="$PROBE_JSON" _STRICT_FLAG="${STRICT_MODE:-false}" python3 <<'PARSE_EOF'
import json, os, sys

payload = json.loads(os.environ["_PROBE_JSON"])
strict_flag = os.environ.get("_STRICT_FLAG", "false")

healthy = payload.get("healthy", False)
summary = payload.get("summary", {})
missing = payload.get("missing_required_keys", [])

print(f"secrets_health_healthy={healthy}")
print(f"secrets_health_strict_mode={payload.get('strict_mode', False)}")
print(f"secrets_health_backend={payload.get('backend', 'unknown')}")
print(f"secrets_health_enabled_features={summary.get('enabled_features', 0)}")
print(f"secrets_health_required_keys={summary.get('required_keys', 0)}")
print(f"secrets_health_configured_keys={summary.get('configured_keys', 0)}")
print(f"secrets_health_missing_keys_count={summary.get('missing_keys', 0)}")

if missing:
    # Print key NAMES only (not values) — safe for logs
    print(f"secrets_health_missing_keys={','.join(missing)}")

if strict_flag == "true":
    print(f"verify_strict_flag={strict_flag}")

if healthy:
    print("HEALTHY: all required secrets for enabled features are present")
    sys.exit(0)
else:
    print(f"UNHEALTHY: missing required secrets: {', '.join(missing)}")
    sys.exit(3)
PARSE_EOF
