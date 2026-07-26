#!/usr/bin/env bash
# Restore a selected encrypted pgBackRest backup to a time target on the
# disposable clean host and verify the before/after PITR witness.

set -euo pipefail

STANZA="rtbcat"
CONFIG_FILE="/etc/pgbackrest/pgbackrest.conf"
MARKER_FILE="/etc/rtbcat/restore-drill-host.env"
PRODUCTION_MARKER="/etc/rtbcat/database-host.env"
PGDATA="/var/lib/postgresql/15/main"
POSTGRES_UNIT="postgresql@15-main.service"
BACKUP_SET=""
TARGET_TIME=""
TARGET_TIME_POSTGRES=""
EXPECTED_DATABASE="rtbcat_serving_rehearsal"
EXPECTED_TABLE_COUNT="98"
BEFORE_MARKER=""
AFTER_MARKER=""
JSON_OUT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/restore_pgbackrest_pitr_drill.sh \
  --backup-set <full-backup-label> \
  --target-time <RFC3339-time> \
  --before-marker <marker> \
  --after-marker <marker> \
  --json-out <path> \
  --confirm DESTROY_EMPTY_RESTORE_DRILL_CLUSTER

Optional:
  --expected-database <name>      Default: rtbcat_serving_rehearsal
  --expected-table-count <count>  Default: 98
  --config-file <path>            Default: /etc/pgbackrest/pgbackrest.conf

This command is destructive only to the small, stopped PostgreSQL cluster on
the Terraform-marked disposable restore host. It refuses the production host,
requires the local-disk restore marker and hostname, and refuses a pre-restore
PGDATA larger than 1 GiB.

Install an exact mode-0600 postgres-owned copy of the production repository
configuration on the disposable host before running this command. Never print
or place that configuration in evidence.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-set)
      BACKUP_SET="${2:?--backup-set requires a value}"
      shift 2
      ;;
    --target-time)
      TARGET_TIME="${2:?--target-time requires a value}"
      shift 2
      ;;
    --before-marker)
      BEFORE_MARKER="${2:?--before-marker requires a value}"
      shift 2
      ;;
    --after-marker)
      AFTER_MARKER="${2:?--after-marker requires a value}"
      shift 2
      ;;
    --expected-database)
      EXPECTED_DATABASE="${2:?--expected-database requires a value}"
      shift 2
      ;;
    --expected-table-count)
      EXPECTED_TABLE_COUNT="${2:?--expected-table-count requires a value}"
      shift 2
      ;;
    --config-file)
      CONFIG_FILE="${2:?--config-file requires a value}"
      shift 2
      ;;
    --json-out)
      JSON_OUT="${2:?--json-out requires a value}"
      shift 2
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
  echo "Run this script as root." >&2
  exit 1
fi
if [[ "$CONFIRM" != "DESTROY_EMPTY_RESTORE_DRILL_CLUSTER" ]]; then
  echo "Exact destructive confirmation for the disposable cluster is required." >&2
  usage >&2
  exit 1
fi
if [[ ! -f "$MARKER_FILE" ]] || \
   ! grep -qx 'RTBCAT_RESTORE_DRILL=true' "$MARKER_FILE" || \
   ! grep -qx 'RTBCAT_RESTORE_DRILL_BOOTSTRAPPED=true' "$MARKER_FILE"; then
  echo "Bootstrapped Terraform restore-drill marker is absent." >&2
  exit 1
fi
if [[ -e "$PRODUCTION_MARKER" ]]; then
  echo "Production database marker is present; refusing restore." >&2
  exit 1
fi
if [[ "$(hostname -s)" != *"-pgbackrest-restore" ]]; then
  echo "Unexpected hostname for a restore-drill host: $(hostname -s)" >&2
  exit 1
fi
if [[ -z "$BACKUP_SET" || -z "$TARGET_TIME" || -z "$BEFORE_MARKER" || \
      -z "$AFTER_MARKER" || -z "$JSON_OUT" ]]; then
  echo "Backup set, target time, both witness markers and JSON output are required." >&2
  usage >&2
  exit 1
