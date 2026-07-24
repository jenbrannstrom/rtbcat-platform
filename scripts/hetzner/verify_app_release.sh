#!/usr/bin/env bash
# Verify the digest-pinned Part 3 shadow deployment without changing it.

set -euo pipefail

RELEASE_FILE=""
WITH_GOOGLE="false"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/verify_app_release.sh \
  --release-file <digest-release.env> [--with-google]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-file) RELEASE_FILE="${2:?missing release file}"; shift 2 ;;
    --with-google) WITH_GOOGLE="true"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root on the Hetzner app host." >&2
  exit 1
fi
if [[ ! -f "$RELEASE_FILE" ]]; then
  echo "Release file is required." >&2
  exit 1
fi

release_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; found=1; exit} END {if (!found) exit 1}' "$RELEASE_FILE"
}

release_sha="$(release_value RELEASE_GIT_SHA)"
api_image="$(release_value API_IMAGE)"
dashboard_image="$(release_value DASHBOARD_IMAGE)"

for container in rtbcat-api rtbcat-dashboard; do
  if [[ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true)" != "true" ]]; then
    echo "Container is not running: ${container}." >&2
    exit 1
  fi
done

actual_api_image="$(docker inspect --format '{{.Config.Image}}' rtbcat-api)"
actual_dashboard_image="$(docker inspect --format '{{.Config.Image}}' rtbcat-dashboard)"
if [[ "$actual_api_image" != "$api_image" || "$actual_dashboard_image" != "$dashboard_image" ]]; then
  echo "Running container image references do not match the approved digests." >&2
  exit 1
fi
if ! docker inspect rtbcat-api | jq -e \
  '.[0].HostConfig.PortBindings["8000/tcp"] == [{"HostIp":"127.0.0.1","HostPort":"8000"}]' \
  >/dev/null; then
  echo "API Docker port binding is not exactly 127.0.0.1:8000." >&2
  exit 1
fi
if ! docker inspect rtbcat-dashboard | jq -e \
  '.[0].HostConfig.PortBindings["3000/tcp"] == [{"HostIp":"127.0.0.1","HostPort":"3000"}]' \
  >/dev/null; then
  echo "Dashboard Docker port binding is not exactly 127.0.0.1:3000." >&2
  exit 1
fi

health_file="$(mktemp)"
cleanup() {
  rm -f -- "$health_file"
}
trap cleanup EXIT
curl -fsS --max-time 10 http://127.0.0.1:8000/health > "$health_file"
if ! jq -e --arg sha "$release_sha" \
  '.status == "healthy" and .database_exists == true and .git_sha == $sha' \
  "$health_file" >/dev/null; then
  echo "API health, database state, or release SHA does not match." >&2
  jq '{status, database_exists, version, git_sha}' "$health_file" >&2
  exit 1
fi
curl -fsS --max-time 10 http://127.0.0.1:3000/login >/dev/null

container_env="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' rtbcat-api)"
for scheduler_flag in \
  CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER \
  CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER \
  CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER; do
  if ! grep -qx "${scheduler_flag}=false" <<<"$container_env"; then
    echo "Shadow scheduler guard is not false: ${scheduler_flag}." >&2
    exit 1
  fi
done
if ! grep -qx 'CATSCAN_READ_ONLY_SHADOW=true' <<<"$container_env"; then
  echo "Shadow API is missing CATSCAN_READ_ONLY_SHADOW=true." >&2
  exit 1
fi
mutation_status="$(
  curl -sS --max-time 10 -o /dev/null -w '%{http_code}' \
    -X POST http://127.0.0.1:8000/seats/populate
)"
if [[ "$mutation_status" != "405" ]]; then
  echo "Read-only shadow mutation guard returned HTTP ${mutation_status}, expected 405." >&2
  exit 1
fi

bad_listener="$(ss -ltnH | awk '$4 ~ /:3000$/ || $4 ~ /:8000$/ {if ($4 !~ /^127\.0\.0\.1:/) print $4}')"
if [[ -n "$bad_listener" ]]; then
  echo "API/dashboard has a non-loopback listener: ${bad_listener}." >&2
  exit 1
fi
if ss -ltnH | awk '$4 ~ /:5432$/ {found=1} END {exit !found}'; then
  echo "The app host unexpectedly listens on PostgreSQL port 5432." >&2
  exit 1
fi

if [[ "$WITH_GOOGLE" == "true" ]]; then
  docker exec rtbcat-api \
    python /app/scripts/hetzner/verify_google_access.py
fi

echo "Part 3 shadow release verified: digest pins, database, Google access, scheduler guards, and loopback-only listeners are healthy."
