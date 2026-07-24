#!/usr/bin/env bash
# Close host-level public SSH only after a separate Tailscale SSH connection
# has been verified. Terraform closes the provider firewall in a second step.

set -euo pipefail

CONFIRMED="false"
SSH_CIDRS=()

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/close_public_ssh.sh \
  --confirmed-tailnet-ssh --cidr <bootstrap-cidr> [--cidr <bootstrap-cidr> ...]

After this host-level change, set enable_public_bootstrap_ssh=false in
terraform/hetzner/terraform.tfvars and review/apply the firewall-only plan.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirmed-tailnet-ssh)
      CONFIRMED="true"
      shift
      ;;
    --cidr)
      SSH_CIDRS+=("${2:?--cidr requires a value}")
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
if [[ "$CONFIRMED" != "true" || ${#SSH_CIDRS[@]} -eq 0 ]]; then
  echo "A verified tailnet login and at least one bootstrap CIDR are required." >&2
  usage >&2
  exit 1
fi
if ! tailscale status --json | jq -e '.BackendState == "Running"' >/dev/null; then
  echo "Tailscale is not in the Running state; refusing to close public SSH." >&2
  exit 1
fi
if [[ -z "$(tailscale ip -4)" ]]; then
  echo "No Tailscale IPv4 is assigned; refusing to close public SSH." >&2
  exit 1
fi

ufw allow in on tailscale0 to any port 22 proto tcp comment 'SSH over Tailscale'
for cidr in "${SSH_CIDRS[@]}"; do
  if ! [[ "$cidr" =~ ^[0-9a-fA-F:.]+/[0-9]{1,3}$ ]]; then
    echo "Invalid CIDR: $cidr" >&2
    exit 1
  fi
  ufw --force delete allow from "$cidr" to any port 22 proto tcp || true
done

ufw status verbose
cat <<'EOF'
Host-level public SSH rules are closed.

Next, set enable_public_bootstrap_ssh=false and apply the reviewed Terraform
plan. It should update only the two hcloud_firewall resources. Do not proceed
if Terraform proposes replacing either server.
EOF
