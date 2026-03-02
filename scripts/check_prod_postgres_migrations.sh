#!/usr/bin/env bash
set -euo pipefail

INSTANCE="${CATSCAN_GCP_INSTANCE:-catscan-production-sg}"
ZONE="${CATSCAN_GCP_ZONE:-asia-southeast1-b}"
PROJECT="${CATSCAN_GCP_PROJECT:-}"
CONTAINER="${CATSCAN_API_CONTAINER:-catscan-api}"
MODE="both"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  scripts/check_prod_postgres_migrations.sh [options]

Runs postgres migration checks on the target VM/container:
  - python /app/scripts/postgres_migrate.py --status
  - python /app/scripts/postgres_migrate.py --audit-versions

Options:
  --instance <name>      VM instance (default: catscan-production-sg)
  --zone <zone>          GCP zone (default: asia-southeast1-b)
  --project <id>         Optional GCP project id
  --container <name>     Docker container name (default: catscan-api)
  --status-only          Run only --status
  --audit-only           Run only --audit-versions
  --dry-run              Print command only
  -h, --help             Show help

Examples:
  scripts/check_prod_postgres_migrations.sh
  scripts/check_prod_postgres_migrations.sh --project catscan-prod-202601
  scripts/check_prod_postgres_migrations.sh --status-only
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      INSTANCE="${2:-}"
      shift 2
      ;;
    --zone)
      ZONE="${2:-}"
      shift 2
      ;;
    --project)
      PROJECT="${2:-}"
      shift 2
      ;;
    --container)
      CONTAINER="${2:-}"
      shift 2
      ;;
    --status-only)
      MODE="status"
      shift
      ;;
    --audit-only)
      MODE="audit"
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if ! command -v gcloud >/dev/null 2>&1; then
  echo "'gcloud' is required but not installed." >&2
  exit 2
fi

if ! gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q .; then
  echo "No active gcloud login found. Run: gcloud auth login" >&2
  exit 2
fi

if [[ -z "${INSTANCE}" || -z "${ZONE}" || -z "${CONTAINER}" ]]; then
  echo "instance/zone/container must be non-empty." >&2
  exit 2
fi

status_cmd='/usr/bin/env "$PY_BIN" /app/scripts/postgres_migrate.py --status'
audit_cmd='/usr/bin/env "$PY_BIN" /app/scripts/postgres_migrate.py --audit-versions'
py_detect_cmd='set -euo pipefail; PY_BIN=""; for cand in /opt/venv/bin/python3 /opt/venv/bin/python /usr/local/bin/python3 /usr/local/bin/python python3 python; do if [ "${cand#/}" != "$cand" ]; then [ -x "$cand" ] || continue; else command -v "$cand" >/dev/null 2>&1 || continue; fi; if "$cand" -c "import psycopg" >/dev/null 2>&1; then PY_BIN="$cand"; break; fi; done; if [ -z "$PY_BIN" ]; then echo "No python with psycopg found in container. Tried /opt/venv/bin/python3,/opt/venv/bin/python,/usr/local/bin/python3,/usr/local/bin/python,python3,python." >&2; exit 3; fi; echo "Using PY_BIN=$PY_BIN";'

case "$MODE" in
  both)
    remote_inner="${py_detect_cmd} ${status_cmd}; echo; ${audit_cmd}"
    ;;
  status)
    remote_inner="${py_detect_cmd} ${status_cmd}"
    ;;
  audit)
    remote_inner="${py_detect_cmd} ${audit_cmd}"
    ;;
  *)
    echo "Invalid mode: $MODE" >&2
    exit 2
    ;;
esac

remote_cmd="sudo docker exec ${CONTAINER} sh -lc '$remote_inner'"

cmd=(gcloud compute ssh "$INSTANCE" --zone "$ZONE")
if [[ -n "$PROJECT" ]]; then
  cmd+=(--project "$PROJECT")
fi
cmd+=(--tunnel-through-iap -- "$remote_cmd")

echo "Target VM: ${INSTANCE} (${ZONE})"
if [[ -n "$PROJECT" ]]; then
  echo "Project: ${PROJECT}"
fi
echo "Container: ${CONTAINER}"
echo "Mode: ${MODE}"

if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "Dry-run command:"
  printf '  %q' "${cmd[@]}"
  echo
  exit 0
fi

"${cmd[@]}"
