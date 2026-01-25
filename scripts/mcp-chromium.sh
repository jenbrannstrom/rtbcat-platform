#!/usr/bin/env bash
set -euo pipefail

# Launch the MCP Playwright server (Chromium via Playwright).
# Pass through any CLI flags (for example: --port, --headless, --browser).
npx -y @playwright/mcp "$@"
