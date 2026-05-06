#!/usr/bin/env bash
# Provision Cat-Scan production runtime config that cannot safely live in git:
# Google Secret Manager secret versions, Cloud SQL serving credentials, and
# Cloud Scheduler secret headers.
#
# Terraform owns the GCP resources. This script owns the reproducible runtime
# values and post-apply wiring.

set -euo pipefail

PROJECT=""
REGION="asia-southeast1"
APP_NAME="catscan"
DOMAIN_NAME=""
DB_INSTANCE=""
DB_NAME="rtbcat_serving"
DB_USER="rtbcat_serving"
GMAIL_OAUTH_CLIENT_FILE=""
GMAIL_TOKEN_FILE=""
AB_SERVICE_ACCOUNT_FILE=""
OAUTH_CLIENT_SECRET_VALUE="${OAUTH_CLIENT_SECRET:-}"
ROTATE_SCHEDULER_SECRETS="false"
ROTATE_API_KEY="false"
ROTATE_DB_PASSWORD="false"
GITHUB_REPO=""
SYNC_GITHUB_CANARY_SECRET="false"
GMAIL_SCHEDULE="0 12 * * *"
PRECOMPUTE_SCHEDULE="30 13 * * *"
TIME_ZONE="Etc/UTC"

usage() {
  cat <<'EOF'
Usage:
  scripts/provision_gcp_runtime_config.sh \
    --project catscan-prod-202601 \
    --domain scan.rtb.cat \
    --db-instance catscan-production-serving

Optional inputs:
  --region asia-southeast1
  --app-name catscan
  --db-name rtbcat_serving
  --db-user rtbcat_serving
  --gmail-oauth-client-file path/to/gmail-oauth-client.json
  --gmail-token-file path/to/gmail-token.json
  --ab-service-account-file path/to/catscan-service-account.json
  --oauth-client-secret "$OAUTH_CLIENT_SECRET"
  --github-repo jenbrannstrom/rtbcat-platform
  --sync-github-canary-secret
  --rotate-scheduler-secrets
  --rotate-api-key
  --rotate-db-password

This script does not print secret values.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) PROJECT="${2:-}"; shift 2 ;;
    --region) REGION="${2:-}"; shift 2 ;;
    --app-name) APP_NAME="${2:-}"; shift 2 ;;
    --domain) DOMAIN_NAME="${2:-}"; shift 2 ;;
    --db-instance) DB_INSTANCE="${2:-}"; shift 2 ;;
    --db-name) DB_NAME="${2:-}"; shift 2 ;;
    --db-user) DB_USER="${2:-}"; shift 2 ;;
    --gmail-oauth-client-file) GMAIL_OAUTH_CLIENT_FILE="${2:-}"; shift 2 ;;
    --gmail-token-file) GMAIL_TOKEN_FILE="${2:-}"; shift 2 ;;
    --ab-service-account-file) AB_SERVICE_ACCOUNT_FILE="${2:-}"; shift 2 ;;
    --oauth-client-secret) OAUTH_CLIENT_SECRET_VALUE="${2:-}"; shift 2 ;;
    --github-repo) GITHUB_REPO="${2:-}"; shift 2 ;;
    --sync-github-canary-secret) SYNC_GITHUB_CANARY_SECRET="true"; shift ;;
    --rotate-scheduler-secrets) ROTATE_SCHEDULER_SECRETS="true"; shift ;;
    --rotate-api-key) ROTATE_API_KEY="true"; shift ;;
    --rotate-db-password) ROTATE_DB_PASSWORD="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

require() {
  local name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    echo "Missing required argument: ${name}" >&2
    exit 2
  fi
}

require "--project" "$PROJECT"
require "--domain" "$DOMAIN_NAME"
require "--db-instance" "$DB_INSTANCE"

GMAIL_IMPORT_URL="https://${DOMAIN_NAME}/api/gmail/import/scheduled"
PRECOMPUTE_REFRESH_URL="https://${DOMAIN_NAME}/api/precompute/refresh/scheduled"

secret_name() {
  local suffix="$1"
  printf "%s-%s" "$APP_NAME" "$suffix"
}

secret_exists() {
  gcloud secrets describe "$1" --project="$PROJECT" >/dev/null 2>&1
}

ensure_secret() {
  local name="$1"
  if secret_exists "$name"; then
    echo "Secret exists: ${name}"
  else
    echo "Creating secret: ${name}"
    gcloud secrets create "$name" \
      --project="$PROJECT" \
      --replication-policy=automatic \
      >/dev/null
  fi
}

secret_has_latest_version() {
  gcloud secrets versions access latest \
    --secret="$1" \
    --project="$PROJECT" \
    >/dev/null 2>&1
}

add_secret_string() {
  local name="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"
  chmod 600 "$tmp"
  printf "%s" "$value" > "$tmp"
  gcloud secrets versions add "$name" \
    --project="$PROJECT" \
    --data-file="$tmp" \
    >/dev/null
  rm -f "$tmp"
}

add_secret_file_if_present() {
  local name="$1"
  local file="$2"
  if [ -z "$file" ]; then
    return 0
  fi
  if [ ! -s "$file" ]; then
    echo "Secret file not found or empty: ${file}" >&2
    exit 2
  fi
  echo "Adding secret version from file: ${name}"
  gcloud secrets versions add "$name" \
    --project="$PROJECT" \
    --data-file="$file" \
    >/dev/null
}

get_secret() {
  gcloud secrets versions access latest \
    --secret="$1" \
    --project="$PROJECT"
}

ensure_generated_secret_version() {
  local name="$1"
  if [ "$ROTATE_SCHEDULER_SECRETS" = "true" ] || ! secret_has_latest_version "$name"; then
    echo "Adding generated secret version: ${name}"
    add_secret_string "$name" "$(openssl rand -hex 32)"
  else
    echo "Keeping existing secret version: ${name}"
  fi
}

