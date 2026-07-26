#!/usr/bin/env bash
# Configure encrypted pgBackRest backups and WAL archiving to independent
# S3-compatible storage. Secrets are read from a root-owned file, never args.

set -euo pipefail

ENV_FILE=""
START_FULL_BACKUP="false"
ENABLE_BACKUP_TIMERS="false"
STANZA="rtbcat"
MARKER_FILE="/etc/rtbcat/database-host.env"
CONFIG_FILE="/etc/pgbackrest/pgbackrest.conf"
POSTGRES_ARCHIVE_CONFIG="/etc/postgresql/15/main/conf.d/30-pgbackrest.conf"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/configure_pgbackrest_s3.sh \
  --env-file <path> [--start-full-backup | --enable-backup-timers]

The env file must be root-owned mode 0600/0400 and define the variables shown
in pgbackrest-s3.env.example.

The first invocation configures the encrypted repository, enables WAL
archiving, proves archive push/check, and installs systemd units. Add
--start-full-backup to launch the production-sized initial full backup as a
non-blocking systemd job. Monitor it with:

  systemctl status rtbcat-pgbackrest-full.service
  journalctl -fu rtbcat-pgbackrest-full.service

Only after that job succeeds, rerun with --enable-backup-timers. This refuses
to enable the weekly-full and daily-differential timers unless the repository
contains a successful full backup.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:?--env-file requires a value}"
      shift 2
      ;;
    --start-full-backup)
      START_FULL_BACKUP="true"
      shift
      ;;
    --enable-backup-timers)
      ENABLE_BACKUP_TIMERS="true"
      shift
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
if [[ "$START_FULL_BACKUP" == "true" && "$ENABLE_BACKUP_TIMERS" == "true" ]]; then
  echo "Start the initial full backup and enable recurring timers in separate invocations." >&2
  exit 1
fi
if [[ -z "$ENV_FILE" || ! -f "$ENV_FILE" ]]; then
  echo "A pgBackRest env file is required." >&2
  usage >&2
  exit 1
fi
if [[ ! -f "$MARKER_FILE" ]]; then
  echo "Database host marker is absent; run bootstrap_database_host.sh first." >&2
  exit 1
fi
env_owner="$(stat -c '%U' "$ENV_FILE")"
env_mode="$(stat -c '%a' "$ENV_FILE")"
if [[ "$env_owner" != "root" || ( "$env_mode" != "600" && "$env_mode" != "400" ) ]]; then
  echo "Env file must be root-owned mode 0600 or 0400." >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a
# shellcheck source=/dev/null
source "$MARKER_FILE"

unset_secrets() {
  unset PGBACKREST_S3_KEY PGBACKREST_S3_KEY_SECRET PGBACKREST_CIPHER_PASS
}
trap unset_secrets EXIT

PGBACKREST_REPO_TYPE="${PGBACKREST_REPO_TYPE:-s3}"
required_vars=(PGBACKREST_CIPHER_PASS)
case "$PGBACKREST_REPO_TYPE" in
  gcs)
    required_vars+=(
      PGBACKREST_GCS_BUCKET
      PGBACKREST_GCS_KEY_FILE
    )
    ;;
  s3)
    required_vars+=(
      PGBACKREST_S3_BUCKET
      PGBACKREST_S3_ENDPOINT
      PGBACKREST_S3_REGION
      PGBACKREST_S3_KEY
      PGBACKREST_S3_KEY_SECRET
    )
    ;;
  *)
    echo "PGBACKREST_REPO_TYPE must be gcs or s3." >&2
    exit 1
    ;;
esac
for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" || "${!name}" == "replace-me"* ]]; then
    echo "Missing or placeholder value: $name" >&2
    exit 1
  fi
  if [[ "${!name}" == *$'\n'* || "${!name}" == *$'\r'* ]]; then
    echo "Newlines are not allowed in ${name}." >&2
    exit 1
  fi
