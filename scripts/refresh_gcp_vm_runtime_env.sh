#!/usr/bin/env bash
# Refresh Cat-Scan VM runtime env files from Google Secret Manager.
#
# Run on the GCE VM. This script does not print secret values.

set -euo pipefail

APP_NAME="${APP_NAME:-catscan}"
APP_DIR="${APP_DIR:-/opt/catscan}"
PROJECT_ID="${GCP_PROJECT_ID:-}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-}"
RECREATE_API="false"

usage() {
  cat <<'EOF'
Usage:
  scripts/refresh_gcp_vm_runtime_env.sh [options]

Options:
  --project <project-id>     GCP project ID. Defaults to VM metadata project.
  --app-name <name>          Secret name prefix. Default: catscan
  --app-dir <path>           App directory. Default: /opt/catscan
  --cloudsql-instance <name> Cloud SQL connection name for compose recreation.
  --recreate-api             Recreate the API container after writing env files.
  --no-recreate-api          Only write env files.
  -h, --help                 Show help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) PROJECT_ID="${2:-}"; shift 2 ;;
    --app-name) APP_NAME="${2:-}"; shift 2 ;;
    --app-dir) APP_DIR="${2:-}"; shift 2 ;;
    --cloudsql-instance) CLOUDSQL_INSTANCE="${2:-}"; shift 2 ;;
    --recreate-api) RECREATE_API="true"; shift ;;
    --no-recreate-api) RECREATE_API="false"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID="$(curl -sf -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/project/project-id)"
fi

get_secret() {
  local secret_id="$1"
  gcloud secrets versions access latest \
    --secret="$secret_id" \
    --project="$PROJECT_ID"
}

upsert_env_line() {
  local file="$1"
  local key="$2"
  local value="$3"

  touch "$file"
  chmod 600 "$file"
  if grep -q "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf "%s=%s\n" "$key" "$value" >> "$file"
  fi
}

API_KEY="$(get_secret "${APP_NAME}-api-key")"
GMAIL_IMPORT_SECRET="$(get_secret "${APP_NAME}-gmail-import-secret")"
PRECOMPUTE_REFRESH_SECRET="$(get_secret "${APP_NAME}-precompute-refresh-secret")"
PRECOMPUTE_MONITOR_SECRET="$(get_secret "${APP_NAME}-precompute-monitor-secret")"
CREATIVE_CACHE_REFRESH_SECRET="$(get_secret "${APP_NAME}-creative-cache-refresh-secret")"

for env_file in /etc/catscan.env "${APP_DIR}/.env"; do
  upsert_env_line "$env_file" CATSCAN_API_KEY "$API_KEY"
  upsert_env_line "$env_file" GMAIL_IMPORT_SECRET "$GMAIL_IMPORT_SECRET"
  upsert_env_line "$env_file" PRECOMPUTE_REFRESH_SECRET "$PRECOMPUTE_REFRESH_SECRET"
  upsert_env_line "$env_file" PRECOMPUTE_MONITOR_SECRET "$PRECOMPUTE_MONITOR_SECRET"
  upsert_env_line "$env_file" CREATIVE_CACHE_REFRESH_SECRET "$CREATIVE_CACHE_REFRESH_SECRET"
done

if id catscan >/dev/null 2>&1 && [ -f "${APP_DIR}/.env" ]; then
  chown catscan:catscan "${APP_DIR}/.env"
fi

echo "Runtime env refreshed from GSM for ${APP_NAME} in ${PROJECT_ID}."

if [ "$RECREATE_API" = "true" ]; then
  cd "$APP_DIR"
  if [ -z "${IMAGE_REGISTRY:-}" ] || [ -z "${IMAGE_TAG:-}" ]; then
    current_image="$(docker inspect catscan-api --format '{{.Config.Image}}' 2>/dev/null || true)"
    if [[ "$current_image" == *"/catscan-api:"* ]]; then
      IMAGE_REGISTRY="${IMAGE_REGISTRY:-${current_image%/catscan-api:*}}"
      IMAGE_TAG="${IMAGE_TAG:-${current_image##*:}}"
      export IMAGE_REGISTRY IMAGE_TAG
    fi
  fi
  if [ -n "$CLOUDSQL_INSTANCE" ]; then
    export CLOUDSQL_INSTANCE
  fi
  if docker compose version >/dev/null 2>&1; then
    docker compose -f docker-compose.gcp.yml up -d --force-recreate api
  else
    docker-compose -f docker-compose.gcp.yml up -d --force-recreate api
  fi
fi
