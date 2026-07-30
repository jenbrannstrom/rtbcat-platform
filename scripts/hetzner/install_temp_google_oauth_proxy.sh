#!/usr/bin/env bash
set -euo pipefail

OAUTH2_PROXY_VERSION="7.6.0"
OAUTH2_PROXY_SHA256="5e2f84ded61074b5f33eeef2c9f6d2d94294bcc9f9802e78921f02189ece0988"
CLIENT_ID_FILE="/etc/rtbcat/secrets/oauth-client-id"
CLIENT_SECRET_FILE="/etc/rtbcat/secrets/oauth-client-secret"
COOKIE_SECRET_FILE="/etc/rtbcat/secrets/oauth-cookie-secret"
CONFIG_FILE="/etc/rtbcat/oauth2-proxy.cfg"
SERVICE_FILE="/etc/systemd/system/rtbcat-temp-oauth2-proxy.service"
TEMP_HOSTNAME=""
CONFIRM=""
ALLOWED_EMAIL_DOMAINS=()

usage() {
  cat <<'USAGE'
Usage:
  install_temp_google_oauth_proxy.sh \
    --hostname <temporary-hostname> \
    --allowed-email-domain <domain> \
    [--allowed-email-domain <domain> ...] \
    [--client-id-file <root-only-file>] \
    [--client-secret-file <root-only-file>] \
    --confirm INSTALL_TEMP_GOOGLE_OAUTH_PROXY_NO_DNS

Installs the checksum-pinned OAuth2 Proxy used by the GCP deployment and binds
it only to 127.0.0.1:4180. This command does not change DNS, Nginx, Compose,
database mode or scheduler ownership.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hostname)
      TEMP_HOSTNAME="${2:-}"
      shift 2
      ;;
    --allowed-email-domain)
      ALLOWED_EMAIL_DOMAINS+=("${2:-}")
      shift 2
      ;;
    --client-id-file)
      CLIENT_ID_FILE="${2:-}"
      shift 2
      ;;
    --client-secret-file)
      CLIENT_SECRET_FILE="${2:-}"
      shift 2
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
if [[ ! -f /etc/rtbcat/app-host.env ]]; then
  echo "Hetzner app-host marker is absent." >&2
  exit 1
fi
if [[ "${CONFIRM}" != "INSTALL_TEMP_GOOGLE_OAUTH_PROXY_NO_DNS" ]]; then
  echo "Exact temporary OAuth installation confirmation is required." >&2
  exit 1
fi
if [[ ! "${TEMP_HOSTNAME}" =~ ^[a-z0-9][a-z0-9-]*-hetzner\.rtb\.cat$ ]]; then
  echo "Temporary hostname must match <name>-hetzner.rtb.cat." >&2
  exit 1
fi
if [[ "${#ALLOWED_EMAIL_DOMAINS[@]}" -eq 0 ]]; then
  echo "At least one --allowed-email-domain is required." >&2
  exit 2
fi
for domain in "${ALLOWED_EMAIL_DOMAINS[@]}"; do
  if [[ ! "${domain}" =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ ]]; then
    echo "Invalid allowed email domain: ${domain}." >&2
    exit 2
  fi
done

check_secret_file() {
  local path="$1"
  if [[ ! -s "${path}" ]]; then
    echo "Required OAuth input is absent or empty: ${path}." >&2
    exit 1
  fi
  if [[ "$(stat -c '%u:%g:%a' "${path}")" != "0:0:600" ]]; then
    echo "OAuth inputs must be root:root mode 0600: ${path}." >&2
    exit 1
  fi
}
check_secret_file "${CLIENT_ID_FILE}"
check_secret_file "${CLIENT_SECRET_FILE}"

client_id="$(<"${CLIENT_ID_FILE}")"
if [[ ! "${client_id}" =~ ^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$ ]]; then
  echo "OAuth client ID file has an unexpected format." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf -- "${tmp_dir}"
}
trap cleanup EXIT

archive="oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-amd64.tar.gz"
download_url="https://github.com/oauth2-proxy/oauth2-proxy/releases/download/v${OAUTH2_PROXY_VERSION}/${archive}"
curl -fsSL --proto '=https' --tlsv1.2 "${download_url}" -o "${tmp_dir}/${archive}"
printf '%s  %s\n' "${OAUTH2_PROXY_SHA256}" "${tmp_dir}/${archive}" |
  sha256sum -c -
