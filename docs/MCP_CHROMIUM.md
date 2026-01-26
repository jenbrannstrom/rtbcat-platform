# MCP Chromium (Playwright) Setup

This project expects MCP tooling to be external to the app. The Chromium MCP server is used
for browser-based inspection (e.g., rendering creatives for OCR or screenshots).

## Quick start (noob-friendly)

Goal: run a local MCP server and point your MCP client (Codex CLI) at it so the assistant can control Chrome.

1) Start the MCP server (from the repo root):
```bash
cd /home/x1-7/Documents/rtbcat-platform
./scripts/mcp-chromium-cdp.sh
```
This attaches to an existing Chrome with remote debugging enabled and serves MCP at:
`http://127.0.0.1:8765/mcp`

2) If you see “Failed to resolve CDP endpoint”, start Chrome with debugging:
```bash
google-chrome --remote-debugging-port=9222
```
Then rerun `./scripts/mcp-chromium-cdp.sh`.

3) Point your MCP client (Codex CLI) to the local server.
Add this to your Codex config (exact path varies by setup):
```json
{
  "mcpServers": {
    "chromium": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```
Restart Codex after editing the config.

If you're using Codex CLI, the config file is typically:
```
~/.codex/config.toml
```
Add this TOML block:
```toml
[mcpServers.chromium]
url = "http://127.0.0.1:8765/mcp"
```

If you see “Access is only allowed at localhost:8765” in the browser, that’s good —
it means the MCP server is running and waiting for the client to connect.

## Prerequisites
- Node.js 18+
- Chromium (Playwright will download a browser on first run)

## Start the MCP Chromium server
```bash
./scripts/mcp-chromium.sh
```

## MCP client configuration
Add a server entry in your MCP client configuration that points to the Playwright server.
Example JSON:

```json
{
  "mcpServers": {
    "chromium": {
      "command": "npx",
      "args": [
        "-y",
        "@playwright/mcp"
      ]
    }
  }
}
```

If your MCP client supports browser selection flags, pass them in `args`
(for example, `--browser=chromium`).

If `npx` reports a revoked/expired npm token, run `npm logout` or `npm login`
and retry.

## Persistent (SSE) server
When running the service in SSE mode, configure your client with a URL:

```json
{
  "mcpServers": {
    "chromium": {
      "url": "http://localhost:8765/mcp"
    }
  }
}
```
