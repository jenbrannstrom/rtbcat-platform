#!/usr/bin/env bash
# Pull and start one exact digest-pinned release on the Hetzner shadow app host.
# This script never updates DNS and refuses to enable schedulers.

set -euo pipefail

RELEASE_FILE=""
COMPOSE_FILE=""
CONFIRM=""
DOCKER_CONFIG_DIR="/etc/rtbcat/docker"
MARKER_FILE="/etc/rtbcat/app-host.env"
RUNTIME_MARKER="/etc/rtbcat/app-runtime-installed.env"
RUNTIME_ENV_FILE="/etc/rtbcat/runtime.env"
POSTGRES_PASSWORD_FILE="/etc/rtbcat/secrets/postgres-password"
POSTGRES_CA_FILE="/etc/rtbcat/secrets/postgres-ca.crt"
GOOGLE_CREDENTIALS_FILE="/etc/rtbcat/secrets/google-adc.json"
DATA_DIR="/var/lib/rtbcat/app-data"
RELEASE_DIR="/var/lib/rtbcat/releases"
CONTAINER_UID=10001
CONTAINER_GID=10001
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_SCRIPT="${SCRIPT_DIR}/verify_app_release.sh"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/deploy_app_release.sh \
  --release-file <hetzner-release.env> \
  [--compose-file <hetzner-compose.yml>] \
  --confirm deploy-shadow-no-dns

By default, hetzner-compose.yml is read beside the release file or from the
archived release. This does not alter DNS or the GCP source.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-file) RELEASE_FILE="${2:?missing release file}"; shift 2 ;;
    --compose-file) COMPOSE_FILE="${2:?missing Compose file}"; shift 2 ;;
    --confirm) CONFIRM="${2:?missing confirmation}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root on the Hetzner app host." >&2
  exit 1
fi
if [[ "$CONFIRM" != "deploy-shadow-no-dns" ]]; then
  echo "Exact shadow-deploy confirmation is required." >&2
  exit 1
fi
for required_path in \
  "$RELEASE_FILE" "$MARKER_FILE" "$RUNTIME_MARKER" "$RUNTIME_ENV_FILE" \
  "$POSTGRES_PASSWORD_FILE" "$POSTGRES_CA_FILE" "$GOOGLE_CREDENTIALS_FILE" \
  "$VERIFY_SCRIPT"; do
  if [[ ! -f "$required_path" ]]; then
    echo "Missing required file: ${required_path}." >&2
    exit 1
  fi
done

# shellcheck source=/dev/null
source "$MARKER_FILE"
if [[ -z "${RTBCAT_DATABASE_PRIVATE_IP:-}" || -z "${RTBCAT_DATABASE_NAME:-}" || -z "${RTBCAT_DATABASE_OWNER:-}" ]]; then
  echo "App-host marker is incomplete." >&2
  exit 1
fi

check_runtime_secret() {
  local path="$1"
  if [[ "$(stat -c '%u' "$path")" != "0" || \
        "$(stat -c '%g' "$path")" != "$CONTAINER_GID" || \
        "$(stat -c '%a' "$path")" != "440" ]]; then
    echo "Runtime secret must be root:${CONTAINER_GID} mode 0440: ${path}." >&2
    exit 1
  fi
}
check_runtime_secret "$POSTGRES_PASSWORD_FILE"
check_runtime_secret "$POSTGRES_CA_FILE"
check_runtime_secret "$GOOGLE_CREDENTIALS_FILE"
if [[ "$(stat -c '%u:%a' "$RUNTIME_ENV_FILE")" != "0:600" ]]; then
  echo "Runtime env must be root-owned mode 0600." >&2
  exit 1
fi
for scheduler_flag in \
  CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER \
  CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER \
  CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER; do
  if ! grep -qx "${scheduler_flag}=false" "$RUNTIME_ENV_FILE"; then
    echo "Refusing dual scheduler ownership: ${scheduler_flag} is not false." >&2
    exit 1
  fi
done

