#!/usr/bin/env bash
# Prepare a fresh Hetzner database host for the RTBcat restore rehearsal.
# This script never formats a device and refuses an already-populated volume.

set -euo pipefail

REQUIRED_POSTGRES_VERSION="15.17"
REQUIRED_POSTGRES_VERSION_NUM="150017"
POSTGRES_PACKAGE_VERSION="15.17-1.pgdg24.04+1"
POSTGRES_SERVER_SHA256="db186eb11b5af796d77a46ca411861e232c8f10441ddbde0b4c18d71617f34c4"
POSTGRES_CLIENT_SHA256="a2f145d29318fbf92d3ded83652c01e12d68277fcfedbb60f74aa05ea1207165"
VOLUME_ID=""
PRIVATE_IP=""
APP_PRIVATE_IP=""
DATABASE_NAME="rtbcat_serving"
DATABASE_OWNER="rtbcat_serving"
PASSWORD_FILE=""
VERIFY_ONLY="false"
DATA_MOUNT="/var/lib/postgresql"
MARKER_FILE="/etc/rtbcat/database-host.env"
POSTGRESQL_CONF="/etc/postgresql/15/main/postgresql.conf"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/bootstrap_database_host.sh [options]

Required for first run:
  --volume-id <id>             Hetzner Volume ID from Terraform output.
  --private-ip <ip>            Database private IP (default plan: 10.60.1.20).
  --app-private-ip <ip>        App private IP allowed to TCP/5432.
  --password-file <path>       Root-readable mode-0600 file containing only the
                               initial application database password.

Optional:
  --database <name>            Application database (default: rtbcat_serving).
  --owner <role>               Application role (default: rtbcat_serving).
  --verify-only                Verify an already-configured host without changes.
  --help                       Show this help.

The Volume must already be XFS-formatted by Terraform. This script will never
run mkfs. It pins PostgreSQL 15.17 for the first restore rehearsal.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --volume-id)
      VOLUME_ID="${2:?--volume-id requires a value}"
      shift 2
      ;;
    --private-ip)
      PRIVATE_IP="${2:?--private-ip requires a value}"
      shift 2
      ;;
    --app-private-ip)
      APP_PRIVATE_IP="${2:?--app-private-ip requires a value}"
      shift 2
      ;;
    --database)
      DATABASE_NAME="${2:?--database requires a value}"
      shift 2
      ;;
    --owner)
      DATABASE_OWNER="${2:?--owner requires a value}"
      shift 2
      ;;
    --password-file)
      PASSWORD_FILE="${2:?--password-file requires a value}"
      shift 2
      ;;
    --verify-only)
      VERIFY_ONLY="true"
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

verify_host() {
  local actual_version actual_version_num expected_volume mount_source listeners
  actual_version="$(sudo -u postgres psql -X -Atqc 'SHOW server_version')"
  actual_version_num="$(sudo -u postgres psql -X -Atqc 'SHOW server_version_num')"
  if [[ "$actual_version_num" != "$REQUIRED_POSTGRES_VERSION_NUM" ]]; then
    echo "Expected PostgreSQL ${REQUIRED_POSTGRES_VERSION}, found ${actual_version}." >&2
    return 1
  fi
  mount_source="$(findmnt -n -o SOURCE --target "$DATA_MOUNT")"
  expected_volume="/dev/disk/by-id/scsi-0HC_Volume_${VOLUME_ID}"
  if [[ -z "$VOLUME_ID" || ! -b "$expected_volume" ]] || \
     [[ "$(readlink -f "$mount_source")" != "$(readlink -f "$expected_volume")" ]]; then
    echo "PostgreSQL is not mounted from the expected Hetzner Volume ${VOLUME_ID}: ${mount_source}." >&2
    return 1
  fi
  listeners="$(sudo -u postgres psql -X -Atqc 'SHOW listen_addresses')"
  if [[ "$listeners" != "127.0.0.1,${PRIVATE_IP}" ]]; then
    echo "Unexpected listen_addresses: $listeners" >&2
    return 1
  fi
  sudo -u postgres psql -X -Atqc \
    "SELECT current_setting('server_version'), current_setting('data_checksums'), datcollate, datctype FROM pg_database WHERE datname = current_database();"
  pgbackrest version
  if ! ufw status | grep -qx 'Status: active'; then
    echo "UFW is not active." >&2
    return 1
  fi
  ufw status verbose
}

