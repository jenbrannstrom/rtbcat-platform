#!/usr/bin/env bash
set -euo pipefail

RELEASE_FILE="/var/lib/rtbcat/releases/current.env"
OVERRIDE_FILE="/etc/rtbcat/temp-google-oauth.override.yml"
RUNTIME_ENV_FILE="/etc/rtbcat/runtime.env"
POSTGRES_PASSWORD_FILE="/etc/rtbcat/secrets/postgres-password"
POSTGRES_CA_FILE="/etc/rtbcat/secrets/postgres-ca.crt"
GOOGLE_CREDENTIALS_FILE="/etc/rtbcat/secrets/google-adc.json"
DATA_DIR="/var/lib/rtbcat/app-data"
MARKER_FILE="/etc/rtbcat/app-host.env"
RELEASE_DIR="/var/lib/rtbcat/releases"
EXPECTED_DATABASE="rtbcat_serving_rehearsal"
CONFIRM=""
RESTORE_ONLY="false"
DEADMAN_UNIT=""
ACCEPTED="false"
SCRIPT_SELF="$(readlink -f "${BASH_SOURCE[0]}")"

usage() {
  cat <<'USAGE'
Usage:
  rehearse_temp_google_login.sh \
    [--release-file <accepted-release.env>] \
    [--override-file <temp-google-oauth.override.yml>] \
    --confirm ENABLE_TEMP_GOOGLE_LOGIN_READ_ONLY_SCHEDULERS_OFF

Restore the accepted password-only shadow:
  rehearse_temp_google_login.sh \
    --restore-only \
    [--release-file <accepted-release.env>] \
    --confirm RESTORE_TEMP_GOOGLE_LOGIN_SHADOW

This command changes only the Hetzner API container's login-provider
environment. It keeps the stale rehearsal database, read-only mode and every
scheduler flag disabled. A 15-minute systemd deadman restores the accepted
base Compose deployment unless activation is verified and accepted.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-file)
      RELEASE_FILE="${2:-}"
      shift 2
      ;;
    --override-file)
      OVERRIDE_FILE="${2:-}"
      shift 2
      ;;
    --restore-only)
      RESTORE_ONLY="true"
      shift
      ;;
    --confirm)
      CONFIRM="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this command as root on the Hetzner app host." >&2
  exit 1
fi
if [[ "${RESTORE_ONLY}" == "true" ]]; then
  if [[ "${CONFIRM}" != "RESTORE_TEMP_GOOGLE_LOGIN_SHADOW" ]]; then
    echo "Exact Google-login shadow-restoration confirmation is required." >&2
    exit 2
  fi
elif [[ "${CONFIRM}" != "ENABLE_TEMP_GOOGLE_LOGIN_READ_ONLY_SCHEDULERS_OFF" ]]; then
  echo "Exact temporary Google-login confirmation is required." >&2
  exit 2
fi

for required in \
  "${RELEASE_FILE}" \
  "${RUNTIME_ENV_FILE}" \
  "${POSTGRES_PASSWORD_FILE}" \
  "${POSTGRES_CA_FILE}" \
  "${GOOGLE_CREDENTIALS_FILE}" \
  "${MARKER_FILE}"; do
  if [[ ! -f "${required}" ]]; then
    echo "Required runtime file is absent: ${required}." >&2
    exit 1
  fi
done
if [[ "${RESTORE_ONLY}" != "true" && ! -f "${OVERRIDE_FILE}" ]]; then
  echo "Temporary Google OAuth override is absent: ${OVERRIDE_FILE}." >&2
  exit 1
fi

RELEASE_FILE="$(readlink -f "${RELEASE_FILE}")"
unset MCP_IMAGE
# shellcheck source=/dev/null
source "${RELEASE_FILE}"
# shellcheck source=/dev/null
source "${MARKER_FILE}"

