#!/usr/bin/env bash
# Run on the Hetzner database host. Database bytes travel directly from Cloud
# SQL through a localhost-only Auth Proxy into a dump on a temporary Hetzner
# Volume. The restored database lives on the separate permanent Volume.

set -euo pipefail

SOURCE_INSTANCE=""
SOURCE_DATABASE=""
SOURCE_USER=""
SOURCE_PGPASS_FILE=""
CREDENTIALS_FILE=""
TARGET_DATABASE="rtbcat_serving_rehearsal"
TARGET_OWNER="rtbcat_serving"
DUMP_ROOT=""
JOBS=4
RESTORE="false"
CONFIRM=""
SOURCE_PORT=15432
REQUIRED_POSTGRES_VERSION="15.17"
REQUIRED_POSTGRES_VERSION_NUM="150017"
MARKER_FILE="/etc/rtbcat/database-host.env"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/rehearse_cloudsql_restore.sh [options]

Required:
  --source-instance <project:region:instance>
  --source-database <name>
  --source-user <name>
  --source-pgpass-file <path>  Mode-0600 libpq passfile for 127.0.0.1:15432.
  --dump-root <path>           Directory on the temporary rehearsal Volume.
  --confirm online-rehearsal-source-stays-live

Optional:
  --credentials-file <path>    ADC/WIF/service-account credential file for the
                               Cloud SQL Auth Proxy. If omitted, normal ADC is used.
  --target-database <name>     Must end in _rehearsal.
  --target-owner <role>        Existing target role (default: rtbcat_serving).
  --jobs <1-8>                 Parallel dump/restore jobs (default: 4).
  --restore                    Drop/recreate only the _rehearsal target and
                               restore the new dump after it is checksummed.
  --help

This is an ONLINE rehearsal: it does not freeze writers or change the source.
pg_dump takes a consistent snapshot while Cloud SQL remains production.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-instance)
      SOURCE_INSTANCE="${2:?--source-instance requires a value}"
      shift 2
      ;;
    --source-database)
      SOURCE_DATABASE="${2:?--source-database requires a value}"
      shift 2
      ;;
    --source-user)
      SOURCE_USER="${2:?--source-user requires a value}"
      shift 2
      ;;
    --source-pgpass-file)
      SOURCE_PGPASS_FILE="${2:?--source-pgpass-file requires a value}"
      shift 2
      ;;
    --credentials-file)
      CREDENTIALS_FILE="${2:?--credentials-file requires a value}"
      shift 2
      ;;
    --target-database)
      TARGET_DATABASE="${2:?--target-database requires a value}"
      shift 2
      ;;
    --target-owner)
      TARGET_OWNER="${2:?--target-owner requires a value}"
      shift 2
      ;;
    --dump-root)
      DUMP_ROOT="${2:?--dump-root requires a value}"
      shift 2
      ;;
    --jobs)
      JOBS="${2:?--jobs requires a value}"
      shift 2
      ;;
    --restore)
      RESTORE="true"
      shift
      ;;
    --confirm)
      CONFIRM="${2:?--confirm requires a value}"
      shift 2
      ;;
    --help|-h)
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

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root on the Hetzner database host." >&2
  exit 1
fi
if [[ "$CONFIRM" != "online-rehearsal-source-stays-live" ]]; then
  echo "The exact online-rehearsal confirmation is required." >&2
  usage >&2
  exit 1
fi
for value_name in SOURCE_INSTANCE SOURCE_DATABASE SOURCE_USER SOURCE_PGPASS_FILE DUMP_ROOT; do
  if [[ -z "${!value_name}" ]]; then
    echo "Missing required option: $value_name" >&2
    exit 1
  fi
done
if ! [[ "$SOURCE_INSTANCE" =~ ^[^:]+:[^:]+:[^:]+$ ]]; then
  echo "Source instance must have project:region:instance form." >&2
  exit 1
fi
if ! [[ "$TARGET_DATABASE" =~ ^[a-z_][a-z0-9_]*_rehearsal$ ]]; then
  echo "Target database must be a safe identifier ending in _rehearsal." >&2
  exit 1
fi
if ! [[ "$TARGET_OWNER" =~ ^[a-z_][a-z0-9_]{0,62}$ ]]; then
  echo "Target owner is not a safe lowercase PostgreSQL identifier." >&2
  exit 1
fi
if ! [[ "$JOBS" =~ ^[1-8]$ ]]; then
  echo "--jobs must be an integer from 1 to 8." >&2
  exit 1
