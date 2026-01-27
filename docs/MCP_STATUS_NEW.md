# MCP Status (Jan 27, 2026)

This file is for the *new* Codex instance after restart.

## What was done
- Started a new MCP server bound to 127.0.0.1:8766 attached to the existing Chrome CDP.
- Updated Codex config to point to it.

## Current config
- `/home/x1-7/.codex/config.toml`:
  - `mcpServers.chromium.url = "http://127.0.0.1:8766/mcp"`

## How it was started
- Command (run in this repo):
  - `CDP_ENDPOINT=$(python3 - <<'PY'
import json, urllib.request
print(json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/version'))['webSocketDebuggerUrl'])
PY
)
nohup npx -y @playwright/mcp --cdp-endpoint "$CDP_ENDPOINT" --host 127.0.0.1 --port 8766 > /tmp/mcp-8766.log 2>&1 &`

## Verify
- `ss -ltnp | rg 8766` should show a node listener.
- Log: `/tmp/mcp-8766.log`

## Next step for new instance
- Restart Codex CLI, then run `list_mcp_resources`.