for required_value in \
  API_IMAGE \
  DASHBOARD_IMAGE \
  RELEASE_GIT_SHA \
  RELEASE_VERSION \
  DEPLOY_COMPOSE_SHA256 \
  RTBCAT_DATABASE_PRIVATE_IP \
  RTBCAT_DATABASE_NAME \
  RTBCAT_DATABASE_OWNER; do
  if [[ -z "${!required_value:-}" ]]; then
    echo "Required release/runtime value is absent: ${required_value}." >&2
    exit 1
  fi
done
MCP_IMAGE="${MCP_IMAGE:-}"
HAS_MCP="false"
if [[ -n "${MCP_IMAGE}" ]]; then
  if ! [[ "${MCP_IMAGE}" =~ ^ghcr\.io/[a-z0-9._-]+/catscan-mcp@sha256:[a-f0-9]{64}$ ]]; then
    echo "Only the expected digest-pinned MCP image is accepted." >&2
    exit 1
  fi
  HAS_MCP="true"
fi
if [[ "${RTBCAT_DATABASE_NAME}" != "${EXPECTED_DATABASE}" ]]; then
  echo "Temporary Google login is restricted to ${EXPECTED_DATABASE}." >&2
  exit 1
fi
if [[ "$(readlink -f "${RELEASE_DIR}/current.env")" != "${RELEASE_FILE}" ]] ||
   [[ ! -f "${RELEASE_DIR}/accepted-${RELEASE_GIT_SHA}.marker" ]]; then
  echo "Release is not the currently accepted immutable shadow." >&2
  exit 1
fi

COMPOSE_FILE="${RELEASE_DIR}/compose-${RELEASE_GIT_SHA}.yml"
if [[ ! -f "${COMPOSE_FILE}" ]] ||
   [[ "$(sha256sum "${COMPOSE_FILE}" | awk '{print $1}')" != "${DEPLOY_COMPOSE_SHA256}" ]]; then
  echo "Archived Compose file does not match the accepted release." >&2
  exit 1
fi
if [[ "$(stat -c '%u:%a' "${RUNTIME_ENV_FILE}")" != "0:600" ]]; then
  echo "Runtime env must remain root-owned mode 0600." >&2
  exit 1
fi
for flag in \
  CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER \
  CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER \
  CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER; do
  if ! grep -qx "${flag}=false" "${RUNTIME_ENV_FILE}"; then
    echo "Runtime scheduler flag is not false: ${flag}." >&2
    exit 1
  fi
done
if ! grep -qx 'CATSCAN_READ_ONLY_SHADOW=true' "${RUNTIME_ENV_FILE}"; then
  echo "Runtime env is not read-only shadow mode." >&2
  exit 1
fi

export API_IMAGE DASHBOARD_IMAGE RELEASE_GIT_SHA RELEASE_VERSION
if [[ "${HAS_MCP}" == "true" ]]; then
  export MCP_IMAGE
else
  unset MCP_IMAGE
fi
export RTBCAT_RUNTIME_ENV_FILE="${RUNTIME_ENV_FILE}"
export RTBCAT_POSTGRES_PASSWORD_FILE="${POSTGRES_PASSWORD_FILE}"
export RTBCAT_POSTGRES_CA_FILE="${POSTGRES_CA_FILE}"
export RTBCAT_GOOGLE_CREDENTIALS_FILE="${GOOGLE_CREDENTIALS_FILE}"
export RTBCAT_DATA_DIR="${DATA_DIR}"
export RTBCAT_DATABASE_PRIVATE_IP RTBCAT_DATABASE_NAME RTBCAT_DATABASE_OWNER
export RTBCAT_DEPLOY_READ_ONLY_SHADOW=true
export RTBCAT_DEPLOY_GMAIL_SCHEDULER=false
export RTBCAT_DEPLOY_PRECOMPUTE_SCHEDULER=false
export RTBCAT_DEPLOY_CREATIVE_CACHE_SCHEDULER=false
export RTBCAT_DEPLOY_MCP_ENABLED=false

