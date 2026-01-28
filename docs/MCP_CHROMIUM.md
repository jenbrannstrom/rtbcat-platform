# MCP Chromium (Playwright) Setup

This project expects MCP tooling to be external to the app. The Chromium MCP server is used
for browser-based inspection (e.g., rendering creatives for OCR or screenshots).

## Quick start (current, stable)

Goal: run a local MCP server and point your MCP client (Codex CLI) at it so the assistant can control Chrome.

1) Start Chrome with CDP (if not already running):
```bash
google-chrome --remote-debugging-port=9222
```

2) Start MCP server (from repo root):
```bash
cd /home/x1-7/Documents/rtbcat-platform
./scripts/mcp-chromium-cdp.sh
```

This attaches to the existing Chrome CDP endpoint and serves MCP at:
`http://localhost:8765/mcp`

**Important:** host allowlist rejects 127.0.0.1. Use `localhost`.

3) Point your MCP client to the local server.
For Codex CLI (TOML):
```toml
[mcpServers.chromium]
url = "http://localhost:8765/mcp"
```

Restart Codex after editing config.

## Deterministic bring-up checklist

1) CDP responds:
```bash
curl -s http://127.0.0.1:9222/json/version
```

2) Kill stale MCP:
```bash
pkill -f "@playwright/mcp" || true
pkill -f "playwright-mcp" || true
pkill -f "mcp --cdp-endpoint" || true
```

3) Start MCP (script uses `playwright-mcp` and allows all hosts):
```bash
./scripts/mcp-chromium-cdp.sh
```

4) Restart Codex CLI.

5) Validate by tool usage (e.g., screenshot). `list_mcp_resources` may be empty because MCP is tool-based.

## Notes
- Use `localhost`, not `127.0.0.1`, in client config.
- `scripts/mcp-chromium-cdp.sh` starts:
  `playwright-mcp --cdp-endpoint ... --host localhost --port 8765 --allowed-hosts "*"`
