#!/usr/bin/env bash
set -euo pipefail

# One-command installer for VM2 (staging) using terraform/gcp_sg_vm2
# Stores terraform.tfvars locally (gitignored). No secrets are committed.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT_DIR/terraform/gcp_sg_vm2"
TFVARS="$TF_DIR/terraform.tfvars"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: $1 not found. Install it first." >&2
    exit 1
  }
}

prompt() {
  local var_name="$1"
  local prompt_text="$2"
  local default_value="${3:-}"
  local secret="${4:-false}"

  if [ "$secret" = "true" ]; then
    read -r -s -p "$prompt_text" value
    echo
  else
    if [ -n "$default_value" ]; then
      read -r -p "$prompt_text [$default_value]: " value
      value="${value:-$default_value}"
    else
      read -r -p "$prompt_text: " value
    fi
  fi

  printf -v "$var_name" '%s' "$value"
}

require_cmd gcloud
require_cmd terraform

if [ ! -d "$TF_DIR" ]; then
  echo "ERROR: $TF_DIR not found." >&2
  exit 1
fi

# Collect inputs
prompt PROJECT_ID "GCP Project ID" "your-gcp-project-id"
prompt REGION "GCP region" "asia-southeast1"
prompt ZONE "GCP zone" "asia-southeast1-b"
prompt APP_NAME "App name" "catscan"
prompt ENVIRONMENT "Environment" "production"
prompt MACHINE_TYPE "Machine type" "e2-medium"
prompt BOOT_DISK_SIZE "Boot disk size (GB)" "80"

prompt DOMAIN_NAME "Domain (e.g., app.example.com or leave blank)" ""
prompt ENABLE_HTTPS "Enable HTTPS (true/false)" "true"

prompt GITHUB_REPO "GitHub repo URL" "https://github.com/YOUR_ORG/rtbcat-platform.git"
prompt GITHUB_BRANCH "GitHub branch" "main"

prompt OAUTH_CLIENT_ID "OAuth Client ID" ""
prompt OAUTH_CLIENT_SECRET "OAuth Client Secret" "" true

prompt ALLOWED_DOMAINS "Allowed email domains (comma-separated)" "example.com"

prompt SERVICE_ACCOUNT_EMAIL "VM service account email" "service-account@your-gcp-project-id.iam.gserviceaccount.com"
prompt ARTIFACT_DOMAIN "Artifact Registry domain" "asia-southeast1-docker.pkg.dev"
prompt GCS_BUCKET "GCS bucket name" "your-analytics-bucket"

# Write tfvars (protected perms)
umask 077
cat > "$TFVARS" << EOFVARS
gcp_project = "$PROJECT_ID"
gcp_region  = "$REGION"
gcp_zone    = "$ZONE"

app_name    = "$APP_NAME"
environment = "$ENVIRONMENT"

machine_type   = "$MACHINE_TYPE"
boot_disk_size = $BOOT_DISK_SIZE

domain_name  = "$DOMAIN_NAME"
enable_https = $ENABLE_HTTPS

github_repo   = "$GITHUB_REPO"
github_branch = "$GITHUB_BRANCH"

google_oauth_client_id     = "$OAUTH_CLIENT_ID"
google_oauth_client_secret = "$OAUTH_CLIENT_SECRET"
allowed_email_domains      = ["${ALLOWED_DOMAINS//,/","}"]

service_account_email    = "$SERVICE_ACCOUNT_EMAIL"
artifact_registry_domain = "$ARTIFACT_DOMAIN"

gcs_bucket = "$GCS_BUCKET"
EOFVARS

# Run terraform
terraform -chdir="$TF_DIR" init
terraform -chdir="$TF_DIR" apply

echo "Done. VM2 should be created."
