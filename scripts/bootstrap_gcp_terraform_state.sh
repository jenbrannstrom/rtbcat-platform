#!/usr/bin/env bash
# Create the GCS bucket used for Terraform remote state and initialize Terraform.

set -euo pipefail

PROJECT=""
LOCATION="asia-southeast1"
BUCKET=""
PREFIX="terraform/gcp"
RUN_INIT="false"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/bootstrap_gcp_terraform_state.sh \
    --project catscan-prod-202601 \
    --bucket catscan-prod-202601-tfstate \
    --init

Options:
  --location asia-southeast1
  --prefix terraform/gcp
  --init        Run terraform init with this backend after creating the bucket.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) PROJECT="${2:-}"; shift 2 ;;
    --location) LOCATION="${2:-}"; shift 2 ;;
    --bucket) BUCKET="${2:-}"; shift 2 ;;
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --init) RUN_INIT="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$PROJECT" ] || [ -z "$BUCKET" ]; then
  usage >&2
  exit 2
fi

if gcloud storage buckets describe "gs://${BUCKET}" --project="$PROJECT" >/dev/null 2>&1; then
  echo "Terraform state bucket exists: gs://${BUCKET}"
else
  echo "Creating Terraform state bucket: gs://${BUCKET}"
  gcloud storage buckets create "gs://${BUCKET}" \
    --project="$PROJECT" \
    --location="$LOCATION" \
    --uniform-bucket-level-access \
    --public-access-prevention=enforced \
    >/dev/null
fi

gcloud storage buckets update "gs://${BUCKET}" \
  --project="$PROJECT" \
  --versioning \
  >/dev/null

echo "Terraform backend:"
echo "  bucket = ${BUCKET}"
echo "  prefix = ${PREFIX}"

if [ "$RUN_INIT" = "true" ]; then
  terraform -chdir="$ROOT_DIR/terraform/gcp" init \
    -backend-config="bucket=${BUCKET}" \
    -backend-config="prefix=${PREFIX}" \
    -migrate-state
fi
