#!/usr/bin/env bash
# Configure encrypted pgBackRest backups and WAL archiving to independent
# S3-compatible storage. Secrets are read from a root-owned file, never args.

set -euo pipefail

ENV_FILE=""
STANZA="rtbcat"
MARKER_FILE="/etc/rtbcat/database-host.env"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/configure_pgbackrest_s3.sh --env-file <path>

The env file must be root-owned mode 0600/0400 and define the variables shown
in pgbackrest-s3.env.example. The command creates a stanza, verifies archive
push, and takes an initial full backup. It will fail closed on any error.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:?--env-file requires a value}"
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

required_vars=(
  PGBACKREST_S3_BUCKET
  PGBACKREST_S3_ENDPOINT
  PGBACKREST_S3_REGION
  PGBACKREST_S3_KEY
  PGBACKREST_S3_KEY_SECRET
  PGBACKREST_CIPHER_PASS
)
for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" || "${!name}" == "replace-me"* ]]; then
    echo "Missing or placeholder value: $name" >&2
    exit 1
  fi
done
if [[ ${#PGBACKREST_CIPHER_PASS} -lt 32 ]]; then
  echo "PGBACKREST_CIPHER_PASS must be at least 32 characters." >&2
  exit 1
fi

PGBACKREST_S3_URI_STYLE="${PGBACKREST_S3_URI_STYLE:-host}"
PGBACKREST_REPO_PATH="${PGBACKREST_REPO_PATH:-/rtbcat/postgresql}"
PGBACKREST_RETENTION_FULL="${PGBACKREST_RETENTION_FULL:-2}"
PGBACKREST_RETENTION_DIFF="${PGBACKREST_RETENTION_DIFF:-6}"
if [[ "$PGBACKREST_S3_URI_STYLE" != "host" && "$PGBACKREST_S3_URI_STYLE" != "path" ]]; then
  echo "PGBACKREST_S3_URI_STYLE must be host or path." >&2
  exit 1
fi
if ! [[ "$PGBACKREST_RETENTION_FULL" =~ ^[1-9][0-9]*$ ]] || \
   ! [[ "$PGBACKREST_RETENTION_DIFF" =~ ^[1-9][0-9]*$ ]]; then
  echo "Retention values must be positive integers." >&2
  exit 1
fi

install -d -o postgres -g postgres -m 0750 /etc/pgbackrest /var/log/pgbackrest /var/spool/pgbackrest
tmp_config="$(mktemp)"
cleanup() {
  rm -f -- "$tmp_config"
}
trap cleanup EXIT
chmod 0600 "$tmp_config"
cat > "$tmp_config" <<EOF
[global]
repo1-type=s3
repo1-path=${PGBACKREST_REPO_PATH}
repo1-s3-bucket=${PGBACKREST_S3_BUCKET}
repo1-s3-endpoint=${PGBACKREST_S3_ENDPOINT}
repo1-s3-region=${PGBACKREST_S3_REGION}
repo1-s3-uri-style=${PGBACKREST_S3_URI_STYLE}
repo1-s3-key=${PGBACKREST_S3_KEY}
repo1-s3-key-secret=${PGBACKREST_S3_KEY_SECRET}
repo1-cipher-type=aes-256-cbc
repo1-cipher-pass=${PGBACKREST_CIPHER_PASS}
repo1-retention-full=${PGBACKREST_RETENTION_FULL}
repo1-retention-diff=${PGBACKREST_RETENTION_DIFF}
archive-async=y
start-fast=y
process-max=4
spool-path=/var/spool/pgbackrest
log-level-console=info
log-level-file=detail

[${STANZA}]
pg1-path=/var/lib/postgresql/15/main
EOF
install -o postgres -g postgres -m 0600 "$tmp_config" /etc/pgbackrest/pgbackrest.conf

cat > /etc/postgresql/15/main/conf.d/30-pgbackrest.conf <<EOF
archive_mode = on
archive_command = 'pgbackrest --stanza=${STANZA} archive-push %p'
archive_timeout = '60s'
restore_command = 'pgbackrest --stanza=${STANZA} archive-get %f "%p"'
EOF

systemctl restart postgresql
sudo -u postgres pgbackrest --stanza="$STANZA" stanza-create
sudo -u postgres pgbackrest --stanza="$STANZA" check
sudo -u postgres pgbackrest --stanza="$STANZA" --type=full backup
sudo -u postgres pgbackrest --stanza="$STANZA" info

cat > /etc/systemd/system/rtbcat-pgbackrest-full.service <<EOF
[Unit]
Description=RTBcat weekly pgBackRest full backup
After=postgresql.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=postgres
Group=postgres
ExecStart=/usr/bin/pgbackrest --stanza=${STANZA} --type=full backup
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
ExecStart=/usr/bin/pgbackrest --stanza=${STANZA} --type=diff backup
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
ExecStart=/usr/bin/pgbackrest --stanza=${STANZA} check
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
systemctl enable --now \
  rtbcat-pgbackrest-full.timer \
  rtbcat-pgbackrest-diff.timer \
  rtbcat-pgbackrest-check.timer
systemctl list-timers 'rtbcat-pgbackrest-*' --no-pager

unset PGBACKREST_S3_KEY PGBACKREST_S3_KEY_SECRET PGBACKREST_CIPHER_PASS
echo "pgBackRest stanza, WAL archive check, initial full backup, and backup timers succeeded."
