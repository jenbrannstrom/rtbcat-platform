#!/usr/bin/env bash
# Bootstrap only the disposable, local-disk pgBackRest restore-drill host.
# This script refuses the production database host and does not expose TCP/5432.

set -euo pipefail

REQUIRED_POSTGRES_VERSION="15.17"
REQUIRED_POSTGRES_VERSION_NUM="150017"
POSTGRES_PACKAGE_VERSION="15.17-1.pgdg24.04+1"
POSTGRES_SERVER_SHA256="db186eb11b5af796d77a46ca411861e232c8f10441ddbde0b4c18d71617f34c4"
POSTGRES_CLIENT_SHA256="a2f145d29318fbf92d3ded83652c01e12d68277fcfedbb60f74aa05ea1207165"
REQUIRED_PGBACKREST_VERSION="2.58.0"
MIN_ROOT_BYTES="600000000000"
MARKER_FILE="/etc/rtbcat/restore-drill-host.env"
PRODUCTION_MARKER="/etc/rtbcat/database-host.env"
PGDATA="/var/lib/postgresql/15/main"
PG_CONTROLDATA="/usr/lib/postgresql/15/bin/pg_controldata"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/bootstrap_pgbackrest_restore_host.sh \
  --confirm BOOTSTRAP_DISPOSABLE_RESTORE_HOST

Run only on the opt-in Terraform pgBackRest restore-drill host. The script
requires its cloud-init marker, at least 600 decimal GB on the root disk, no
production database marker, and the expected recovery-drill hostname. It pins
PostgreSQL 15.17, creates a small checksummed cluster, leaves PostgreSQL
stopped, and never opens TCP/5432.
EOF
}

