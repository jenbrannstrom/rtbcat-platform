#!/usr/bin/env bash
set -euo pipefail

# Keep Chrome running with remote debugging enabled.
CHROME_BIN="/usr/bin/google-chrome"
PROFILE_DIR="/home/x1-7/.catscan/chrome-profile"
URL="https://your-deployment.example.com"

while true; do
  if curl -sf http://127.0.0.1:9222/json/version >/dev/null; then
    sleep 5
    continue
  fi

  "${CHROME_BIN}" \
    --remote-debugging-port=9222 \
    --user-data-dir="${PROFILE_DIR}" \
    --no-first-run \
    --no-default-browser-check \
    "${URL}" || true

  sleep 5
done
