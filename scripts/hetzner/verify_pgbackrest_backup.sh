#!/usr/bin/env bash
# Verify the live pgBackRest repository, WAL archive path, successful full
# backup, and recurring systemd schedule without exposing repository secrets.

set -euo pipefail

JSON_OUT=""
STANZA="rtbcat"
CONFIG_FILE="/etc/pgbackrest/pgbackrest.conf"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/verify_pgbackrest_backup.sh [--json-out <path>]

Runs pgBackRest check, validates a successful full backup and WAL archive
activity, and requires the daily check plus weekly-full/daily-differential
timers to be enabled. The optional JSON evidence contains metadata only, never
repository credentials or the encryption passphrase.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json-out)
      JSON_OUT="${2:?--json-out requires a value}"
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
if [[ ! -r "$CONFIG_FILE" ]]; then
  echo "pgBackRest configuration is missing: ${CONFIG_FILE}" >&2
  exit 1
fi

sudo -u postgres pgbackrest --config="$CONFIG_FILE" --stanza="$STANZA" check
info_json="$(sudo -u postgres pgbackrest \
  --config="$CONFIG_FILE" --stanza="$STANZA" --output=json info)"
archive_json="$(sudo -u postgres psql -X -Atqc "
  SELECT json_build_object(
    'archive_mode', current_setting('archive_mode'),
    'archive_command', current_setting('archive_command'),
    'archived_count', archived_count,
    'last_archived_wal', last_archived_wal,
    'last_archived_time', last_archived_time,
    'failed_count', failed_count,
    'last_failed_wal', last_failed_wal,
    'last_failed_time', last_failed_time
  )
  FROM pg_stat_archiver;
")"

unit_state() {
  local unit="$1"
  systemctl is-enabled "$unit" 2>/dev/null || true
}

check_timer_state="$(unit_state rtbcat-pgbackrest-check.timer)"
full_timer_state="$(unit_state rtbcat-pgbackrest-full.timer)"
diff_timer_state="$(unit_state rtbcat-pgbackrest-diff.timer)"
full_service_state="$(systemctl is-active rtbcat-pgbackrest-full.service 2>/dev/null || true)"
diff_service_state="$(systemctl is-active rtbcat-pgbackrest-diff.service 2>/dev/null || true)"

evidence_json="$(jq -n \
  --arg generated_at "$(date -u +%FT%TZ)" \
  --arg hostname "$(hostname -f)" \
  --arg pgbackrest_version "$(pgbackrest version | awk '{print $2}')" \
  --arg check_timer "$check_timer_state" \
  --arg full_timer "$full_timer_state" \
  --arg diff_timer "$diff_timer_state" \
  --arg full_service "$full_service_state" \
  --arg diff_service "$diff_service_state" \
  --argjson archive "$archive_json" \
  --argjson info "$info_json" \
  '
    def good_full:
      [.[] | .backup[]? | select(.type == "full" and (.error == false))]
      | sort_by(.timestamp.stop)
      | last;
    {
      generated_at: $generated_at,
      hostname: $hostname,
      pgbackrest_version: $pgbackrest_version,
      archive: $archive,
      repository: {
        stanza: ($info[0].name // null),
        status: ($info[0].status // null),
        cipher: ($info[0].cipher // null),
        archive: ($info[0].archive // []),
        latest_successful_full: ($info | good_full)
      },
      systemd: {
        check_timer: $check_timer,
        full_timer: $full_timer,
        diff_timer: $diff_timer,
        full_service: $full_service,
        diff_service: $diff_service
      }
    }
    | .accepted = (
        .archive.archive_mode == "on"
        and (.archive.archived_count > 0)
        and (.archive.last_archived_wal != null)
        and (.repository.latest_successful_full != null)
        and (.repository.status.code == 0)
        and (.repository.cipher == "aes-256-cbc")
        and (.systemd.check_timer == "enabled")
        and (.systemd.full_timer == "enabled")
        and (.systemd.diff_timer == "enabled")
      )
  ')"

if [[ -n "$JSON_OUT" ]]; then
  output_parent="$(dirname "$JSON_OUT")"
  if [[ ! -d "$output_parent" ]]; then
    echo "Evidence parent directory does not exist: ${output_parent}" >&2
    exit 1
  fi
  umask 077
  printf '%s\n' "$evidence_json" > "$JSON_OUT"
fi
printf '%s\n' "$evidence_json"

if ! jq -e '.accepted == true' <<<"$evidence_json" >/dev/null; then
  echo "pgBackRest backup/WAL acceptance failed." >&2
  exit 1
fi