mapfile -t API_GATEWAYS < <(
  docker inspect \
    --format '{{range .NetworkSettings.Networks}}{{println .Gateway}}{{end}}' \
    rtbcat-api |
    sed '/^[[:space:]]*$/d'
)
if [[ "${#API_GATEWAYS[@]}" -ne 1 ]] ||
   [[ ! "${API_GATEWAYS[0]}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Expected exactly one IPv4 Docker gateway for the accepted API container." >&2
  exit 1
fi
API_GATEWAY="${API_GATEWAYS[0]}"
export RTBCAT_OAUTH2_PROXY_TRUSTED_IPS="127.0.0.1,::1,${API_GATEWAY}"

wait_for_api() {
  local attempt
  for attempt in {1..30}; do
    if [[ "$(docker inspect --format '{{.State.Health.Status}}' rtbcat-api 2>/dev/null || true)" == "healthy" ]] &&
       curl -fsS --max-time 10 http://127.0.0.1:8000/health |
         jq -e '.status == "healthy" and .database_exists == true' >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "API did not become healthy after the temporary login change." >&2
  return 1
}

assert_runtime_mode() {
  local expected_google="$1"
  local actual_trusted_proxy_ips bad_listener expected_password="true"
  if [[ "$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' rtbcat-api |
    awk -F= '$1 == "OAUTH2_PROXY_ENABLED" {sub(/^[^=]*=/, ""); print; exit}')" != "${expected_google}" ]]; then
    echo "Unexpected OAUTH2_PROXY_ENABLED runtime value." >&2
    return 1
  fi
  if [[ "${expected_google}" == "true" ]]; then
    expected_password="false"
  fi
  for pair in \
    CATSCAN_ENABLE_PASSWORD_LOGIN="${expected_password}" \
    CATSCAN_READ_ONLY_SHADOW=true \
    CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER=false \
    CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER=false \
    CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER=false \
    POSTGRES_DB="${EXPECTED_DATABASE}"; do
    key="${pair%%=*}"
    expected="${pair#*=}"
    actual="$(
      docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' rtbcat-api |
        awk -F= -v wanted="${key}" '$1 == wanted {sub(/^[^=]*=/, ""); print; exit}'
    )"
    if [[ "${actual}" != "${expected}" ]]; then
      echo "Unexpected runtime value for ${key}." >&2
      return 1
    fi
  done
  actual_trusted_proxy_ips="$(
    docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' rtbcat-api |
      awk -F= '$1 == "OAUTH2_PROXY_TRUSTED_IPS" {sub(/^[^=]*=/, ""); print; exit}'
  )"
  if [[ "${expected_google}" == "true" &&
        "${actual_trusted_proxy_ips}" != "${RTBCAT_OAUTH2_PROXY_TRUSTED_IPS}" ]]; then
    echo "OAuth2 Proxy trust is not restricted to loopback plus the exact Docker gateway." >&2
    return 1
  fi
  bad_listener="$(
    ss -ltnH |
      awk '$4 ~ /:(3000|8000|8010)$/ {if ($4 !~ /^127\.0\.0\.1:/) print $4}'
  )"
  if [[ -n "${bad_listener}" ]]; then
    echo "Application container listener escaped loopback: ${bad_listener}." >&2
    return 1
  fi
}

restore_shadow() {
  echo "Restoring accepted password-only read-only shadow." >&2
  docker compose \
    --project-name rtbcat-hetzner \
    -f "${COMPOSE_FILE}" \
    up -d --no-build --remove-orphans
  wait_for_api
  assert_runtime_mode false
}

restore_on_exit() {
  if [[ "${ACCEPTED}" != "true" ]]; then
    restore_shadow || true
  fi
}

if [[ "${RESTORE_ONLY}" == "true" ]]; then
  restore_shadow
  echo "Accepted password-only shadow restored."
  exit 0
