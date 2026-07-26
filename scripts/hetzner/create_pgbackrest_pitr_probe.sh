#!/usr/bin/env bash
# Create an isolated before/after WAL witness on the non-authoritative Hetzner
# rehearsal cluster so a clean-host time-target restore can prove PITR.

set -euo pipefail

STANZA="rtbcat"
CONFIG_FILE="/etc/pgbackrest/pgbackrest.conf"
MARKER_FILE="/etc/rtbcat/database-host.env"
PROBE_DATABASE="rtbcat_pgbackrest_pitr_probe"
JSON_OUT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/create_pgbackrest_pitr_probe.sh \
  --json-out <path> \
  --confirm CREATE_ISOLATED_PITR_WITNESS

Creates a separate probe database on the non-authoritative Hetzner rehearsal
cluster, commits a before marker, captures a time target, then commits an after
marker. WAL is switched and pgBackRest check succeeds after each marker.

The application database is not modified and no application writer or
scheduler is enabled. The probe database is retained until the clean-host
restore evidence is accepted.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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
if [[ "$CONFIRM" != "CREATE_ISOLATED_PITR_WITNESS" ]]; then
  echo "Exact isolated-witness confirmation is required." >&2
  usage >&2
  exit 1
fi
if [[ -z "$JSON_OUT" ]]; then
  echo "A private JSON evidence path is required." >&2
  exit 1
fi
if [[ ! -f "$MARKER_FILE" || ! -f "$CONFIG_FILE" ]]; then
  echo "Database host marker or pgBackRest configuration is missing." >&2
  exit 1
fi
if [[ "$(sudo -u postgres psql -X -Atqc 'SHOW archive_mode')" != "on" ]]; then
  echo "PostgreSQL WAL archiving is not enabled." >&2
  exit 1
fi

info_json="$(sudo -u postgres pgbackrest \
  --config="$CONFIG_FILE" --stanza="$STANZA" --output=json info)"
backup_set="$(jq -er '
  [.[] | .backup[]? | select(.type == "full" and (.error == false))]
  | sort_by(.timestamp.stop)
  | last
  | .label
' <<<"$info_json")"
if sudo -u postgres psql -X -Atqc \
  "SELECT 1 FROM pg_database WHERE datname = '${PROBE_DATABASE}'" postgres | \
  grep -qx 1; then
  echo "Probe database already exists; refusing to overwrite prior evidence." >&2
  exit 1
fi

before_marker="before-$(tr -d '-' < /proc/sys/kernel/random/uuid)"
after_marker="after-$(tr -d '-' < /proc/sys/kernel/random/uuid)"

sudo -u postgres createdb "$PROBE_DATABASE"
sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
  --dbname="$PROBE_DATABASE" <<'SQL'
CREATE TABLE public.pitr_markers (
  marker text PRIMARY KEY,
  committed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
SQL
sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
  --dbname="$PROBE_DATABASE" \
  --set=marker="$before_marker" <<'SQL'
INSERT INTO public.pitr_markers (marker) VALUES (:'marker');
SQL
sudo -u postgres psql -X -Atqc 'SELECT pg_switch_wal()' postgres >/dev/null
sudo -u postgres pgbackrest --config="$CONFIG_FILE" --stanza="$STANZA" check

target_time="$(sudo -u postgres psql -X -Atqc "
  SELECT to_char(
    clock_timestamp() AT TIME ZONE 'UTC',
    'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"'
  );
" postgres)"
sleep 2

sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
  --dbname="$PROBE_DATABASE" \
  --set=marker="$after_marker" <<'SQL'
INSERT INTO public.pitr_markers (marker) VALUES (:'marker');
SQL
sudo -u postgres psql -X -Atqc 'SELECT pg_switch_wal()' postgres >/dev/null
sudo -u postgres pgbackrest --config="$CONFIG_FILE" --stanza="$STANZA" check

markers_json="$(sudo -u postgres psql -X -Atqc "
  SELECT json_agg(marker ORDER BY marker)
  FROM public.pitr_markers;
" "$PROBE_DATABASE")"
archiver_json="$(sudo -u postgres psql -X -Atqc "
  SELECT json_build_object(
    'archived_count', archived_count,
    'last_archived_wal', last_archived_wal,
    'last_archived_time', last_archived_time,
    'failed_count', failed_count,
    'last_failed_wal', last_failed_wal,
    'last_failed_time', last_failed_time
  )
  FROM pg_stat_archiver;
" postgres)"

evidence_json="$(jq -n \
  --arg generated_at "$(date -u +%FT%TZ)" \
  --arg hostname "$(hostname -f)" \
  --arg backup_set "$backup_set" \
  --arg target_time "$target_time" \
  --arg probe_database "$PROBE_DATABASE" \
  --arg before_marker "$before_marker" \
  --arg after_marker "$after_marker" \
  --argjson markers "$markers_json" \
  --argjson archiver "$archiver_json" \
  '{
    generated_at: $generated_at,
    hostname: $hostname,
    backup_set: $backup_set,
    target_time: $target_time,
    probe_database: $probe_database,
    before_marker: $before_marker,
    after_marker: $after_marker,
    source_markers: $markers,
    archiver: $archiver
  }
  | .accepted = (
      (.source_markers | index($before_marker) != null)
      and (.source_markers | index($after_marker) != null)
      and (.archiver.archived_count > 0)
      and (.archiver.last_archived_wal != null)
    )')"

output_parent="$(dirname "$JSON_OUT")"
if [[ ! -d "$output_parent" ]]; then
  echo "Evidence parent directory does not exist: ${output_parent}" >&2
  exit 1
fi
umask 077
printf '%s\n' "$evidence_json" > "$JSON_OUT"
printf '%s\n' "$evidence_json"

if ! jq -e '.accepted == true' <<<"$evidence_json" >/dev/null; then
  echo "PITR witness creation failed acceptance." >&2
  exit 1
fi
