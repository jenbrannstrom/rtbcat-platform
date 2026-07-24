#!/usr/bin/env bash
# Roll the shadow app back to a previously archived immutable manifest.

set -euo pipefail

TARGET_SHA=""
CONFIRM=""
RELEASE_DIR="/var/lib/rtbcat/releases"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  sudo scripts/hetzner/rollback_app_release.sh --list
  sudo scripts/hetzner/rollback_app_release.sh \
    --to-sha <full-40-character-sha> --confirm rollback-immutable-release
EOF
}

if [[ "${1:-}" == "--list" ]]; then
  find "$RELEASE_DIR" -maxdepth 1 -type f -name 'accepted-*.marker' \
    -printf '%f\n' | sed -e 's/^accepted-/release-/' -e 's/\.marker$/.env/' | sort
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --to-sha) TARGET_SHA="${2:?missing SHA}"; shift 2 ;;
    --confirm) CONFIRM="${2:?missing confirmation}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi
if ! [[ "$TARGET_SHA" =~ ^[a-f0-9]{40}$ ]] || \
   [[ "$CONFIRM" != "rollback-immutable-release" ]]; then
  echo "A full SHA and exact rollback confirmation are required." >&2
  exit 1
fi
target_release="${RELEASE_DIR}/release-${TARGET_SHA}.env"
accepted_marker="${RELEASE_DIR}/accepted-${TARGET_SHA}.marker"
if [[ ! -f "$target_release" || ! -f "$accepted_marker" ]]; then
  echo "Accepted archived release does not exist: ${target_release}." >&2
  exit 1
fi

exec "$SCRIPT_DIR/deploy_app_release.sh" \
  --release-file "$target_release" \
  --confirm deploy-shadow-no-dns
