#!/usr/bin/env bash
# Install a root-only Docker credential for private GHCR package pulls.

set -euo pipefail

USERNAME=""
TOKEN_FILE=""
DOCKER_CONFIG_DIR="/etc/rtbcat/docker"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/install_ghcr_pull_credentials.sh \
  --username <github-user> --token-file <root-readable-file>

The token should be a dedicated classic PAT with read:packages only. Skip this
script when both GHCR packages are public.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --username) USERNAME="${2:?missing username}"; shift 2 ;;
    --token-file) TOKEN_FILE="${2:?missing token file}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi
if ! [[ "$USERNAME" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,38}$ ]]; then
  echo "Invalid GitHub username." >&2
  exit 1
fi
if [[ ! -f "$TOKEN_FILE" || -L "$TOKEN_FILE" ]]; then
  echo "Token file must be a regular non-symlink file." >&2
  exit 1
fi
token_mode="$(stat -c '%a' "$TOKEN_FILE")"
if [[ "$token_mode" != "400" && "$token_mode" != "600" ]]; then
  echo "Token file must have mode 0400 or 0600." >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$DOCKER_CONFIG_DIR"
docker --config "$DOCKER_CONFIG_DIR" login ghcr.io \
  --username "$USERNAME" \
  --password-stdin < "$TOKEN_FILE"
chmod 0600 "$DOCKER_CONFIG_DIR/config.json"
echo "Installed root-only GHCR pull credentials."
