#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  manage_temp_public_ingress.sh stage \
    --hostname <temporary-hostname> \
    --confirm STAGE_TEMP_INGRESS_SEALED_NO_DNS

  manage_temp_public_ingress.sh activate \
    --hostname <temporary-hostname> \
    --operator-cidr <ipv4-or-ipv6-cidr> \
    --expected-ipv4 <hetzner-app-ipv4> \
    --email <acme-contact-email> \
    [--google-oauth] \
    --confirm ACTIVATE_TEMP_READ_ONLY_INGRESS_SCHEDULERS_OFF

  manage_temp_public_ingress.sh seal \
    --hostname <temporary-hostname> \
    --confirm SEAL_TEMP_INGRESS

  manage_temp_public_ingress.sh status \
    --hostname <temporary-hostname>

This command manages a temporary, operator-restricted public path to the
Hetzner shadow. It never changes DNS, database state, application mode or
scheduler ownership.

The stage action installs Nginx and Certbot, but serves only the ACME webroot
and HTTP 404 for the temporary hostname. The activate action requires direct
DNS resolution to the expected Hetzner IPv4, obtains a certificate, and proxies
only from loopback or the approved operator CIDR. The seal action returns the
hostname to ACME-plus-404 behavior without deleting certificates.
USAGE
}

MODE="${1:-}"
if [[ -n "${MODE}" ]]; then
  shift
fi

TEMP_HOSTNAME=""
OPERATOR_CIDR=""
EXPECTED_IPV4=""
ACME_EMAIL=""
CONFIRM=""
ENABLE_GOOGLE_OAUTH="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hostname)
      TEMP_HOSTNAME="${2:-}"
      shift 2
      ;;
    --operator-cidr)
      OPERATOR_CIDR="${2:-}"
      shift 2
      ;;
    --expected-ipv4)
      EXPECTED_IPV4="${2:-}"
      shift 2
      ;;
    --email)
      ACME_EMAIL="${2:-}"
      shift 2
      ;;
    --google-oauth)
      ENABLE_GOOGLE_OAUTH="true"
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

case "${MODE}" in
  stage|activate|seal|status)
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this command as root on the Hetzner app host." >&2
  exit 1
fi

if [[ ! -f /etc/rtbcat/app-host.env ]]; then
  echo "Hetzner app-host marker is absent." >&2
  exit 1
fi

if [[ ! "${TEMP_HOSTNAME}" =~ ^[a-z0-9][a-z0-9-]*-hetzner\.rtb\.cat$ ]]; then
  echo "Temporary hostname must match <name>-hetzner.rtb.cat." >&2
  exit 1
fi

if [[ "${TEMP_HOSTNAME}" == "scan.rtb.cat" ]]; then
  echo "The production hostname is forbidden in this temporary ingress tool." >&2
  exit 1
fi

SITE_AVAILABLE="/etc/nginx/sites-available/rtbcat-temp-ingress"
SITE_ENABLED="/etc/nginx/sites-enabled/rtbcat-temp-ingress"
ACME_WEBROOT="/var/lib/rtbcat/acme-webroot"

require_confirmation() {
  local expected="$1"
  if [[ "${CONFIRM}" != "${expected}" ]]; then
    echo "Refusing without --confirm ${expected}." >&2
    exit 1
  fi
}

validate_ip_or_cidr() {
  local value="$1"
  python3 - "${value}" <<'PY'
import ipaddress
import sys

try:
    ipaddress.ip_network(sys.argv[1], strict=False)
except ValueError as exc:
    raise SystemExit(f"Invalid IP/CIDR: {exc}")
PY
}

validate_ipv4() {
  local value="$1"
  python3 - "${value}" <<'PY'
import ipaddress
import sys

value = ipaddress.ip_address(sys.argv[1])
if value.version != 4:
    raise SystemExit("Expected an IPv4 address")
PY
}

container_env() {
  local key="$1"
  docker inspect \
    --format '{{range .Config.Env}}{{println .}}{{end}}' \
    rtbcat-api |
    awk -F= -v wanted="${key}" '$1 == wanted {sub(/^[^=]*=/, ""); print; exit}'
}