done
if [[ ${#PGBACKREST_CIPHER_PASS} -lt 32 ]]; then
  echo "PGBACKREST_CIPHER_PASS must be at least 32 characters." >&2
  exit 1
fi
if [[ "$PGBACKREST_REPO_TYPE" == "gcs" ]]; then
  if ! [[ "$PGBACKREST_GCS_BUCKET" =~ ^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$ ]]; then
    echo "PGBACKREST_GCS_BUCKET is not a safe GCS bucket name." >&2
    exit 1
  fi
  if ! [[ "$PGBACKREST_GCS_KEY_FILE" =~ ^/[A-Za-z0-9._/-]+$ ]] || \
     [[ ! -f "$PGBACKREST_GCS_KEY_FILE" ]]; then
    echo "PGBACKREST_GCS_KEY_FILE must be an existing safe absolute path." >&2
    exit 1
  fi
  gcs_key_owner="$(stat -c '%U' "$PGBACKREST_GCS_KEY_FILE")"
  gcs_key_mode="$(stat -c '%a' "$PGBACKREST_GCS_KEY_FILE")"
  if [[ "$gcs_key_owner" != "postgres" || "$gcs_key_mode" != "600" ]]; then
    echo "The GCS service key must be postgres-owned mode 0600." >&2
    exit 1
  fi
  if ! jq -e \
    '.type == "service_account"
     and (.project_id | type == "string")
     and (.client_email | type == "string")
     and (.private_key | startswith("-----BEGIN PRIVATE KEY-----"))' \
    "$PGBACKREST_GCS_KEY_FILE" >/dev/null; then
    echo "The GCS service key is not a valid service-account JSON file." >&2
    exit 1
  fi
else
  if ! [[ "$PGBACKREST_S3_BUCKET" =~ ^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$ ]]; then
    echo "PGBACKREST_S3_BUCKET is not a safe S3-compatible bucket name." >&2
    exit 1
  fi
  if ! [[ "$PGBACKREST_S3_ENDPOINT" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]{1,5})?$ ]]; then
    echo "PGBACKREST_S3_ENDPOINT must be a hostname with no scheme or path." >&2
    exit 1
  fi
  if ! [[ "$PGBACKREST_S3_REGION" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$ ]]; then
    echo "PGBACKREST_S3_REGION is invalid." >&2
    exit 1
  fi
fi

PGBACKREST_S3_URI_STYLE="${PGBACKREST_S3_URI_STYLE:-host}"
PGBACKREST_REPO_PATH="${PGBACKREST_REPO_PATH:-/rtbcat/postgresql}"
PGBACKREST_RETENTION_FULL="${PGBACKREST_RETENTION_FULL:-2}"
PGBACKREST_RETENTION_DIFF="${PGBACKREST_RETENTION_DIFF:-6}"
if [[ "$PGBACKREST_S3_URI_STYLE" != "host" && "$PGBACKREST_S3_URI_STYLE" != "path" ]]; then
  echo "PGBACKREST_S3_URI_STYLE must be host or path." >&2
  exit 1
fi
if ! [[ "$PGBACKREST_REPO_PATH" =~ ^/[A-Za-z0-9._/-]+$ ]] || \
   [[ "$PGBACKREST_REPO_PATH" == *"//"* || "$PGBACKREST_REPO_PATH" == *"/../"* ]]; then
  echo "PGBACKREST_REPO_PATH must be a safe absolute repository prefix." >&2
  exit 1
fi
if ! [[ "$PGBACKREST_RETENTION_FULL" =~ ^[1-9][0-9]*$ ]] || \
   ! [[ "$PGBACKREST_RETENTION_DIFF" =~ ^[1-9][0-9]*$ ]]; then
  echo "Retention values must be positive integers." >&2
  exit 1
fi

install -d -o postgres -g postgres -m 0750 \
  /etc/pgbackrest /etc/pgbackrest/conf.d /var/log/pgbackrest /var/spool/pgbackrest
tmp_config="$(mktemp)"
tmp_archive_config="$(mktemp)"
cleanup_files() {
  rm -f -- "$tmp_config" "$tmp_archive_config"
}
trap 'cleanup_files; unset_secrets' EXIT
chmod 0600 "$tmp_config" "$tmp_archive_config"

cat > "$tmp_config" <<'EOF'
[global]
EOF
if [[ "$PGBACKREST_REPO_TYPE" == "gcs" ]]; then
  cat >> "$tmp_config" <<EOF
repo1-type=gcs
repo1-path=${PGBACKREST_REPO_PATH}
repo1-gcs-bucket=${PGBACKREST_GCS_BUCKET}
repo1-gcs-key-type=service
repo1-gcs-key=${PGBACKREST_GCS_KEY_FILE}
EOF
else
  cat >> "$tmp_config" <<EOF
repo1-type=s3
repo1-path=${PGBACKREST_REPO_PATH}
repo1-s3-bucket=${PGBACKREST_S3_BUCKET}
repo1-s3-endpoint=${PGBACKREST_S3_ENDPOINT}
repo1-s3-region=${PGBACKREST_S3_REGION}
repo1-s3-uri-style=${PGBACKREST_S3_URI_STYLE}
repo1-s3-key=${PGBACKREST_S3_KEY}
repo1-s3-key-secret=${PGBACKREST_S3_KEY_SECRET}
EOF
fi
cat >> "$tmp_config" <<EOF
repo1-cipher-type=aes-256-cbc
repo1-cipher-pass=${PGBACKREST_CIPHER_PASS}
repo1-retention-full=${PGBACKREST_RETENTION_FULL}
repo1-retention-diff=${PGBACKREST_RETENTION_DIFF}
repo1-bundle=y
repo1-block=y
archive-async=y
start-fast=y
resume=y
process-max=4
compress-type=zst
compress-level=3
spool-path=/var/spool/pgbackrest
log-level-console=info
log-level-file=detail

[${STANZA}]
pg1-path=/var/lib/postgresql/15/main
EOF

if [[ ! -f "$CONFIG_FILE" ]] || ! cmp -s "$tmp_config" "$CONFIG_FILE"; then
  install -o postgres -g postgres -m 0600 "$tmp_config" "$CONFIG_FILE"
fi

# Create/validate the repository stanza before PostgreSQL starts invoking the
# archive command. This avoids creating an avoidable archive failure window.
sudo -u postgres pgbackrest --config="$CONFIG_FILE" --stanza="$STANZA" stanza-create

cat > "$tmp_archive_config" <<EOF
archive_mode = on
archive_command = 'pgbackrest --config=${CONFIG_FILE} --stanza=${STANZA} archive-push %p'
archive_timeout = '60s'
restore_command = 'pgbackrest --config=${CONFIG_FILE} --stanza=${STANZA} archive-get %f "%p"'
EOF

archive_config_changed="false"
if [[ ! -f "$POSTGRES_ARCHIVE_CONFIG" ]] || \
   ! cmp -s "$tmp_archive_config" "$POSTGRES_ARCHIVE_CONFIG"; then
  install -o root -g root -m 0644 "$tmp_archive_config" "$POSTGRES_ARCHIVE_CONFIG"
  archive_config_changed="true"
fi

archive_mode="$(sudo -u postgres psql -X -Atqc 'SHOW archive_mode')"
# pgBackRest reads its repository configuration for every invocation, so a
# repository-only change does not justify interrupting PostgreSQL.
if [[ "$archive_config_changed" == "true" || "$archive_mode" != "on" ]]; then
  systemctl restart postgresql
fi
if [[ "$(sudo -u postgres psql -X -Atqc 'SHOW archive_mode')" != "on" ]]; then
  echo "PostgreSQL did not enable archive_mode." >&2
  exit 1
fi

sudo -u postgres pgbackrest --config="$CONFIG_FILE" --stanza="$STANZA" check

cat > /etc/systemd/system/rtbcat-pgbackrest-full.service <<EOF
[Unit]
Description=RTBcat weekly pgBackRest full backup
After=postgresql.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=postgres
Group=postgres
ExecStart=/usr/bin/pgbackrest --config=${CONFIG_FILE} --stanza=${STANZA} --type=full backup
TimeoutStartSec=infinity
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF

cat > /etc/systemd/system/rtbcat-pgbackrest-full.timer <<'EOF'
[Unit]
Description=Schedule RTBcat weekly pgBackRest full backup

[Timer]
OnCalendar=Sun *-*-* 01:15:00 UTC
RandomizedDelaySec=15m
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/rtbcat-pgbackrest-diff.service <<EOF
[Unit]
Description=RTBcat daily pgBackRest differential backup
After=postgresql.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=postgres
Group=postgres
ExecStart=/usr/bin/pgbackrest --config=${CONFIG_FILE} --stanza=${STANZA} --type=diff backup
TimeoutStartSec=infinity
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF

cat > /etc/systemd/system/rtbcat-pgbackrest-diff.timer <<'EOF'
[Unit]
Description=Schedule RTBcat daily pgBackRest differential backup

[Timer]
OnCalendar=Mon..Sat *-*-* 02:15:00 UTC
RandomizedDelaySec=15m
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/rtbcat-pgbackrest-check.service <<EOF
[Unit]
Description=RTBcat pgBackRest archive and repository check
After=postgresql.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=postgres
Group=postgres
ExecStart=/usr/bin/pgbackrest --config=${CONFIG_FILE} --stanza=${STANZA} check
EOF

cat > /etc/systemd/system/rtbcat-pgbackrest-check.timer <<'EOF'
[Unit]
Description=Schedule RTBcat pgBackRest archive and repository check

[Timer]
OnCalendar=*-*-* 06:15:00 UTC
RandomizedDelaySec=10m
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now rtbcat-pgbackrest-check.timer

unit_is_running() {
  local active_state
  active_state="$(systemctl show "$1" --property=ActiveState --value 2>/dev/null || true)"
  case "$active_state" in
    active|activating|reloading|deactivating)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if [[ "$START_FULL_BACKUP" == "true" ]]; then
  if unit_is_running rtbcat-pgbackrest-full.service || \
     unit_is_running rtbcat-pgbackrest-diff.service; then
    echo "A pgBackRest backup service is already active; refusing a concurrent start." >&2
    exit 1
  fi
  systemctl start --no-block rtbcat-pgbackrest-full.service
  echo "Initial full backup started as rtbcat-pgbackrest-full.service."
elif [[ "$ENABLE_BACKUP_TIMERS" == "true" ]]; then
  info_json="$(sudo -u postgres pgbackrest \
    --config="$CONFIG_FILE" --stanza="$STANZA" --output=json info)"
  if ! jq -e \
    'any(.[]; any(.backup[]?; .type == "full" and (.error == false)))' \
    <<<"$info_json" >/dev/null; then
    echo "No successful full backup exists; refusing to enable recurring backup timers." >&2
    exit 1
  fi
  systemctl enable --now \
    rtbcat-pgbackrest-full.timer \
    rtbcat-pgbackrest-diff.timer
  echo "Recurring full and differential backup timers enabled."
else
  echo "Repository/WAL configuration passed. The initial full backup was not started."
fi

systemctl list-timers 'rtbcat-pgbackrest-*' --all --no-pager
sudo -u postgres pgbackrest --config="$CONFIG_FILE" --stanza="$STANZA" info