fi
if [[ ! -f "$MARKER_FILE" ]]; then
  echo "This is not a marked RTBcat target database host." >&2
  exit 1
fi
if [[ ! -f "$SOURCE_PGPASS_FILE" ]] || \
   [[ "$(stat -c '%U' "$SOURCE_PGPASS_FILE")" != "root" ]] || \
   [[ "$(stat -c '%a' "$SOURCE_PGPASS_FILE")" != "600" ]]; then
  echo "Source pgpass file must be root-owned mode 0600." >&2
  exit 1
fi
if [[ -n "$CREDENTIALS_FILE" ]]; then
  if [[ ! -f "$CREDENTIALS_FILE" ]]; then
    echo "Credentials file does not exist: $CREDENTIALS_FILE" >&2
    exit 1
  fi
  credentials_owner="$(stat -c '%U' "$CREDENTIALS_FILE")"
  credentials_mode="$(stat -c '%a' "$CREDENTIALS_FILE")"
  if [[ "$credentials_owner" != "root" || ( "$credentials_mode" != "600" && "$credentials_mode" != "400" ) ]]; then
    echo "Credentials file must be root-owned mode 0600 or 0400." >&2
    exit 1
  fi
fi

required_commands=(cloud-sql-proxy pg_dump pg_restore psql pg_isready sha256sum findmnt jq realpath)
for command_name in "${required_commands[@]}"; do
  if ! command -v "$command_name" >/dev/null; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done