assert_shadow_safe() {
  local bad_listener database_name

  if [[ "$(docker inspect --format '{{.State.Running}}' rtbcat-api 2>/dev/null)" != "true" ]]; then
    echo "rtbcat-api is not running." >&2
    exit 1
  fi
  if [[ "$(docker inspect --format '{{.State.Health.Status}}' rtbcat-api 2>/dev/null)" != "healthy" ]]; then
    echo "rtbcat-api is not healthy." >&2
    exit 1
  fi
  if [[ "$(docker inspect --format '{{.State.Running}}' rtbcat-dashboard 2>/dev/null)" != "true" ]]; then
    echo "rtbcat-dashboard is not running." >&2
    exit 1
  fi
  if [[ "$(docker inspect --format '{{.State.Health.Status}}' rtbcat-dashboard 2>/dev/null)" != "healthy" ]]; then
    echo "rtbcat-dashboard is not healthy." >&2
    exit 1
  fi

  if [[ "$(container_env CATSCAN_READ_ONLY_SHADOW)" != "true" ]]; then
    echo "Temporary ingress requires CATSCAN_READ_ONLY_SHADOW=true." >&2
    exit 1
  fi
  if [[ "$(container_env CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER)" != "false" ]] ||
     [[ "$(container_env CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER)" != "false" ]] ||
     [[ "$(container_env CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER)" != "false" ]]; then
    echo "Every target scheduler flag must remain false." >&2
    exit 1
  fi

  database_name="$(container_env POSTGRES_DB)"
  case "${database_name}" in
    rtbcat_serving_rehearsal|rtbcat_serving)
      ;;
    *)
      echo "Unexpected target database for temporary ingress: ${database_name}." >&2
      exit 1
      ;;
  esac

  bad_listener="$(
    ss -ltnH |
      awk '$4 ~ /:3000$/ || $4 ~ /:8000$/ {if ($4 !~ /^127\.0\.0\.1:/) print $4}'
  )"
  if [[ -n "${bad_listener}" ]]; then
    echo "Application containers have a non-loopback listener: ${bad_listener}." >&2
    exit 1
  fi

  curl -fsS --max-time 15 http://127.0.0.1:8000/health |
    jq -e '.status == "healthy" and .database_exists == true' >/dev/null
}

render_sealed_site() {
  install -d -m 0755 "$(dirname "${SITE_AVAILABLE}")" "$(dirname "${SITE_ENABLED}")"
  install -d -o root -g www-data -m 0755 "${ACME_WEBROOT}/.well-known/acme-challenge"

  python3 - "${TEMP_HOSTNAME}" "${SITE_AVAILABLE}" "${ACME_WEBROOT}" <<'PY'
from pathlib import Path
import sys

hostname, output_path, webroot = sys.argv[1:]
config = f"""# Managed by scripts/hetzner/manage_temp_public_ingress.sh
# SEALED: ACME challenge files are available; application proxying is disabled.
server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}}

server {{
    listen 80;
    listen [::]:80;
    server_name {hostname};

    location ^~ /.well-known/acme-challenge/ {{
        root {webroot};
        default_type text/plain;
        try_files $uri =404;
    }}

    location / {{
        return 404;
    }}
}}
"""
Path(output_path).write_text(config)
Path(output_path).chmod(0o644)
PY
}