fi

if ! systemctl is-active --quiet rtbcat-temp-oauth2-proxy.service ||
   ! curl -fsS --max-time 5 http://127.0.0.1:4180/ping >/dev/null; then
  echo "Temporary OAuth2 Proxy is not healthy on loopback." >&2
  exit 1
fi

rendered_config="$(mktemp)"
trap 'rm -f -- "${rendered_config}"' EXIT
docker compose \
  --project-name rtbcat-hetzner \
  -f "${COMPOSE_FILE}" \
  -f "${OVERRIDE_FILE}" \
  config --format json > "${rendered_config}"
if ! jq -e \
  --arg api "${API_IMAGE}" \
  --arg dashboard "${DASHBOARD_IMAGE}" \
  --arg mcp "${MCP_IMAGE}" \
  --argjson has_mcp "${HAS_MCP}" \
  --arg database "${EXPECTED_DATABASE}" \
  --arg trusted_proxy_ips "${RTBCAT_OAUTH2_PROXY_TRUSTED_IPS}" \
  '
    .services.api.image == $api
    and .services.dashboard.image == $dashboard
    and (if $has_mcp then
      .services.mcp.image == $mcp
      and .services.mcp.environment.CATSCAN_MCP_ENABLED == "false"
      and all(.services.mcp.ports[]; .host_ip == "127.0.0.1")
    else
      (.services | has("mcp") | not)
    end)
    and (.services.api | has("build") | not)
    and (.services.dashboard | has("build") | not)
    and .services.api.environment.OAUTH2_PROXY_ENABLED == "true"
    and .services.api.environment.OAUTH2_PROXY_TRUSTED_IPS == $trusted_proxy_ips
    and .services.api.environment.CATSCAN_ENABLE_GOOGLE_LOGIN == "true"
    and .services.api.environment.CATSCAN_ENABLE_PASSWORD_LOGIN == "false"
    and .services.api.environment.CATSCAN_READ_ONLY_SHADOW == "true"
    and .services.api.environment.CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER == "false"
    and .services.api.environment.CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER == "false"
    and .services.api.environment.CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER == "false"
    and .services.api.environment.POSTGRES_DB == $database
  ' "${rendered_config}" >/dev/null; then
  echo "Temporary Google-login Compose render violates immutable safety guards." >&2
  exit 1
fi

if ! docker exec rtbcat-api python /app/scripts/check_gmail_import_idle.py; then
  echo "Gmail import is active or could not be proven idle; refusing API restart." >&2
  exit 1
fi

DEADMAN_UNIT="rtbcat-temp-google-login-deadman-$(date -u +%Y%m%d%H%M%S)"
systemd-run \
  --unit "${DEADMAN_UNIT}" \
  --on-active=15m \
  "${SCRIPT_SELF}" \
  --restore-only \
  --release-file "${RELEASE_FILE}" \
  --confirm RESTORE_TEMP_GOOGLE_LOGIN_SHADOW >/dev/null

trap restore_on_exit EXIT
docker compose \
  --project-name rtbcat-hetzner \
  -f "${COMPOSE_FILE}" \
  -f "${OVERRIDE_FILE}" \
  up -d --no-build --remove-orphans
wait_for_api
assert_runtime_mode true
curl -fsS --max-time 10 http://127.0.0.1:8000/auth/providers |
  jq -e '
    .google == true
    and .password == false
    and .authing == false
    and .default_method == "google"
  ' >/dev/null

ACCEPTED="true"
trap - EXIT
rm -f -- "${rendered_config}"
systemctl stop "${DEADMAN_UNIT}.timer" >/dev/null 2>&1 || true
systemctl reset-failed "${DEADMAN_UNIT}.service" >/dev/null 2>&1 || true
echo "Temporary Google login enabled; password login is hidden while the app remains read-only and schedulers remain disabled."
