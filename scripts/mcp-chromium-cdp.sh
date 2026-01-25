#!/bin/bash
set -euo pipefail

# Attach MCP to an existing Chrome with remote debugging enabled.
CDP_ENDPOINT=""
attempts=0
while [ "${attempts}" -lt 50 ]; do
  if CDP_ENDPOINT="$(python3 - <<'PY' 2>/dev/null
import json, urllib.request
print(json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/version'))['webSocketDebuggerUrl'])
PY
)"; then
    break
  fi
  attempts=$((attempts + 1))
  sleep 0.2
done

if [ -z "${CDP_ENDPOINT}" ]; then
  echo "Failed to resolve CDP endpoint at http://127.0.0.1:9222/json/version" >&2
  exit 1
fi

exec npx -y @playwright/mcp --cdp-endpoint "${CDP_ENDPOINT}" --host 127.0.0.1 --port 8765