tar -xzf "${tmp_dir}/${archive}" -C "${tmp_dir}"
binary="${tmp_dir}/oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-amd64/oauth2-proxy"
if [[ "$("${binary}" --version 2>&1)" != "oauth2-proxy v${OAUTH2_PROXY_VERSION} (built with go1.21.6)" ]]; then
  echo "Unexpected OAuth2 Proxy binary version." >&2
  exit 1
fi
install -o root -g root -m 0755 "${binary}" /usr/local/bin/oauth2-proxy

if ! getent group rtbcat-oauth >/dev/null; then
  groupadd --system rtbcat-oauth
fi
if ! id -u rtbcat-oauth >/dev/null 2>&1; then
  useradd \
    --system \
    --gid rtbcat-oauth \
    --home-dir /nonexistent \
    --shell /usr/sbin/nologin \
    rtbcat-oauth
fi

if [[ ! -s "${COOKIE_SECRET_FILE}" ]]; then
  umask 077
  openssl rand -hex 16 > "${COOKIE_SECRET_FILE}"
fi
chown root:root "${COOKIE_SECRET_FILE}"
chmod 0600 "${COOKIE_SECRET_FILE}"

python3 - \
  "${TEMP_HOSTNAME}" \
  "${CLIENT_ID_FILE}" \
  "${CLIENT_SECRET_FILE}" \
  "${COOKIE_SECRET_FILE}" \
  "${CONFIG_FILE}" \
  "${ALLOWED_EMAIL_DOMAINS[@]}" <<'PY'
from pathlib import Path
import json
import sys

hostname, client_id_path, client_secret_path, cookie_secret_path, output_path, *domains = sys.argv[1:]
client_id = Path(client_id_path).read_text().strip()
client_secret = Path(client_secret_path).read_text().strip()
cookie_secret = Path(cookie_secret_path).read_text().strip()
if not client_id or not client_secret or len(cookie_secret) != 32:
    raise SystemExit("OAuth input file is empty or malformed")

config = f"""# Managed by scripts/hetzner/install_temp_google_oauth_proxy.sh
provider = "google"
client_id = {json.dumps(client_id)}
client_secret = {json.dumps(client_secret)}
cookie_secret = {json.dumps(cookie_secret)}
cookie_secure = true
cookie_name = "_catscan_temp_oauth"
redirect_url = "https://{hostname}/oauth2/callback"
http_address = "127.0.0.1:4180"
email_domains = {json.dumps(domains)}
cookie_expire = "168h"
cookie_refresh = "1h"
set_xauthrequest = true
pass_user_headers = true
reverse_proxy = true
skip_auth_routes = ["/ping", "/health"]
"""
path = Path(output_path)
path.write_text(config)
path.chmod(0o640)
PY
chown root:rtbcat-oauth "${CONFIG_FILE}"

install -o root -g root -m 0644 /dev/stdin "${SERVICE_FILE}" <<'UNIT'
[Unit]
Description=RTBcat temporary-host Google OAuth2 Proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=rtbcat-oauth
Group=rtbcat-oauth
ExecStart=/usr/local/bin/oauth2-proxy --config=/etc/rtbcat/oauth2-proxy.cfg
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictSUIDSGID=true
LockPersonality=true
CapabilityBoundingSet=
AmbientCapabilities=

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable rtbcat-temp-oauth2-proxy.service
systemctl restart rtbcat-temp-oauth2-proxy.service

for attempt in {1..20}; do
  if curl -fsS --max-time 3 http://127.0.0.1:4180/ping >/dev/null; then
    break
  fi
  if [[ "${attempt}" -eq 20 ]]; then
    echo "OAuth2 Proxy did not become healthy." >&2
    systemctl status rtbcat-temp-oauth2-proxy.service --no-pager >&2 || true
    exit 1
  fi
  sleep 1
done

bad_listener="$(
  ss -ltnH |
    awk '$4 ~ /:4180$/ {if ($4 !~ /^127\.0\.0\.1:/) print $4}'
)"
if [[ -n "${bad_listener}" ]]; then
  echo "OAuth2 Proxy has a non-loopback listener: ${bad_listener}." >&2
  exit 1
fi

echo "Temporary Google OAuth2 Proxy installed on loopback for ${TEMP_HOSTNAME}."
