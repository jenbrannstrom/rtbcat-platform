# MCP Chromium (Playwright) Setup

This project expects MCP tooling to be external to the app. The Chromium MCP server is used
for browser-based inspection (e.g., rendering creatives for OCR or screenshots).

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
