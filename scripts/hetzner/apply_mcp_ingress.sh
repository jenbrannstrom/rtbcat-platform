#!/usr/bin/env bash
# Install the fixed mcp.rtb.cat Nginx vhost on the Hetzner app host.
# This script does not create DNS records or issue TLS certificates.

set -euo pipefail

CONFIRM=""
HOSTNAME="mcp.rtb.cat"
SITE_AVAILABLE="/etc/nginx/sites-available/rtbcat-mcp"
SITE_ENABLED="/etc/nginx/sites-enabled/rtbcat-mcp"
CERT_DIR="/etc/letsencrypt/live/${HOSTNAME}"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/apply_mcp_ingress.sh \
  --confirm APPLY_MCP_RTB_CAT_INGRESS

Installs and reloads the mcp.rtb.cat Nginx vhost. The MCP container must be
healthy on 127.0.0.1:8010 and the DNS-01 certificate must already exist at
/etc/letsencrypt/live/mcp.rtb.cat/{fullchain.pem,privkey.pem}.

This command never changes DNS, obtains a certificate, or enables MCP.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm) CONFIRM="${2:?missing confirmation}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root on the Hetzner app host." >&2
  exit 1
fi
if [[ "$CONFIRM" != "APPLY_MCP_RTB_CAT_INGRESS" ]]; then
  echo "Exact ingress confirmation is required." >&2
  exit 1
fi
for required_path in \
  /etc/rtbcat/app-host.env \
  "${CERT_DIR}/fullchain.pem" \
  "${CERT_DIR}/privkey.pem"; do
  if [[ ! -s "$required_path" ]]; then
    echo "Required host or certificate file is absent: ${required_path}." >&2
    exit 1
  fi
done
for command_name in curl docker install nginx python3 systemctl; do
  if ! command -v "$command_name" >/dev/null; then
    echo "Missing required command: ${command_name}." >&2
    exit 1
  fi
done
if [[ "$(docker inspect --format '{{.State.Running}}' rtbcat-mcp 2>/dev/null || true)" != "true" ]] || \
   [[ "$(docker inspect --format '{{.State.Health.Status}}' rtbcat-mcp 2>/dev/null || true)" != "healthy" ]]; then
  echo "rtbcat-mcp is not running and healthy." >&2
  exit 1
fi
curl -fsS --max-time 10 http://127.0.0.1:8010/health >/dev/null

install -d -o root -g root -m 0755 \
  "$(dirname "$SITE_AVAILABLE")" "$(dirname "$SITE_ENABLED")"
site_tmp="$(mktemp)"
cleanup() {
  rm -f -- "$site_tmp"
}
trap cleanup EXIT

python3 - "$HOSTNAME" "$site_tmp" "$CERT_DIR" <<'PY'
from pathlib import Path
import sys

hostname, output_path, cert_dir = sys.argv[1:]
config = f"""# Managed by scripts/hetzner/apply_mcp_ingress.sh
server {{
    listen 80;
    listen [::]:80;
    server_name {hostname};
    return 308 https://$host$request_uri;
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {hostname};

    ssl_certificate {cert_dir}/fullchain.pem;
    ssl_certificate_key {cert_dir}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:RTBCAT_MCP_TLS:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    location / {{
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_connect_timeout 15s;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_buffering off;
        proxy_request_buffering off;
    }}

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=86400" always;
}}
"""
Path(output_path).write_text(config)
PY

install -o root -g root -m 0644 "$site_tmp" "$SITE_AVAILABLE"
ln -sfn "$SITE_AVAILABLE" "$SITE_ENABLED"
nginx -t
systemctl reload nginx

curl -fsS \
  --max-time 15 \
  --resolve "${HOSTNAME}:443:127.0.0.1" \
  "https://${HOSTNAME}/health" >/dev/null

echo "Installed mcp.rtb.cat ingress to loopback port 8010; DNS and MCP enablement were unchanged."