upsert_http_scheduler() {
  local job_name="$1"
  local schedule="$2"
  local uri="$3"
  local headers="$4"
  local description="$5"

  if gcloud scheduler jobs describe "$job_name" \
    --project="$PROJECT" \
    --location="$REGION" \
    >/dev/null 2>&1; then
    echo "Updating Cloud Scheduler job: ${job_name}"
    gcloud scheduler jobs update http "$job_name" \
      --project="$PROJECT" \
      --location="$REGION" \
      --schedule="$schedule" \
      --time-zone="$TIME_ZONE" \
      --uri="$uri" \
      --http-method=POST \
      --update-headers="$headers" \
      --description="$description" \
      >/dev/null
  else
    echo "Creating Cloud Scheduler job: ${job_name}"
    gcloud scheduler jobs create http "$job_name" \
      --project="$PROJECT" \
      --location="$REGION" \
      --schedule="$schedule" \
      --time-zone="$TIME_ZONE" \
      --uri="$uri" \
      --http-method=POST \
      --headers="$headers" \
      --description="$description" \
      >/dev/null
  fi
}

echo "Provisioning Cat-Scan runtime config in project ${PROJECT}"

for suffix in \
  gmail-oauth-client \
  gmail-token \
  ab-service-account \
  api-key \
  precompute-refresh-secret \
  precompute-monitor-secret \
  gmail-import-secret \
  creative-cache-refresh-secret \
  oauth-client-secret \
  serving-db-credentials; do
  ensure_secret "$(secret_name "$suffix")"
done

add_secret_file_if_present "$(secret_name gmail-oauth-client)" "$GMAIL_OAUTH_CLIENT_FILE"
add_secret_file_if_present "$(secret_name gmail-token)" "$GMAIL_TOKEN_FILE"
add_secret_file_if_present "$(secret_name ab-service-account)" "$AB_SERVICE_ACCOUNT_FILE"

if [ -n "$OAUTH_CLIENT_SECRET_VALUE" ]; then
  echo "Adding OAuth client secret version"
  add_secret_string "$(secret_name oauth-client-secret)" "$OAUTH_CLIENT_SECRET_VALUE"
elif ! secret_has_latest_version "$(secret_name oauth-client-secret)"; then
  echo "Missing OAuth client secret. Pass --oauth-client-secret or set OAUTH_CLIENT_SECRET." >&2
  exit 2
fi

ensure_generated_secret_version "$(secret_name gmail-import-secret)"
if [ "$ROTATE_API_KEY" = "true" ] || ! secret_has_latest_version "$(secret_name api-key)"; then
  echo "Adding generated secret version: $(secret_name api-key)"
  add_secret_string "$(secret_name api-key)" "$(openssl rand -hex 32)"
else
  echo "Keeping existing API key secret version"
fi
ensure_generated_secret_version "$(secret_name precompute-refresh-secret)"
ensure_generated_secret_version "$(secret_name precompute-monitor-secret)"
ensure_generated_secret_version "$(secret_name creative-cache-refresh-secret)"

if [ "$SYNC_GITHUB_CANARY_SECRET" = "true" ]; then
  if [ -z "$GITHUB_REPO" ]; then
    echo "--sync-github-canary-secret requires --github-repo owner/repo" >&2
    exit 2
  fi
  if ! command -v gh >/dev/null 2>&1; then
    echo "--sync-github-canary-secret requires gh CLI" >&2
    exit 2
  fi
  echo "Syncing GitHub Actions CATSCAN_CANARY_BEARER_TOKEN from GSM API key"
  tmp_api_key="$(mktemp)"
  chmod 600 "$tmp_api_key"
  get_secret "$(secret_name api-key)" > "$tmp_api_key"
  gh secret set CATSCAN_CANARY_BEARER_TOKEN \
    --repo "$GITHUB_REPO" \
    < "$tmp_api_key" \
    >/dev/null
  rm -f "$tmp_api_key"
fi

if [ "$ROTATE_DB_PASSWORD" = "true" ] || ! secret_has_latest_version "$(secret_name serving-db-credentials)"; then
  echo "Creating Cloud SQL serving DB credential version"
  DB_PASSWORD="$(openssl rand -base64 36 | tr -d '\n')"
  gcloud sql users set-password "$DB_USER" \
    --project="$PROJECT" \
    --instance="$DB_INSTANCE" \
    --password="$DB_PASSWORD" \
    >/dev/null
  DB_JSON="{\"username\":\"${DB_USER}\",\"password\":\"${DB_PASSWORD}\",\"database\":\"${DB_NAME}\"}"
  add_secret_string "$(secret_name serving-db-credentials)" "$DB_JSON"
else
  echo "Keeping existing Cloud SQL serving DB credentials"
fi

GMAIL_IMPORT_SECRET_VALUE="$(get_secret "$(secret_name gmail-import-secret)")"
PRECOMPUTE_REFRESH_SECRET_VALUE="$(get_secret "$(secret_name precompute-refresh-secret)")"

upsert_http_scheduler \
  gmail-import \
  "$GMAIL_SCHEDULE" \
  "$GMAIL_IMPORT_URL" \
  "X-Gmail-Import-Secret=${GMAIL_IMPORT_SECRET_VALUE}" \
  "Daily Gmail report import"

upsert_http_scheduler \
  precompute-refresh \
  "$PRECOMPUTE_SCHEDULE" \
  "$PRECOMPUTE_REFRESH_URL" \
  "X-Precompute-Refresh-Secret=${PRECOMPUTE_REFRESH_SECRET_VALUE}" \
  "Daily precompute refresh after Gmail import"

echo "Runtime config provisioning complete."