fi
if ! [[ "$BACKUP_SET" =~ ^[0-9]{8}-[0-9]{6}F$ ]]; then
  echo "The restore drill requires an explicit full-backup label." >&2
  exit 1
fi
if ! date -u -d "$TARGET_TIME" +%FT%TZ >/dev/null 2>&1; then
  echo "TARGET_TIME is not parseable as an RFC3339 timestamp." >&2
  exit 1
fi
# pgBackRest accepts an RFC3339 target, but PostgreSQL 15 writes and parses the
# recovery target as a timestamp with time zone. Normalize to PostgreSQL's
# unambiguous UTC representation before pgBackRest writes postgresql.auto.conf.
TARGET_TIME_POSTGRES="$(
  date -u -d "$TARGET_TIME" '+%Y-%m-%d %H:%M:%S.%6N+00'
)"
if ! [[ "$EXPECTED_DATABASE" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || \
   ! [[ "$EXPECTED_TABLE_COUNT" =~ ^[1-9][0-9]*$ ]]; then
  echo "Expected database or table-count argument is invalid." >&2
  exit 1
fi
for marker in "$BEFORE_MARKER" "$AFTER_MARKER"; do
  if ! [[ "$marker" =~ ^[A-Za-z0-9._:-]{8,128}$ ]]; then
    echo "PITR witness markers must be safe 8-128 character identifiers." >&2
    exit 1
  fi
done
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Repository configuration is missing: ${CONFIG_FILE}" >&2
  exit 1
fi
output_parent="$(dirname "$JSON_OUT")"
if [[ ! -d "$output_parent" ]]; then
  echo "Evidence parent directory does not exist: ${output_parent}" >&2
  exit 1
fi
config_owner="$(stat -c '%U' "$CONFIG_FILE")"
config_mode="$(stat -c '%a' "$CONFIG_FILE")"
if [[ "$config_owner" != "postgres" || "$config_mode" != "600" ]]; then
  echo "Repository configuration must be postgres-owned mode 0600." >&2
  exit 1
fi
if ! grep -qx 'repo1-cipher-type=aes-256-cbc' "$CONFIG_FILE"; then
  echo "Repository configuration does not enforce AES-256-CBC encryption." >&2
  exit 1
fi
if [[ "$(findmnt -n -o TARGET --target "$PGDATA")" != "/" ]]; then
  echo "Restore-drill PGDATA is not on the disposable host's local root disk." >&2
  exit 1
fi

info_json="$(sudo -u postgres pgbackrest \
  --config="$CONFIG_FILE" --stanza="$STANZA" --output=json info)"
if ! jq -e \
  --arg backup_set "$BACKUP_SET" \
  'any(.[]; any(.backup[]?; .label == $backup_set and .type == "full" and (.error == false)))' \
  <<<"$info_json" >/dev/null; then
  echo "Requested successful full backup is not present in the repository." >&2
  exit 1
fi

systemctl stop "$POSTGRES_UNIT" postgresql
if systemctl is-active --quiet "$POSTGRES_UNIT"; then
  echo "PostgreSQL is still active; refusing to replace PGDATA." >&2
  exit 1
fi
pgdata_bytes="$(du -sb "$PGDATA" | awk '{print $1}')"
if ! [[ "$pgdata_bytes" =~ ^[0-9]+$ ]] || (( pgdata_bytes > 1073741824 )); then
  echo "Pre-restore PGDATA exceeds the 1 GiB disposable-cluster guard: ${pgdata_bytes}." >&2
  exit 1
fi

find "$PGDATA" -mindepth 1 -delete
install -d -o postgres -g postgres -m 0700 "$PGDATA"

restore_started_at="$(date -u +%FT%TZ)"
sudo -u postgres pgbackrest \
  --config="$CONFIG_FILE" \
  --stanza="$STANZA" \
  --set="$BACKUP_SET" \
  --type=time \
  --target="$TARGET_TIME_POSTGRES" \
  --target-action=promote \
  --archive-mode=off \
  restore
restore_finished_at="$(date -u +%FT%TZ)"

systemctl start "$POSTGRES_UNIT"
for _attempt in $(seq 1 60); do
  if sudo -u postgres psql -X -Atqc 'SELECT 1' postgres >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if ! sudo -u postgres psql -X -Atqc 'SELECT 1' postgres >/dev/null 2>&1; then
  echo "Restored PostgreSQL did not become ready." >&2
  exit 1
fi

server_json="$(sudo -u postgres psql -X -Atqc "
  SELECT json_build_object(
    'server_version', current_setting('server_version'),
    'data_checksums', current_setting('data_checksums'),
    'archive_mode', current_setting('archive_mode'),
    'listen_addresses', current_setting('listen_addresses'),
    'in_recovery', pg_is_in_recovery()
  );
")"
database_json="$(sudo -u postgres psql -X -Atq \
  --dbname="$EXPECTED_DATABASE" -c "
  SELECT json_build_object(
    'database', current_database(),
    'database_bytes', pg_database_size(current_database()),
    'user_table_count', (
      SELECT count(*)
      FROM information_schema.tables
      WHERE table_type = 'BASE TABLE'
        AND table_schema NOT IN ('pg_catalog', 'information_schema')
    )
  );
")"
probe_json="$(sudo -u postgres psql -X -Atq \
  --dbname=rtbcat_pgbackrest_pitr_probe -c "
  SELECT COALESCE(json_agg(marker ORDER BY marker), '[]'::json)
  FROM public.pitr_markers;
")"
restored_bytes="$(du -sb "$PGDATA" | awk '{print $1}')"
root_free_bytes="$(df -B1 --output=avail / | tail -n 1 | tr -d ' ')"

evidence_json="$(jq -n \
  --arg generated_at "$(date -u +%FT%TZ)" \
  --arg hostname "$(hostname -f)" \
  --arg backup_set "$BACKUP_SET" \
  --arg target_time "$TARGET_TIME" \
  --arg target_time_postgres "$TARGET_TIME_POSTGRES" \
  --arg before_marker "$BEFORE_MARKER" \
  --arg after_marker "$AFTER_MARKER" \
  --arg restore_started_at "$restore_started_at" \
  --arg restore_finished_at "$restore_finished_at" \
  --argjson expected_table_count "$EXPECTED_TABLE_COUNT" \
  --argjson restored_bytes "$restored_bytes" \
  --argjson root_free_bytes "$root_free_bytes" \
  --argjson server "$server_json" \
  --argjson database "$database_json" \
  --argjson probe_markers "$probe_json" \
  '
    {
      generated_at: $generated_at,
      hostname: $hostname,
      backup_set: $backup_set,
      target_time: $target_time,
      target_time_postgres: $target_time_postgres,
      restore_started_at: $restore_started_at,
      restore_finished_at: $restore_finished_at,
      server: $server,
      database: $database,
      pitr_witness: {
        before_marker: $before_marker,
        after_marker: $after_marker,
        restored_markers: $probe_markers
      },
      storage: {
        restored_pgdata_bytes: $restored_bytes,
        root_free_bytes: $root_free_bytes
      }
    }
    | .accepted = ((
        .server.server_version | startswith("15.17")
      ) and (
        .server.data_checksums == "on"
        and .server.archive_mode == "off"
        and .server.listen_addresses == "127.0.0.1"
        and (.server.in_recovery == false)
        and (.database.user_table_count == $expected_table_count)
        and (.pitr_witness.restored_markers | index($before_marker) != null)
        and (.pitr_witness.restored_markers | index($after_marker) == null)
      ))
  ')"

umask 077
printf '%s\n' "$evidence_json" > "$JSON_OUT"
printf '%s\n' "$evidence_json"

if ! jq -e '.accepted == true' <<<"$evidence_json" >/dev/null; then
  echo "Clean-host pgBackRest PITR acceptance failed." >&2
  exit 1
fi