release_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; found=1; exit} END {if (!found) exit 1}' "$RELEASE_FILE"
}
RELEASE_GIT_SHA="$(release_value RELEASE_GIT_SHA)"
RELEASE_VERSION="$(release_value RELEASE_VERSION)"
DEPLOY_COMPOSE_SHA256="$(release_value DEPLOY_COMPOSE_SHA256)"
API_IMAGE="$(release_value API_IMAGE)"
DASHBOARD_IMAGE="$(release_value DASHBOARD_IMAGE)"
if ! [[ "$RELEASE_GIT_SHA" =~ ^[a-f0-9]{40}$ ]] || \
   ! [[ "$RELEASE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || \
   ! [[ "$DEPLOY_COMPOSE_SHA256" =~ ^[a-f0-9]{64}$ ]]; then
  echo "Release SHA or version is malformed." >&2
  exit 1
fi
if ! [[ "$API_IMAGE" =~ ^ghcr\.io/[a-z0-9._-]+/catscan-api@sha256:[a-f0-9]{64}$ ]] || \
   ! [[ "$DASHBOARD_IMAGE" =~ ^ghcr\.io/[a-z0-9._-]+/catscan-dashboard@sha256:[a-f0-9]{64}$ ]]; then
  echo "Only the expected GHCR repositories with sha256 digests are accepted." >&2
  exit 1
fi

install -d -o root -g root -m 0755 "$RELEASE_DIR"
approved_release="${RELEASE_DIR}/release-${RELEASE_GIT_SHA}.env"
approved_compose="${RELEASE_DIR}/compose-${RELEASE_GIT_SHA}.yml"
if [[ -z "$COMPOSE_FILE" ]]; then
  artifact_compose="$(dirname "$RELEASE_FILE")/hetzner-compose.yml"
  if [[ -f "$artifact_compose" ]]; then
    COMPOSE_FILE="$artifact_compose"
  elif [[ -f "$approved_compose" ]]; then
    COMPOSE_FILE="$approved_compose"
  else
    echo "No release-matched Compose file is available." >&2
    exit 1
  fi
fi
if [[ ! -f "$COMPOSE_FILE" ]] || \
   [[ "$(sha256sum "$COMPOSE_FILE" | awk '{print $1}')" != "$DEPLOY_COMPOSE_SHA256" ]]; then
  echo "Compose file does not match the approved release commit." >&2
  exit 1
fi
if [[ -f "$approved_release" ]] && ! cmp -s "$RELEASE_FILE" "$approved_release"; then
  echo "A different manifest already exists for this commit." >&2
  exit 1
fi
if [[ -f "$approved_compose" ]] && ! cmp -s "$COMPOSE_FILE" "$approved_compose"; then
  echo "A different Compose file already exists for this commit." >&2
  exit 1
fi
if [[ ! -f "$approved_release" ]]; then
  install -o root -g root -m 0644 "$RELEASE_FILE" "$approved_release"
fi
if [[ ! -f "$approved_compose" ]]; then
  install -o root -g root -m 0644 "$COMPOSE_FILE" "$approved_compose"
fi
COMPOSE_FILE="$approved_compose"

openssl x509 -in "$POSTGRES_CA_FILE" -noout >/dev/null
if ! timeout 10 openssl s_client \
  -starttls postgres \
  -connect "${RTBCAT_DATABASE_PRIVATE_IP}:5432" \
  -CAfile "$POSTGRES_CA_FILE" \
  -verify_ip "$RTBCAT_DATABASE_PRIVATE_IP" \
  -verify_return_error \
  </dev/null >/dev/null 2>&1; then
  echo "Private PostgreSQL TLS identity check failed." >&2
  exit 1
fi

docker_pull=(docker)
if [[ -f "$DOCKER_CONFIG_DIR/config.json" ]]; then
  if [[ "$(stat -c '%u:%a' "$DOCKER_CONFIG_DIR/config.json")" != "0:600" ]]; then
    echo "GHCR Docker config must be root-owned mode 0600." >&2
    exit 1
  fi
  docker_pull+=(--config "$DOCKER_CONFIG_DIR")
fi
"${docker_pull[@]}" pull "$API_IMAGE"
"${docker_pull[@]}" pull "$DASHBOARD_IMAGE"

for image_ref in "$API_IMAGE" "$DASHBOARD_IMAGE"; do
  revision="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$image_ref")"
  if [[ "$revision" != "$RELEASE_GIT_SHA" ]]; then
    echo "Image revision label does not match the approved commit." >&2
    exit 1
  fi
done
image_uid="$(docker run --rm --pull=never --entrypoint /usr/bin/id "$API_IMAGE" -u)"
image_gid="$(docker run --rm --pull=never --entrypoint /usr/bin/id "$API_IMAGE" -g)"
if [[ "$image_uid" != "$CONTAINER_UID" || "$image_gid" != "$CONTAINER_GID" ]]; then
  echo "API image runtime identity is not ${CONTAINER_UID}:${CONTAINER_GID}." >&2
  exit 1
fi

install -d -o "$CONTAINER_UID" -g "$CONTAINER_GID" -m 0750 "$DATA_DIR"
if [[ "$(stat -c '%u:%g' "$DATA_DIR")" != "${CONTAINER_UID}:${CONTAINER_GID}" ]]; then
  chown -R "${CONTAINER_UID}:${CONTAINER_GID}" "$DATA_DIR"
fi
export API_IMAGE DASHBOARD_IMAGE RELEASE_GIT_SHA RELEASE_VERSION
export RTBCAT_RUNTIME_ENV_FILE="$RUNTIME_ENV_FILE"
export RTBCAT_DB_AUTH_FILE="$POSTGRES_PASSWORD_FILE"
export RTBCAT_POSTGRES_CA_FILE="$POSTGRES_CA_FILE"
export RTBCAT_GOOGLE_CREDENTIALS_FILE="$GOOGLE_CREDENTIALS_FILE"
export RTBCAT_DATA_DIR="$DATA_DIR"
export RTBCAT_DATABASE_PRIVATE_IP RTBCAT_DATABASE_NAME RTBCAT_DATABASE_OWNER

rendered_images="$(docker compose --project-name rtbcat-hetzner -f "$COMPOSE_FILE" config --images)"
if ! grep -Fxq "$API_IMAGE" <<<"$rendered_images" || \
   ! grep -Fxq "$DASHBOARD_IMAGE" <<<"$rendered_images"; then
  echo "Rendered Compose images do not match the approved release." >&2
  exit 1
fi

if [[ "$(docker inspect --format '{{.State.Running}}' rtbcat-api 2>/dev/null || true)" == "true" ]]; then
  if ! docker exec rtbcat-api python /app/scripts/check_gmail_import_idle.py; then
    echo "Current Gmail import is active or could not be proven idle; refusing restart." >&2
    exit 1
  fi
fi

previous_release="$(readlink -f "$RELEASE_DIR/current.env" 2>/dev/null || true)"
docker compose --project-name rtbcat-hetzner -f "$COMPOSE_FILE" \
  up -d --no-build --remove-orphans

if ! docker exec rtbcat-api \
  python /app/scripts/hetzner/hydrate_google_app_credentials.py; then
  echo "Failed to hydrate retained Gmail/Authorized Buyers credentials from GSM." >&2
  exit 1
fi

if ! "$VERIFY_SCRIPT" --release-file "$approved_release" --with-google; then
  echo "New release failed acceptance." >&2
  if [[ -n "$previous_release" ]]; then
    echo "Rollback candidate: ${previous_release}" >&2
  fi
  exit 1
fi

install -o root -g root -m 0644 /dev/null \
  "$RELEASE_DIR/accepted-${RELEASE_GIT_SHA}.marker"
ln -sfn "$(basename "$approved_release")" "$RELEASE_DIR/current.env"
echo "Activated immutable shadow release ${RELEASE_GIT_SHA}. DNS and GCP were unchanged."
