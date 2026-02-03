#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/catscan"
COMPOSE_FILE="docker-compose.gcp.yml"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Missing $APP_DIR. Run on VM2 with /opt/catscan checked out." >&2
  exit 1
fi

cd "$APP_DIR"

# Allow git to operate if repo ownership differs (common on VM2).
git config --global --add safe.directory "$APP_DIR" >/dev/null 2>&1 || true

git pull

SHORT_SHA=$(git rev-parse --short HEAD)
IMAGE_TAG="sha-${SHORT_SHA}"

if [[ -f .env ]]; then
  if grep -q '^IMAGE_TAG=' .env; then
    sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${IMAGE_TAG}/" .env
  else
    printf "\nIMAGE_TAG=%s\n" "$IMAGE_TAG" >> .env
  fi
else
  printf "IMAGE_TAG=%s\n" "$IMAGE_TAG" > .env
fi

# Build and restart containers with new tag/version
if command -v sudo >/dev/null 2>&1; then
  sudo docker compose -f "$COMPOSE_FILE" up -d --build api dashboard
else
  docker compose -f "$COMPOSE_FILE" up -d --build api dashboard
fi

# Show deployed version
curl -s http://127.0.0.1:8000/health | python - <<'PY'
import json,sys
print(json.dumps(json.load(sys.stdin), indent=2))
PY