if [[ -f "$MARKER_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$MARKER_FILE"
  PRIVATE_IP="${RTBCAT_DATABASE_PRIVATE_IP:-}"
  VOLUME_ID="${RTBCAT_VOLUME_ID:-}"
  if [[ -z "$PRIVATE_IP" || -z "$VOLUME_ID" ]]; then
    echo "Database marker does not contain the private IP and Volume ID." >&2
    exit 1
  fi
  verify_host
  echo "Database host is already configured and verified."
  exit 0
fi

if [[ "$VERIFY_ONLY" == "true" ]]; then
  echo "No database marker exists; first-run bootstrap is incomplete." >&2
  exit 1
fi
if [[ -z "$VOLUME_ID" || -z "$PRIVATE_IP" || -z "$APP_PRIVATE_IP" || -z "$PASSWORD_FILE" ]]; then
  echo "Missing a required first-run argument." >&2
  usage >&2
  exit 1
fi
if ! [[ "$VOLUME_ID" =~ ^[0-9]+$ ]]; then
  echo "Volume ID must be numeric." >&2
  exit 1
fi
if ! [[ "$PRIVATE_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || \
   ! [[ "$APP_PRIVATE_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Private IP arguments must be IPv4 addresses." >&2
  exit 1
fi
if ! [[ "$DATABASE_NAME" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || \
   ! [[ "$DATABASE_OWNER" =~ ^[a-z_][a-z0-9_]{0,62}$ ]]; then
  echo "Database and owner names must be safe lowercase PostgreSQL identifiers." >&2
  exit 1
fi
if [[ ! -f "$PASSWORD_FILE" ]]; then
  echo "Password file does not exist: $PASSWORD_FILE" >&2
  exit 1
fi
password_owner="$(stat -c '%U' "$PASSWORD_FILE")"
password_mode="$(stat -c '%a' "$PASSWORD_FILE")"
if [[ "$password_owner" != "root" || ( "$password_mode" != "600" && "$password_mode" != "400" ) ]]; then
  echo "Password file must be root-owned mode 0600 or 0400." >&2
  exit 1
fi
database_password="$(<"$PASSWORD_FILE")"
if [[ ${#database_password} -lt 24 || "$database_password" == *$'\n'* ]]; then
  echo "Database password must be a single line of at least 24 characters." >&2
  exit 1
fi

# shellcheck source=/dev/null
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_CODENAME:-}" != "noble" ]]; then
  echo "Expected Ubuntu 24.04 (noble), found ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi
if [[ "$(dpkg --print-architecture)" != "amd64" ]]; then
  echo "Expected amd64 architecture." >&2
  exit 1
fi
memory_kib="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
if [[ -z "$memory_kib" ]] || (( memory_kib < 14 * 1024 * 1024 )); then
  echo "The baseline PostgreSQL tuning requires a 16 GiB-class host (at least 14 GiB visible RAM)." >&2
  exit 1
fi

volume_device="/dev/disk/by-id/scsi-0HC_Volume_${VOLUME_ID}"
if [[ ! -b "$volume_device" ]]; then
  echo "Hetzner Volume device is absent: $volume_device" >&2
  exit 1
fi
root_device="$(findmnt -n -o SOURCE /)"
resolved_volume="$(readlink -f "$volume_device")"
resolved_root="$(readlink -f "$root_device")"
if [[ "$resolved_volume" == "$resolved_root" ]]; then
  echo "Refusing to use the root device as the PostgreSQL Volume." >&2
  exit 1
fi
if [[ "$(blkid -s TYPE -o value "$volume_device")" != "xfs" ]]; then
  echo "Volume is not XFS-formatted by Terraform; refusing to format it." >&2
  exit 1
fi

existing_mount="$(findmnt -n -o TARGET --source "$volume_device" 2>/dev/null || true)"
if [[ -n "$existing_mount" && "$existing_mount" != "$DATA_MOUNT" ]]; then
  umount "$existing_mount"
fi
install -d -o root -g root -m 0755 "$DATA_MOUNT"
if findmnt --mountpoint "$DATA_MOUNT" >/dev/null 2>&1; then
  current_source="$(findmnt -n -o SOURCE --mountpoint "$DATA_MOUNT")"
  if [[ "$(readlink -f "$current_source")" != "$resolved_volume" ]]; then
    echo "$DATA_MOUNT is already mounted from another device: $current_source" >&2
    exit 1
  fi
else
  volume_uuid="$(blkid -s UUID -o value "$volume_device")"
  if [[ -z "$volume_uuid" ]]; then
    echo "Could not read the Volume UUID." >&2
    exit 1
  fi
  cp --no-clobber /etc/fstab "/etc/fstab.pre-rtbcat-${VOLUME_ID}"
  sed -i \
    -e "\\|HC_Volume_${VOLUME_ID}|d" \
    -e "\\|UUID=${volume_uuid} |d" \
    /etc/fstab
  echo "UUID=${volume_uuid} ${DATA_MOUNT} xfs defaults,noatime,nofail,x-systemd.device-timeout=30s 0 2" >> /etc/fstab
  systemctl daemon-reload
  mount "$DATA_MOUNT"
fi

if find "$DATA_MOUNT" -mindepth 1 -maxdepth 1 ! -name lost+found -print -quit | grep -q .; then
  echo "The PostgreSQL Volume is not empty; refusing first-run bootstrap." >&2
  exit 1
fi

install -d -o root -g root -m 0755 /etc/postgresql-common
cat > /etc/postgresql-common/createcluster.conf <<'EOF'
create_main_cluster = false
EOF

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl locales postgresql-common
install -d -o root -g root -m 0755 /usr/share/postgresql-common/pgdg
curl -fsSL --fail \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc \
  -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
cat > /etc/apt/sources.list.d/pgdg.sources <<EOF
Types: deb
URIs: https://apt.postgresql.org/pub/repos/apt
Suites: noble-pgdg
Architectures: amd64
Components: main
Signed-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
EOF

apt-get update
package_dir="$(mktemp -d)"
cleanup_packages() {
  rm -rf -- "$package_dir"
}
trap cleanup_packages EXIT
server_package="${package_dir}/postgresql-15.deb"
client_package="${package_dir}/postgresql-client-15.deb"
package_base_url="https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-15"
curl -fsSL --fail \
  "${package_base_url}/postgresql-15_${POSTGRES_PACKAGE_VERSION}_amd64.deb" \
  -o "$server_package"
curl -fsSL --fail \
  "${package_base_url}/postgresql-client-15_${POSTGRES_PACKAGE_VERSION}_amd64.deb" \
  -o "$client_package"
printf '%s  %s\n' "$POSTGRES_SERVER_SHA256" "$server_package" | sha256sum --check --strict
printf '%s  %s\n' "$POSTGRES_CLIENT_SHA256" "$client_package" | sha256sum --check --strict
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  "$client_package" \
  "$server_package" \
  jq pgbackrest openssl
if [[ "$(dpkg-query -W -f='${Version}' postgresql-15)" != "$POSTGRES_PACKAGE_VERSION" ]] || \
   [[ "$(dpkg-query -W -f='${Version}' postgresql-client-15)" != "$POSTGRES_PACKAGE_VERSION" ]]; then
  echo "PostgreSQL package version drifted from ${POSTGRES_PACKAGE_VERSION}; refusing to continue." >&2
  exit 1
fi
apt-mark hold postgresql-15 postgresql-client-15

locale-gen en_US.UTF-8
install -d -o postgres -g postgres -m 0700 "$DATA_MOUNT/15"
pg_createcluster 15 main \
  --datadir="$DATA_MOUNT/15/main" \
  --locale=en_US.UTF-8 \
  --encoding=UTF8 \
  --start-conf=auto \
  -- --data-checksums

install -d -o postgres -g postgres -m 0700 /etc/postgresql/15/main/tls
openssl req -x509 -nodes -newkey rsa:3072 -sha256 -days 397 \
  -subj "/CN=${PRIVATE_IP}" \
  -addext "subjectAltName=IP:${PRIVATE_IP}" \
  -keyout /etc/postgresql/15/main/tls/server.key \
  -out /etc/postgresql/15/main/tls/server.crt
chown postgres:postgres /etc/postgresql/15/main/tls/server.key /etc/postgresql/15/main/tls/server.crt
chmod 0600 /etc/postgresql/15/main/tls/server.key
chmod 0644 /etc/postgresql/15/main/tls/server.crt

install -d -o root -g root -m 0755 /etc/postgresql/15/main/conf.d
cat > /etc/postgresql/15/main/conf.d/20-rtbcat.conf <<EOF
# Rehearsal baseline. Re-tune only from measured target evidence.
listen_addresses = '127.0.0.1,${PRIVATE_IP}'
password_encryption = 'scram-sha-256'
ssl = on
ssl_cert_file = '/etc/postgresql/15/main/tls/server.crt'
ssl_key_file = '/etc/postgresql/15/main/tls/server.key'
shared_buffers = '4GB'
effective_cache_size = '12GB'
maintenance_work_mem = '1GB'
work_mem = '8MB'
max_connections = 100
checkpoint_completion_target = 0.9
min_wal_size = '4GB'
max_wal_size = '16GB'
wal_compression = on
random_page_cost = 1.1
effective_io_concurrency = 100
log_checkpoints = on
log_lock_waits = on
log_min_duration_statement = '2s'
EOF

if ! grep -Eq \
  "^[[:space:]]*include_dir[[:space:]]*=[[:space:]]*'conf\\.d'[[:space:]]*(#.*)?$" \
  "$POSTGRESQL_CONF"; then
  printf "\ninclude_dir = 'conf.d'\n" >> "$POSTGRESQL_CONF"
fi

cp /etc/postgresql/15/main/pg_hba.conf /etc/postgresql/15/main/pg_hba.conf.provider-default
cat > /etc/postgresql/15/main/pg_hba.conf <<EOF
# TYPE  DATABASE             USER                 ADDRESS             METHOD
local   all                  postgres                                 peer
local   all                  all                                      peer
hostssl all                  ${DATABASE_OWNER}     ${APP_PRIVATE_IP}/32 scram-sha-256
host    all                  all                  0.0.0.0/0           reject
host    all                  all                  ::/0                reject
EOF

systemctl enable postgresql
systemctl restart postgresql

escaped_password="${database_password//\'/\'\'}"
sudo -u postgres psql -X -v ON_ERROR_STOP=1 <<SQL
DO \$role\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DATABASE_OWNER}') THEN
    CREATE ROLE ${DATABASE_OWNER} LOGIN;
  END IF;
END
\$role\$;
ALTER ROLE ${DATABASE_OWNER} WITH LOGIN PASSWORD '${escaped_password}';
SELECT 'CREATE DATABASE ${DATABASE_NAME} OWNER ${DATABASE_OWNER} TEMPLATE template0 ENCODING ''UTF8'' LC_COLLATE ''en_US.UTF-8'' LC_CTYPE ''en_US.UTF-8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${DATABASE_NAME}')\gexec
ALTER DATABASE ${DATABASE_NAME} OWNER TO ${DATABASE_OWNER};
COMMENT ON DATABASE ${DATABASE_NAME} IS 'RTBcat Hetzner target; do not use before an approved cutover';
SQL
unset database_password escaped_password

install -d -o root -g root -m 0755 /etc/rtbcat
cat > "$MARKER_FILE" <<EOF
RTBCAT_DATABASE_PRIVATE_IP=${PRIVATE_IP}
RTBCAT_APP_PRIVATE_IP=${APP_PRIVATE_IP}
RTBCAT_DATABASE_NAME=${DATABASE_NAME}
RTBCAT_DATABASE_OWNER=${DATABASE_OWNER}
RTBCAT_POSTGRES_VERSION=${REQUIRED_POSTGRES_VERSION}
RTBCAT_VOLUME_ID=${VOLUME_ID}
RTBCAT_DATA_MOUNT=${DATA_MOUNT}
EOF
chmod 0644 "$MARKER_FILE"

ufw allow from "$APP_PRIVATE_IP" to "$PRIVATE_IP" port 5432 proto tcp comment 'RTBcat app to PostgreSQL'
verify_host

echo "Database foundation is ready. Configure and prove pgBackRest before loading production data."
