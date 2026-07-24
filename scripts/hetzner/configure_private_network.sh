#!/usr/bin/env bash
# Configure the first Hetzner Cloud Network interface on Ubuntu with the
# fixed address already assigned to the server by the Hetzner API.

set -euo pipefail

PRIVATE_IP=""
NETWORK_CIDR=""
GATEWAY=""
INTERFACE="enp7s0"
CONFIG_FILE="/etc/netplan/60-rtbcat-private-network.yaml"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/configure_private_network.sh \
  --private-ip <ip> --network-cidr <cidr> --gateway <ip> [options]

Options:
  --interface <name>  Private interface (default: enp7s0 for CPX/CCX v2/v3).
  --help              Show this help.

The address, network and gateway must match the Hetzner API/Terraform outputs.
The script refuses to overwrite a different existing RTBcat netplan file.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --private-ip)
      PRIVATE_IP="${2:?--private-ip requires a value}"
      shift 2
      ;;
    --network-cidr)
      NETWORK_CIDR="${2:?--network-cidr requires a value}"
      shift 2
      ;;
    --gateway)
      GATEWAY="${2:?--gateway requires a value}"
      shift 2
      ;;
    --interface)
      INTERFACE="${2:?--interface requires a value}"
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
if [[ -z "$PRIVATE_IP" || -z "$NETWORK_CIDR" || -z "$GATEWAY" ]]; then
  echo "Private IP, network CIDR and gateway are required." >&2
  usage >&2
  exit 1
fi
if ! [[ "$PRIVATE_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || \
   ! [[ "$GATEWAY" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || \
   ! [[ "$NETWORK_CIDR" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]{1,2}$ ]]; then
  echo "Private IP, network CIDR or gateway has an invalid IPv4 format." >&2
  exit 1
fi
if ! [[ "$INTERFACE" =~ ^[a-zA-Z0-9_.:-]+$ ]] || \
   [[ ! -d "/sys/class/net/${INTERFACE}" ]]; then
  echo "Private interface does not exist: $INTERFACE" >&2
  exit 1
fi

# shellcheck source=/dev/null
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_CODENAME:-}" != "noble" ]]; then
  echo "Expected Ubuntu 24.04 (noble), found ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi

tmp_config="$(mktemp)"
cleanup() {
  rm -f -- "$tmp_config"
}
trap cleanup EXIT
chmod 0600 "$tmp_config"
cat > "$tmp_config" <<EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    ${INTERFACE}:
      addresses:
        - ${PRIVATE_IP}/32
      routes:
        - to: ${NETWORK_CIDR}
          via: ${GATEWAY}
          on-link: true
EOF

if [[ -f "$CONFIG_FILE" ]] && ! cmp -s "$tmp_config" "$CONFIG_FILE"; then
  echo "Refusing to overwrite different existing config: $CONFIG_FILE" >&2
  exit 1
fi

install -o root -g root -m 0600 "$tmp_config" "$CONFIG_FILE"
netplan generate
netplan apply

address_ready="false"
for _ in {1..20}; do
  if ip -4 -o address show dev "$INTERFACE" | grep -Fq " ${PRIVATE_IP}/32 "; then
    address_ready="true"
    break
  fi
  sleep 1
done
if [[ "$address_ready" != "true" ]]; then
  echo "Expected ${PRIVATE_IP}/32 is not active on ${INTERFACE}." >&2
  exit 1
fi
if ! ip -4 route show exact "$NETWORK_CIDR" | \
  grep -Eq "via ${GATEWAY//./\\.} dev ${INTERFACE}( |$)"; then
  echo "Expected route ${NETWORK_CIDR} via ${GATEWAY} is absent." >&2
  exit 1
fi

ip -4 -brief address show dev "$INTERFACE"
ip -4 route show exact "$NETWORK_CIDR"
echo "Hetzner private network configuration is active."
