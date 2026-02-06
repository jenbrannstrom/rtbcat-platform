#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/catscan"
COMPOSE_FILE="docker-compose.gcp.yml"
DEPLOY_KEY="/home/catscan/.ssh/github_deploy_key"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Missing $APP_DIR. Run on VM2 with /opt/catscan checked out." >&2
  exit 1
fi

cd "$APP_DIR"

# Allow git to operate if repo ownership differs (common on VM2).
git config --global --add safe.directory "$APP_DIR" >/dev/null 2>&1 || true

# Pull latest code using deploy key.
sudo -u catscan GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git pull

SHORT_SHA=$(sudo -u catscan git rev-parse --short HEAD)
IMAGE_TAG="sha-${SHORT_SHA}"

if [[ -f .env ]]; then
  if grep -q '^IMAGE_TAG=' .env; then
    sudo -u catscan sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${IMAGE_TAG}/" .env
  else
    printf "\nIMAGE_TAG=%s\n" "$IMAGE_TAG" | sudo -u catscan tee -a .env >/dev/null
  fi
else
  printf "IMAGE_TAG=%s\n" "$IMAGE_TAG" | sudo -u catscan tee .env >/dev/null
fi

# Build and restart containers (full stack).
sudo docker compose -f "$COMPOSE_FILE" up -d --build
sudo docker compose -f "$COMPOSE_FILE" restart cloudsql-proxy api dashboard

# Show status.
sudo docker compose -f "$COMPOSE_FILE" ps