render_active_site() {
  local cert_dir="/etc/letsencrypt/live/${TEMP_HOSTNAME}"
  if [[ ! -s "${cert_dir}/fullchain.pem" || ! -s "${cert_dir}/privkey.pem" ]]; then
    echo "TLS certificate files are absent for ${TEMP_HOSTNAME}." >&2
    exit 1
  fi

  python3 - \
    "${TEMP_HOSTNAME}" \
    "${OPERATOR_CIDR}" \
    "${SITE_AVAILABLE}" \
    "${ACME_WEBROOT}" \
    "${cert_dir}" \
    "${ENABLE_GOOGLE_OAUTH}" <<'PY'
from pathlib import Path
import sys

hostname, operator_cidr, output_path, webroot, cert_dir, google_oauth_raw = sys.argv[1:]
google_oauth = google_oauth_raw == "true"

if google_oauth:
    oauth_locations = """
    location = /oauth2/ping {
        proxy_pass http://127.0.0.1:4180/ping;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /oauth2/ {
        proxy_pass http://127.0.0.1:4180;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Auth-Request-Redirect $request_uri;
    }

    location = /oauth2/auth {
        proxy_pass http://127.0.0.1:4180;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Content-Length "";
        proxy_pass_request_body off;
    }
"""
    api_locations = """
    location /api/ {
        auth_request /oauth2/auth;
        error_page 401 403 = @api_without_oauth;
        auth_request_set $email $upstream_http_x_auth_request_email;
        proxy_set_header X-Email $email;

        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;
        proxy_connect_timeout 15s;
        proxy_read_timeout 300s;
    }

    location @api_without_oauth {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;
        proxy_connect_timeout 15s;
        proxy_read_timeout 300s;
    }
"""
else:
    oauth_locations = ""
    api_locations = """
    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;
        proxy_connect_timeout 15s;
        proxy_read_timeout 300s;
    }
"""

config = f"""# Managed by scripts/hetzner/manage_temp_public_ingress.sh
# ACTIVE: read-only shadow proxy, restricted to loopback and one operator CIDR.
# GOOGLE_OAUTH: {"enabled" if google_oauth else "disabled"}
server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}}

server {{
    listen 80;
    listen [::]:80;
    server_name {hostname};

    location ^~ /.well-known/acme-challenge/ {{
        root {webroot};
        default_type text/plain;
        try_files $uri =404;
    }}

    location / {{
        return 308 https://$host$request_uri;
    }}
}}

server {{
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {hostname};

    ssl_certificate {cert_dir}/fullchain.pem;
    ssl_certificate_key {cert_dir}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:RTBCAT_TEMP_TLS:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    allow 127.0.0.1;
    allow ::1;
    allow {operator_cidr};
    deny all;

    client_max_body_size 200m;

{oauth_locations}
{api_locations}

    location / {{
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_connect_timeout 15s;
        proxy_read_timeout 300s;
    }}

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=86400" always;
}}
"""
Path(output_path).write_text(config)
Path(output_path).chmod(0o644)
PY
}

enable_site() {
  ln -sfn "${SITE_AVAILABLE}" "${SITE_ENABLED}"
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
}

verify_sealed() {
  local attempt status=""
  for attempt in {1..12}; do
    status="$(
      curl -sS \
        --max-time 10 \
        -o /dev/null \
        -w '%{http_code}' \
        -H "Host: ${TEMP_HOSTNAME}" \
        http://127.0.0.1/
    )"
    if [[ "${status}" == "404" ]]; then
      return
    fi
    sleep 1
  done
  echo "Sealed ingress returned HTTP ${status}, expected 404 after Nginx reload." >&2
  exit 1
}

verify_direct_dns() {
  local resolved
  mapfile -t resolved < <(
    getent ahostsv4 "${TEMP_HOSTNAME}" |
      awk '{print $1}' |
      sort -u
  )
  if [[ "${#resolved[@]}" -eq 0 ]]; then
    echo "${TEMP_HOSTNAME} has no IPv4 DNS answer." >&2
    exit 1
  fi
  if [[ "${#resolved[@]}" -ne 1 || "${resolved[0]}" != "${EXPECTED_IPV4}" ]]; then
    printf 'Temporary DNS must resolve only to %s; observed: %s\n' \
      "${EXPECTED_IPV4}" "${resolved[*]}" >&2
    exit 1
  fi
}

verify_active() {
  local attempt health_json=""
  for attempt in {1..12}; do
    if health_json="$(
      curl -fsS \
        --max-time 20 \
        --resolve "${TEMP_HOSTNAME}:443:127.0.0.1" \
        "https://${TEMP_HOSTNAME}/api/health" 2>/dev/null
    )" &&
      jq -e '.status == "healthy" and .database_exists == true' \
        <<<"${health_json}" >/dev/null; then
      break
    fi
    health_json=""
    sleep 1
  done
  if [[ -z "${health_json}" ]]; then
    echo "Temporary HTTPS health did not settle after Nginx reload." >&2
    exit 1
  fi
  if [[ "${ENABLE_GOOGLE_OAUTH}" == "true" ]]; then
    curl -fsS \
      --max-time 10 \
      --resolve "${TEMP_HOSTNAME}:443:127.0.0.1" \
      "https://${TEMP_HOSTNAME}/oauth2/ping" >/dev/null
  fi
  assert_shadow_safe
}