normalized_dump_root="$(realpath -m "$DUMP_ROOT")"
if [[ "$DUMP_ROOT" != /* ]] || [[ "$DUMP_ROOT" == "/" ]] || [[ "$DUMP_ROOT" != "$normalized_dump_root" ]]; then
  echo "Dump root must be a normalized absolute child directory without traversal." >&2
  exit 1
fi
dump_mount="$(dirname "$normalized_dump_root")"
if ! findmnt --mountpoint "$dump_mount" >/dev/null 2>&1; then
  echo "The dump-root parent must be the mounted temporary Volume: ${dump_mount}." >&2
  exit 1
fi
dump_fstype="$(findmnt -n -o FSTYPE --mountpoint "$dump_mount")"
dump_source="$(findmnt -n -o SOURCE --mountpoint "$dump_mount")"
if [[ "$dump_fstype" != "xfs" ]]; then
  echo "Temporary dump Volume must use XFS, found ${dump_fstype}." >&2
  exit 1
fi
resolved_dump_source="$(readlink -f "$dump_source")"
dump_is_hcloud_volume="false"
while IFS= read -r volume_path; do
  if [[ "$(readlink -f "$volume_path")" == "$resolved_dump_source" ]]; then
    dump_is_hcloud_volume="true"
    break
  fi
done < <(compgen -G '/dev/disk/by-id/scsi-0HC_Volume_*' || true)
if [[ "$dump_is_hcloud_volume" != "true" ]]; then
  echo "Dump root is not backed by a recognized Hetzner Volume device." >&2
  exit 1
fi
data_mount="$(sed -n 's/^RTBCAT_DATA_MOUNT=//p' "$MARKER_FILE")"
data_mount="${data_mount:-/var/lib/postgresql}"
if ! findmnt --mountpoint "$data_mount" >/dev/null 2>&1; then
  echo "Permanent PostgreSQL data mount is missing: ${data_mount}." >&2
  exit 1
fi
data_source="$(findmnt -n -o SOURCE --mountpoint "$data_mount")"
if [[ "$(readlink -f "$data_source")" == "$resolved_dump_source" ]]; then
  echo "Dump and PostgreSQL data must use separate Volumes." >&2
  exit 1
fi
install -d -o root -g postgres -m 0750 "$DUMP_ROOT"

proxy_log="$(mktemp)"
proxy_args=(--address 127.0.0.1 --port "$SOURCE_PORT" --run-connection-test)
if [[ -n "$CREDENTIALS_FILE" ]]; then
  proxy_args+=(--credentials-file "$CREDENTIALS_FILE")
fi
proxy_args+=("$SOURCE_INSTANCE")
cloud-sql-proxy "${proxy_args[@]}" >"$proxy_log" 2>&1 &
proxy_pid=$!
cleanup() {
  kill "$proxy_pid" 2>/dev/null || true
  wait "$proxy_pid" 2>/dev/null || true
  rm -f -- "$proxy_log"
}
trap cleanup EXIT

for _ in $(seq 1 30); do
  if ! kill -0 "$proxy_pid" 2>/dev/null; then
    echo "Cloud SQL Auth Proxy exited during startup:" >&2
    sed -n '1,120p' "$proxy_log" >&2
    exit 1
  fi
  if pg_isready -h 127.0.0.1 -p "$SOURCE_PORT" -d "$SOURCE_DATABASE" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! pg_isready -h 127.0.0.1 -p "$SOURCE_PORT" -d "$SOURCE_DATABASE" >/dev/null 2>&1; then
  echo "Cloud SQL source did not become ready." >&2
  exit 1
fi

source_psql=(psql -X -h 127.0.0.1 -p "$SOURCE_PORT" -U "$SOURCE_USER" -d "$SOURCE_DATABASE")
source_version="$(PGPASSFILE="$SOURCE_PGPASS_FILE" "${source_psql[@]}" -Atqc 'SHOW server_version')"
target_version="$(sudo -u postgres psql -X -Atqc 'SHOW server_version')"
source_version_num="$(PGPASSFILE="$SOURCE_PGPASS_FILE" "${source_psql[@]}" -Atqc 'SHOW server_version_num')"
target_version_num="$(sudo -u postgres psql -X -Atqc 'SHOW server_version_num')"
if [[ "$source_version_num" != "$REQUIRED_POSTGRES_VERSION_NUM" || \
      "$target_version_num" != "$REQUIRED_POSTGRES_VERSION_NUM" ]]; then
  echo "Version mismatch: source=${source_version}, target=${target_version}, required=${REQUIRED_POSTGRES_VERSION}." >&2
  exit 1
fi
source_recovery="$(PGPASSFILE="$SOURCE_PGPASS_FILE" "${source_psql[@]}" -Atqc 'SELECT pg_is_in_recovery()')"
if [[ "$source_recovery" != "f" ]]; then
  echo "Expected the Cloud SQL source primary, pg_is_in_recovery=${source_recovery}." >&2
  exit 1
fi
IFS=$'\t' read -r source_encoding source_collate source_ctype < <(
  PGPASSFILE="$SOURCE_PGPASS_FILE" "${source_psql[@]}" -AtF $'\t' -c \
    "SELECT pg_encoding_to_char(encoding), datcollate, datctype FROM pg_database WHERE datname = current_database()"
)
IFS=$'\t' read -r target_encoding target_collate target_ctype < <(
  sudo -u postgres psql -X -AtF $'\t' -c \
    "SELECT pg_encoding_to_char(encoding), datcollate, datctype FROM pg_database WHERE datname = current_database()"
)
source_collate_key="${source_collate,,}"
source_collate_key="${source_collate_key//./}"
source_collate_key="${source_collate_key//-/}"
source_ctype_key="${source_ctype,,}"
source_ctype_key="${source_ctype_key//./}"
source_ctype_key="${source_ctype_key//-/}"
target_collate_key="${target_collate,,}"
target_collate_key="${target_collate_key//./}"
target_collate_key="${target_collate_key//-/}"
target_ctype_key="${target_ctype,,}"
target_ctype_key="${target_ctype_key//./}"
target_ctype_key="${target_ctype_key//-/}"
if [[ "$source_encoding" != "UTF8" || "$target_encoding" != "UTF8" ]] || \
   [[ "$source_collate_key" != "$target_collate_key" || "$source_ctype_key" != "$target_ctype_key" ]]; then
  echo "Encoding/locale mismatch: source=${source_encoding}/${source_collate}/${source_ctype}, target=${target_encoding}/${target_collate}/${target_ctype}." >&2
  echo "Rebuild the empty target cluster with the source locale before rehearsal." >&2
  exit 1
fi
source_size_bytes="$(PGPASSFILE="$SOURCE_PGPASS_FILE" "${source_psql[@]}" -Atqc 'SELECT pg_database_size(current_database())')"
source_data_bytes="$(PGPASSFILE="$SOURCE_PGPASS_FILE" "${source_psql[@]}" -Atqc 'SELECT COALESCE(sum(pg_table_size(relid)), 0) FROM pg_stat_user_tables')"
dump_free_bytes="$(df -B1 --output=avail "$DUMP_ROOT" | tail -n 1 | tr -d ' ')"
target_free_bytes="$(df -B1 --output=avail "$data_mount" | tail -n 1 | tr -d ' ')"
required_dump_free_bytes=$((source_data_bytes * 5 / 4))
required_target_free_bytes=$((source_size_bytes * 5 / 4))
if (( dump_free_bytes < required_dump_free_bytes )); then
  echo "Insufficient temporary dump space: free=${dump_free_bytes}, required=${required_dump_free_bytes}." >&2
  exit 1
fi
if (( target_free_bytes < required_target_free_bytes )); then
  echo "Insufficient permanent database space: free=${target_free_bytes}, required=${required_target_free_bytes}." >&2
  exit 1
fi

rehearsal_id="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${DUMP_ROOT}/${rehearsal_id}"
dump_dir="${run_dir}/database"
mkdir -m 0750 "$run_dir"

jq -n \
  --arg rehearsal_id "$rehearsal_id" \
  --arg source_database "$SOURCE_DATABASE" \
  --arg source_version "$source_version" \
  --arg source_encoding "$source_encoding" \
  --arg source_collate "$source_collate" \
  --arg source_ctype "$source_ctype" \
  --argjson source_size_bytes "$source_size_bytes" \
  --argjson source_data_bytes "$source_data_bytes" \
  --arg dump_mount "$dump_mount" \
  --arg target_database "$TARGET_DATABASE" \
  --arg target_version "$target_version" \
  --argjson parallel_jobs "$JOBS" \
  '{
    rehearsal_id: $rehearsal_id,
    source_database: $source_database,
    source_version: $source_version,
    source_encoding: $source_encoding,
    source_collate: $source_collate,
    source_ctype: $source_ctype,
    source_size_bytes: $source_size_bytes,
    source_data_bytes: $source_data_bytes,
    dump_mount: $dump_mount,
    target_database: $target_database,
    target_version: $target_version,
    parallel_jobs: $parallel_jobs,
    source_writer_freeze: false
  }' > "${run_dir}/metadata.json"

echo "Starting online server-to-server dump at ${rehearsal_id}. Cloud SQL remains writable."
dump_start="$(date +%s)"
PGPASSFILE="$SOURCE_PGPASS_FILE" pg_dump \
  -h 127.0.0.1 \
  -p "$SOURCE_PORT" \
  -U "$SOURCE_USER" \
  -d "$SOURCE_DATABASE" \
  --format=directory \
  --jobs="$JOBS" \
  --no-owner \
  --no-acl \
  --verbose \
  --file="$dump_dir" \
  2> >(tee "${run_dir}/pg_dump.stderr.log" >&2)
dump_seconds=$(( $(date +%s) - dump_start ))

pg_restore --list "$dump_dir" > "${run_dir}/restore.list"
(
  cd "$run_dir"
  find database -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS
)
jq --argjson seconds "$dump_seconds" '.dump_seconds = $seconds' \
  "${run_dir}/metadata.json" > "${run_dir}/metadata.json.next"
mv "${run_dir}/metadata.json.next" "${run_dir}/metadata.json"

chown -R root:postgres "$run_dir"
chmod -R g+rX,o-rwx "$run_dir"

if [[ "$RESTORE" == "true" ]]; then
  echo "Restoring only the protected rehearsal database ${TARGET_DATABASE}."
  restore_start="$(date +%s)"
  sudo -u postgres dropdb --if-exists "$TARGET_DATABASE"
  sudo -u postgres createdb \
    --owner="$TARGET_OWNER" \
    --template=template0 \
    --encoding=UTF8 \
    --locale=en_US.UTF-8 \
    "$TARGET_DATABASE"
  sudo -u postgres pg_restore \
    --dbname="$TARGET_DATABASE" \
    --jobs="$JOBS" \
    --exit-on-error \
    --no-owner \
    --no-acl \
    --role="$TARGET_OWNER" \
    "$dump_dir" \
    2> >(tee "${run_dir}/pg_restore.stderr.log" >&2)
  sudo -u postgres vacuumdb --dbname="$TARGET_DATABASE" --analyze-in-stages --jobs="$JOBS"
  sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d postgres \
    -c "ALTER DATABASE ${TARGET_DATABASE} SET default_transaction_read_only = on"
  restore_seconds=$(( $(date +%s) - restore_start ))
  target_size_bytes="$(sudo -u postgres psql -X -Atqc "SELECT pg_database_size('${TARGET_DATABASE}')")"
  jq \
    --argjson restore_seconds "$restore_seconds" \
    --argjson target_size_bytes "$target_size_bytes" \
    '.restore_seconds = $restore_seconds | .target_size_bytes = $target_size_bytes | .target_default_read_only = true' \
    "${run_dir}/metadata.json" > "${run_dir}/metadata.json.next"
  mv "${run_dir}/metadata.json.next" "${run_dir}/metadata.json"
fi

chown -R root:postgres "$run_dir"
chmod -R g+rX,o-rwx "$run_dir"

echo "Rehearsal artifacts: ${run_dir}"
echo "Source Cloud SQL was not frozen, modified, or disabled."
