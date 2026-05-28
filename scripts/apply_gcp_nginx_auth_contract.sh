#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: apply_gcp_nginx_auth_contract.sh [--domain <domain>] [--no-reload]

Writes the Cat-Scan GCP nginx site from the repo-owned edge auth contract,
validates it with nginx -t, and reloads nginx unless --no-reload is provided.
USAGE
}

DOMAIN_NAME="${DOMAIN_NAME:-}"
RELOAD_NGINX=1
AGENT_API_HTPASSWD="${CATSCAN_AGENT_API_HTPASSWD:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN_NAME="${2:-}"
      shift 2
      ;;
    --no-reload)
      RELOAD_NGINX=0
      shift
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
  echo "This script must run as root because it writes /etc/nginx." >&2
  exit 1
fi

if [[ -z "${DOMAIN_NAME}" && -f /etc/nginx/sites-enabled/catscan ]]; then
  DOMAIN_NAME="$(awk '/server_name/ {print $2; exit}' /etc/nginx/sites-enabled/catscan | tr -d ';')"
fi

if [[ -z "${DOMAIN_NAME}" ]]; then
  DOMAIN_NAME="_"
fi

install -d -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled

read_env_value() {
  local key="$1"
  local file="$2"
  python3 - "$key" "$file" <<'PY'
from pathlib import Path
import sys

key = sys.argv[1]
path = Path(sys.argv[2])
try:
    lines = path.read_text().splitlines()
except FileNotFoundError:
    raise SystemExit(0)

for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    name, value = stripped.split("=", 1)
    if name.strip() != key:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    print(value)
    break
PY
}

if [[ -z "${AGENT_API_HTPASSWD}" && -f /etc/catscan.env ]]; then
  AGENT_API_HTPASSWD="$(read_env_value CATSCAN_AGENT_API_HTPASSWD /etc/catscan.env)"
fi

AGENT_API_AUTH_DIRECTIVES="        # Optional edge Basic Auth disabled; FastAPI still requires a cat_agent_ bearer token."
if [[ -n "${AGENT_API_HTPASSWD}" ]]; then
  printf '%s\n' "${AGENT_API_HTPASSWD}" > /etc/nginx/catscan-agent-api.htpasswd
  if getent group www-data >/dev/null 2>&1; then
    chown root:www-data /etc/nginx/catscan-agent-api.htpasswd
    chmod 0640 /etc/nginx/catscan-agent-api.htpasswd
  else
    chown root:root /etc/nginx/catscan-agent-api.htpasswd
    chmod 0644 /etc/nginx/catscan-agent-api.htpasswd
  fi
  AGENT_API_AUTH_DIRECTIVES='        auth_basic "Cat-Scan Agent API";
        auth_basic_user_file /etc/nginx/catscan-agent-api.htpasswd;'
fi

cat > /etc/nginx/sites-available/catscan <<'NGINXEOF'
# Cat-Scan Nginx Configuration
# Source of truth: scripts/apply_gcp_nginx_auth_contract.sh
# Auth contract:
# - /login reaches Next.js
# - /api/auth/* reaches FastAPI
# - /api/* reaches FastAPI, which owns session/API-key/webhook auth
# - OAuth2 Proxy may inject X-Email but is not the only auth gate

server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    # Allow large CSV uploads for imports (avoid 413)
    client_max_body_size 200m;

    # OAuth2 Proxy endpoints (handles Google login flow)
    location /oauth2/ {
        proxy_pass http://127.0.0.1:4180;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Auth-Request-Redirect $request_uri;
    }

    # OAuth2 Proxy auth check (internal)
    location = /oauth2/auth {
        proxy_pass http://127.0.0.1:4180;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Content-Length "";
        proxy_pass_request_body off;
    }

    # Health check (no auth required - for load balancers/monitoring)
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
    }

    # Precompute endpoints - allow scheduler/monitoring with secret headers
    location = /api/precompute/refresh/scheduled {
        proxy_pass http://127.0.0.1:8000/precompute/refresh/scheduled;
        proxy_set_header Host $host;
    }

    location = /api/precompute/health {
        proxy_pass http://127.0.0.1:8000/precompute/health;
        proxy_set_header Host $host;
    }

    # Gmail import scheduler endpoint - allow scheduler with secret header
    location = /api/gmail/import/scheduled {
        proxy_pass http://127.0.0.1:8000/gmail/import/scheduled;
        proxy_set_header Host $host;
    }

    # Outside-agent API. Optional Basic Auth is evaluated at the edge before
    # FastAPI validates the hashed, buyer-scoped cat_agent_ bearer token.
    location ^~ /api/agent/v1/ {
AGENT_API_AUTH_DIRECTIVES_PLACEHOLDER

        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 75s;
        proxy_connect_timeout 10s;
    }

    # API routes.
    #
    # OAuth2 Proxy is an optional identity source here: when its cookie is
    # present, nginx injects X-Email for the API. When it is absent, the request
    # still reaches FastAPI so local password sessions, bootstrap, provider
    # discovery, and JSON 401 responses keep working.
    location /api/ {
        auth_request /oauth2/auth;
        error_page 401 403 = @api_without_oauth;

        # Pass authenticated user info to backend
        auth_request_set $user $upstream_http_x_auth_request_user;
        auth_request_set $email $upstream_http_x_auth_request_email;
        proxy_set_header X-User $user;
        proxy_set_header X-Email $email;

        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;

        # Timeouts for long operations
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location @api_without_oauth {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Dashboard. The frontend renders /login and redirects unauthenticated users;
    # API calls remain protected by FastAPI session/API-key checks.
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
NGINXEOF

export AGENT_API_AUTH_DIRECTIVES
python3 - "$DOMAIN_NAME" <<'PY'
from pathlib import Path
import os
import sys

domain = sys.argv[1]
path = Path("/etc/nginx/sites-available/catscan")
text = path.read_text()
text = text.replace("DOMAIN_PLACEHOLDER", domain)
text = text.replace(
    "AGENT_API_AUTH_DIRECTIVES_PLACEHOLDER",
    os.environ["AGENT_API_AUTH_DIRECTIVES"],
)
path.write_text(text)
PY

ln -sf /etc/nginx/sites-available/catscan /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t

if [[ "${RELOAD_NGINX}" -eq 1 ]]; then
  systemctl reload nginx
fi

echo "Applied Cat-Scan nginx edge auth contract for server_name=${DOMAIN_NAME}"
