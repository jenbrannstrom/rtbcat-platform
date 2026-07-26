#!/usr/bin/env bash
# Install Tailscale from its Ubuntu stable repository without storing an auth
# key in Terraform, shell history, or this repository.

set -euo pipefail

AUTHENTICATE="false"
TAILSCALE_HOSTNAME="$(hostname -s)"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/install_tailscale.sh [options]

Options:
  --authenticate        Run interactive `tailscale up` after installation.
  --hostname <name>     Tailnet machine name (default: current short hostname).
  --help                Show this help.

The interactive flow prints an authorization URL. No Tailscale auth key is
accepted by this script on purpose.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --authenticate)
      AUTHENTICATE="true"
      shift
      ;;
    --hostname)
      TAILSCALE_HOSTNAME="${2:?--hostname requires a value}"
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

if [[ ! "$TAILSCALE_HOSTNAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}$ ]]; then
  echo "Invalid Tailscale hostname: $TAILSCALE_HOSTNAME" >&2
  exit 1
fi

# shellcheck source=/dev/null
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_CODENAME:-}" != "noble" ]]; then
  echo "Expected Ubuntu 24.04 (noble), found ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf -- "$tmp_dir"
}
trap cleanup EXIT

curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg" \
  -o "$tmp_dir/tailscale-archive-keyring.gpg"
curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list" \
  -o "$tmp_dir/tailscale.list"

install -o root -g root -m 0644 "$tmp_dir/tailscale-archive-keyring.gpg" \
  /usr/share/keyrings/tailscale-archive-keyring.gpg
install -o root -g root -m 0644 "$tmp_dir/tailscale.list" \
  /etc/apt/sources.list.d/tailscale.list

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y tailscale
systemctl enable --now tailscaled
ufw allow 41641/udp comment 'Tailscale direct transport'

if [[ "$AUTHENTICATE" == "true" ]]; then
  tailscale up --ssh --hostname="$TAILSCALE_HOSTNAME"
  ufw allow in on tailscale0 to any port 22 proto tcp comment 'SSH over Tailscale'
  tailscale status
  echo "Tailscale SSH is enabled. Verify a second login over the tailnet before closing public SSH."
else
  cat <<EOF
Tailscale is installed but not authenticated.

Run this from the still-available bootstrap SSH session:
  sudo tailscale up --ssh --hostname=${TAILSCALE_HOSTNAME}
  sudo ufw allow in on tailscale0 to any port 22 proto tcp comment 'SSH over Tailscale'

Verify a second SSH session over the tailnet, then run close_public_ssh.sh and
set enable_public_bootstrap_ssh=false in Terraform.
EOF
fi
