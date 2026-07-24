#!/usr/bin/env bash
# Install a checksum-pinned Cloud SQL Auth Proxy on a Hetzner target host.

set -euo pipefail

CLOUD_SQL_PROXY_VERSION="2.22.0"
CLOUD_SQL_PROXY_SHA256="42e73a8775bc3300b6514816cc4893f01b109a50f65aa779a451d3e4ff4c3ead"
INSTALL_PATH="/usr/local/bin/cloud-sql-proxy"

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi
if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "This pinned binary is for linux/amd64 only." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf -- "$tmp_dir"
}
trap cleanup EXIT

download="$tmp_dir/cloud-sql-proxy"
url="https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v${CLOUD_SQL_PROXY_VERSION}/cloud-sql-proxy.linux.amd64"
curl -fsSL "$url" -o "$download"
echo "${CLOUD_SQL_PROXY_SHA256}  ${download}" | sha256sum -c -
install -o root -g root -m 0755 "$download" "$INSTALL_PATH"

"$INSTALL_PATH" --version
echo "Installed checksum-pinned Cloud SQL Auth Proxy ${CLOUD_SQL_PROXY_VERSION}."