CONFIRM=""
while [[ $# -gt 0 ]]; do
  case "$1" in
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
if [[ "$CONFIRM" != "BOOTSTRAP_DISPOSABLE_RESTORE_HOST" ]]; then
  echo "Exact disposable-host confirmation is required." >&2
  usage >&2
  exit 1
fi
if [[ ! -f "$MARKER_FILE" ]] || \
   ! grep -qx 'RTBCAT_RESTORE_DRILL=true' "$MARKER_FILE"; then
  echo "The Terraform restore-drill marker is absent." >&2
  exit 1
fi
if [[ -e "$PRODUCTION_MARKER" ]]; then
  echo "Production database marker is present; refusing restore-host bootstrap." >&2
  exit 1
fi
if [[ "$(hostname -s)" != *"-pgbackrest-restore" ]]; then
  echo "Unexpected hostname for a restore-drill host: $(hostname -s)" >&2
  exit 1
fi
root_bytes="$(df -B1 --output=size / | tail -n 1 | tr -d ' ')"
if ! [[ "$root_bytes" =~ ^[0-9]+$ ]] || (( root_bytes < MIN_ROOT_BYTES )); then
  echo "Restore-drill root disk is too small: ${root_bytes} bytes." >&2
  exit 1
fi
resume_fresh_cluster="false"
if [[ -d "$PGDATA" ]] && \
   find "$PGDATA" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
  pgdata_bytes="$(du -sb "$PGDATA" | awk '{print $1}')"
  if [[ -f "$PGDATA/PG_VERSION" ]] && \
     grep -qx '15' "$PGDATA/PG_VERSION" && \
     [[ "$pgdata_bytes" =~ ^[0-9]+$ ]] && \
     (( pgdata_bytes <= 1073741824 )) && \
     [[ ! -e "$PGDATA/postmaster.pid" ]] && \
     ! grep -qx 'RTBCAT_RESTORE_DRILL_BOOTSTRAPPED=true' "$MARKER_FILE"; then
    resume_fresh_cluster="true"
  else
    echo "PostgreSQL data directory is not an exact resumable fresh cluster; refusing bootstrap." >&2
    exit 1
  fi
fi

install -d -o root -g root -m 0755 /etc/postgresql-common
cat > /etc/postgresql-common/createcluster.conf <<'EOF'
create_main_cluster = false
EOF

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates curl locales postgresql-common
install -d -o root -g root -m 0755 /usr/share/postgresql-common/pgdg
curl -fsSL --fail \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc \
  -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
cat > /etc/apt/sources.list.d/pgdg.sources <<'EOF'
Types: deb
URIs: https://apt.postgresql.org/pub/repos/apt
Suites: noble-pgdg
Architectures: amd64
Components: main
Signed-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
EOF

apt-get update
package_dir="$(mktemp -d)"
cleanup() {
  rm -rf -- "$package_dir"
}
trap cleanup EXIT
server_package="${package_dir}/postgresql-15.deb"
client_package="${package_dir}/postgresql-client-15.deb"
package_base_url="https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-15"
curl -fsSL --fail \
  "${package_base_url}/postgresql-15_${POSTGRES_PACKAGE_VERSION}_amd64.deb" \
  -o "$server_package"
curl -fsSL --fail \
  "${package_base_url}/postgresql-client-15_${POSTGRES_PACKAGE_VERSION}_amd64.deb" \
  -o "$client_package"
printf '%s  %s\n' "$POSTGRES_SERVER_SHA256" "$server_package" | \
  sha256sum --check --strict
printf '%s  %s\n' "$POSTGRES_CLIENT_SHA256" "$client_package" | \
  sha256sum --check --strict
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  "$client_package" \
  "$server_package" \
  jq pgbackrest
if [[ "$(dpkg-query -W -f='${Version}' postgresql-15)" != "$POSTGRES_PACKAGE_VERSION" ]] || \
   [[ "$(dpkg-query -W -f='${Version}' postgresql-client-15)" != "$POSTGRES_PACKAGE_VERSION" ]]; then
  echo "PostgreSQL package version drifted from ${POSTGRES_PACKAGE_VERSION}." >&2
  exit 1
fi
if [[ "$(pgbackrest version | awk '{print $2}')" != "$REQUIRED_PGBACKREST_VERSION" ]]; then
  echo "pgBackRest version drifted from ${REQUIRED_PGBACKREST_VERSION}." >&2
  exit 1
fi
apt-mark hold postgresql-15 postgresql-client-15

locale-gen en_US.UTF-8
install -d -o postgres -g postgres -m 0700 /var/lib/postgresql/15
if [[ "$resume_fresh_cluster" != "true" ]]; then
  pg_createcluster 15 main \
    --datadir="$PGDATA" \
    --locale=en_US.UTF-8 \
    --encoding=UTF8 \
    --start-conf=manual \
    -- --data-checksums
fi

install -d -o root -g root -m 0755 /etc/postgresql/15/main/conf.d
cat > /etc/postgresql/15/main/conf.d/20-restore-drill.conf <<'EOF'
listen_addresses = '127.0.0.1'
archive_mode = off
# Recovery refuses values lower than those recorded by the source primary.
# Match PostgreSQL's production/default floor while keeping the host loopback-only.
max_connections = 100
shared_buffers = '1GB'
effective_cache_size = '4GB'
maintenance_work_mem = '1GB'
EOF
if ! grep -Eq \
  "^[[:space:]]*include_dir[[:space:]]*=[[:space:]]*'conf\\.d'[[:space:]]*(#.*)?$" \
  /etc/postgresql/15/main/postgresql.conf; then
  printf "\ninclude_dir = 'conf.d'\n" >> /etc/postgresql/15/main/postgresql.conf
fi
cat > /etc/postgresql/15/main/pg_hba.conf <<'EOF'
# Recovery drill is loopback-only.
local   all   postgres                    peer
local   all   all                         peer
host    all   all      127.0.0.1/32       reject
host    all   all      ::1/128            reject
EOF

systemctl stop postgresql
systemctl disable postgresql
if systemctl is-active --quiet postgresql; then
  echo "PostgreSQL is still active; refusing to mark bootstrap complete." >&2
  exit 1
fi
if [[ "$("$PG_CONTROLDATA" "$PGDATA" | awk -F: '/Database cluster state/{gsub(/^ +/, "", $2); print $2}')" != "shut down" ]]; then
  echo "Fresh restore-drill cluster is not cleanly shut down." >&2
  exit 1
fi
if [[ "$("$PG_CONTROLDATA" "$PGDATA" | awk -F: '/Data page checksum version/{gsub(/^ +/, "", $2); print $2}')" == "0" ]]; then
  echo "Data checksums are not enabled." >&2
  exit 1
fi

cat >> "$MARKER_FILE" <<EOF
RTBCAT_RESTORE_DRILL_BOOTSTRAPPED=true
RTBCAT_RESTORE_DRILL_HOSTNAME=$(hostname -s)
RTBCAT_RESTORE_DRILL_ROOT_BYTES=${root_bytes}
RTBCAT_RESTORE_DRILL_PGDATA=${PGDATA}
RTBCAT_POSTGRES_VERSION=${REQUIRED_POSTGRES_VERSION}
RTBCAT_PGBACKREST_VERSION=${REQUIRED_PGBACKREST_VERSION}
EOF
chmod 0644 "$MARKER_FILE"

echo "Disposable restore host is pinned, checksummed, loopback-only, and stopped."