seal_failed_activation() {
  if [[ "${ACTIVATION_ACCEPTED:-0}" -eq 1 ]]; then
    return
  fi
  echo "Activation was not accepted; restoring sealed ACME-plus-404 mode." >&2
  render_sealed_site
  enable_site
  verify_sealed
}

case "${MODE}" in
  stage)
    require_confirmation STAGE_TEMP_INGRESS_SEALED_NO_DNS
    assert_shadow_safe

    if ! dpkg-query -W -f='${Status}\n' nginx certbot 2>/dev/null |
      grep -qx 'install ok installed'; then
      systemctl mask --now nginx.service >/dev/null 2>&1 || true
      apt-get update
      DEBIAN_FRONTEND=noninteractive apt-get install -y nginx certbot
      systemctl unmask nginx.service >/dev/null
    fi

    render_sealed_site
    enable_site
    verify_sealed
    assert_shadow_safe
    echo "Temporary ingress staged in sealed ACME-plus-404 mode for ${TEMP_HOSTNAME}."
    ;;

  activate)
    require_confirmation ACTIVATE_TEMP_READ_ONLY_INGRESS_SCHEDULERS_OFF
    if [[ -z "${OPERATOR_CIDR}" || -z "${EXPECTED_IPV4}" || -z "${ACME_EMAIL}" ]]; then
      echo "activate requires --operator-cidr, --expected-ipv4 and --email." >&2
      exit 2
    fi
    validate_ip_or_cidr "${OPERATOR_CIDR}"
    validate_ipv4 "${EXPECTED_IPV4}"
    if [[ ! "${ACME_EMAIL}" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
      echo "Invalid ACME contact email." >&2
      exit 2
    fi
    if ! command -v nginx >/dev/null || ! command -v certbot >/dev/null; then
      echo "Run stage before activate." >&2
      exit 1
    fi
    if [[ "${ENABLE_GOOGLE_OAUTH}" == "true" ]]; then
      if ! systemctl is-active --quiet rtbcat-temp-oauth2-proxy.service ||
         ! curl -fsS --max-time 5 http://127.0.0.1:4180/ping >/dev/null; then
        echo "Google OAuth was requested but its loopback proxy is not healthy." >&2
        exit 1
      fi
    fi

    assert_shadow_safe
    ACTIVATION_ACCEPTED=0
    trap seal_failed_activation EXIT
    if grep -q '^# ACTIVE:' "${SITE_AVAILABLE}" 2>/dev/null; then
      verify_active
    else
      verify_sealed
    fi
    verify_direct_dns
    certbot certonly \
      --webroot \
      --webroot-path "${ACME_WEBROOT}" \
      --domains "${TEMP_HOSTNAME}" \
      --email "${ACME_EMAIL}" \
      --agree-tos \
      --no-eff-email \
      --non-interactive
    render_active_site
    enable_site
    verify_active
    ACTIVATION_ACCEPTED=1
    trap - EXIT
    echo "Temporary read-only ingress active for ${TEMP_HOSTNAME}; schedulers remain disabled."
    ;;

  seal)
    require_confirmation SEAL_TEMP_INGRESS
    assert_shadow_safe
    if ! command -v nginx >/dev/null; then
      echo "Nginx is not installed; temporary ingress is already absent." >&2
      exit 0
    fi
    render_sealed_site
    enable_site
    verify_sealed
    assert_shadow_safe
    echo "Temporary ingress sealed for ${TEMP_HOSTNAME}; certificates were preserved."
    ;;

  status)
    assert_shadow_safe
    if [[ ! -e "${SITE_ENABLED}" ]]; then
      echo "temp_ingress=absent"
      exit 0
    fi
    if grep -q '^# ACTIVE:' "${SITE_AVAILABLE}"; then
      echo "temp_ingress=active"
    elif grep -q '^# SEALED:' "${SITE_AVAILABLE}"; then
      echo "temp_ingress=sealed"
    else
      echo "temp_ingress=unknown"
      exit 1
    fi
    echo "hostname=${TEMP_HOSTNAME}"
    echo "read_only_shadow=true"
    echo "schedulers=false"
    if grep -q '^# GOOGLE_OAUTH: enabled' "${SITE_AVAILABLE}"; then
      echo "google_oauth=enabled"
    else
      echo "google_oauth=disabled"
    fi
    ;;
esac
