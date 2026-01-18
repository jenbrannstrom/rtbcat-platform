#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${CATSCAN_DB_PATH:-/home/catscan/.catscan/catscan.db}"
BUCKET="${CATSCAN_GCS_BUCKET:-}"
PREFIX="gs://${BUCKET}/backups"
WORK_DIR="/tmp/catscan-restore"

usage() {
  cat <<EOF
Usage: $0 [gs://bucket/path/to/backup.db | YYYYMMDD]

Restores the Cat-Scan SQLite DB from GCS. If no argument is provided, restores
the latest backup found under ${PREFIX}.

Required env:
  CATSCAN_GCS_BUCKET  GCS bucket name (no gs:// prefix)

Optional env:
  CATSCAN_DB_PATH     DB path (default: ${DB_PATH})
EOF
}

if [[ -z "${BUCKET}" ]]; then
  echo "ERROR: CATSCAN_GCS_BUCKET is not set."
  usage
  exit 1
fi

mkdir -p "${WORK_DIR}"

SOURCE="${1:-}"
if [[ -n "${SOURCE}" && "${SOURCE}" != gs://* ]]; then
  SOURCE="${PREFIX}/$(date -d "${SOURCE}" +%Y/%m 2>/dev/null || true)/catscan-${SOURCE}.db"
fi

if [[ -z "${SOURCE}" ]]; then
  SOURCE="$(gsutil ls -l "${PREFIX}"/**/catscan-*.db | awk '{print $3}' | tail -1)"
fi

if [[ -z "${SOURCE}" ]]; then
  echo "ERROR: No backups found under ${PREFIX}."
  exit 1
fi

echo "Using backup: ${SOURCE}"
gsutil cp "${SOURCE}" "${WORK_DIR}/catscan-restore.db"

timestamp="$(date +%Y%m%d-%H%M%S)"
if [[ -f "${DB_PATH}" ]]; then
  echo "Backing up current DB to ${DB_PATH}.pre-restore-${timestamp}.db"
  cp "${DB_PATH}" "${DB_PATH}.pre-restore-${timestamp}.db"
fi

if command -v docker >/dev/null 2>&1; then
  docker stop catscan-api catscan-dashboard >/dev/null 2>&1 || true
fi

cp "${WORK_DIR}/catscan-restore.db" "${DB_PATH}"

if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' | grep -q '^catscan-api$'; then
  api_uid="$(docker exec catscan-api id -u rtbcat 2>/dev/null || true)"
  if [[ -n "${api_uid}" ]]; then
    chown -R "${api_uid}:${api_uid}" "$(dirname "${DB_PATH}")"
  fi
fi

if command -v docker >/dev/null 2>&1; then
  docker start catscan-api catscan-dashboard >/dev/null 2>&1 || true
fi

echo "Restore complete."
