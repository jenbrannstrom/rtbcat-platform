#!/usr/bin/env bash
# Move the Terraform-created app-data Volume from its provider automount path
# to the stable path consumed by the immutable Hetzner Compose deployment.

set -euo pipefail

VOLUME_ID=""
VERIFY_ONLY="false"
TARGET_MOUNT="/var/lib/rtbcat/app-data"
HOST_MARKER="/etc/rtbcat/app-host.env"
VOLUME_MARKER="/etc/rtbcat/app-data-volume.env"
CONTAINER_UID=10001
CONTAINER_GID=10001

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/bootstrap_app_data_volume.sh [options]

Required for first run:
  --volume-id <id>  App-data Volume ID from Terraform output.

Optional:
  --verify-only     Verify the existing stable mount without changing it.
  --help

The Volume must already be XFS-formatted by Terraform. The target directory
must be empty. This script never formats a device and never copies data.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --volume-id)
      VOLUME_ID="${2:?--volume-id requires a value}"
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
  echo "Run this script as root on the marked Hetzner app host." >&2
  exit 1
fi
if [[ ! -f "$HOST_MARKER" ]]; then
  echo "Hetzner app-host marker is absent." >&2
  exit 1
fi
if [[ "$VERIFY_ONLY" == "true" ]]; then
  if [[ ! -f "$VOLUME_MARKER" ]]; then
    echo "App-data Volume marker is absent." >&2
    exit 1
  fi
  VOLUME_ID="$(sed -n 's/^RTBCAT_APP_DATA_VOLUME_ID=//p' "$VOLUME_MARKER")"
fi
if ! [[ "$VOLUME_ID" =~ ^[0-9]+$ ]]; then
  echo "Volume ID must be numeric." >&2
  exit 1
fi

volume_device="/dev/disk/by-id/scsi-0HC_Volume_${VOLUME_ID}"
if [[ ! -b "$volume_device" ]]; then
  echo "Hetzner app-data Volume device is absent: ${volume_device}." >&2
  exit 1
fi
resolved_volume="$(readlink -f "$volume_device")"

verify_mount() {
  local mount_source owner_uid owner_gid filesystem_size

  if ! findmnt --mountpoint "$TARGET_MOUNT" >/dev/null 2>&1; then
    echo "App-data path is not a mountpoint: ${TARGET_MOUNT}." >&2
    exit 1
  fi
  mount_source="$(findmnt -n -o SOURCE --mountpoint "$TARGET_MOUNT")"
  if [[ "$(readlink -f "$mount_source")" != "$resolved_volume" ]]; then
    echo "App-data path is mounted from the wrong device: ${mount_source}." >&2
    exit 1
  fi
  if [[ "$(findmnt -n -o FSTYPE --mountpoint "$TARGET_MOUNT")" != "xfs" ]]; then
    echo "App-data Volume is not mounted as XFS." >&2
    exit 1
  fi
  owner_uid="$(stat -c '%u' "$TARGET_MOUNT")"
  owner_gid="$(stat -c '%g' "$TARGET_MOUNT")"
  if [[ "$owner_uid" != "$CONTAINER_UID" || "$owner_gid" != "$CONTAINER_GID" ]]; then
    echo "App-data mount must be owned by ${CONTAINER_UID}:${CONTAINER_GID}." >&2
    exit 1
  fi
  filesystem_size="$(df -B1 --output=size "$TARGET_MOUNT" | tail -n 1 | tr -d ' ')"
  if (( filesystem_size < 140000000000 )); then
    echo "App-data Volume is smaller than the 150 GB-class baseline." >&2
    exit 1
  fi
}

if [[ "$VERIFY_ONLY" == "true" ]]; then
  verify_mount
  echo "App-data Volume mount verified."
  exit 0
fi

root_source="$(findmnt -n -o SOURCE /)"
if [[ "$resolved_volume" == "$(readlink -f "$root_source")" ]]; then
  echo "Refusing to use the root device as app-data storage." >&2
  exit 1
fi
if [[ "$(blkid -s TYPE -o value "$volume_device")" != "xfs" ]]; then
  echo "App-data Volume is not XFS-formatted by Terraform; refusing to format it." >&2
  exit 1
fi

existing_mount="$(findmnt -n -o TARGET --source "$volume_device" 2>/dev/null || true)"
if [[ -n "$existing_mount" && "$existing_mount" != "$TARGET_MOUNT" ]]; then
  umount "$existing_mount"
fi
install -d -o "$CONTAINER_UID" -g "$CONTAINER_GID" -m 0750 "$TARGET_MOUNT"
if find "$TARGET_MOUNT" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  echo "App-data target is not empty; refusing to hide or overwrite its contents." >&2
  exit 1
fi

volume_uuid="$(blkid -s UUID -o value "$volume_device")"
if [[ -z "$volume_uuid" ]]; then
  echo "Could not read the app-data Volume UUID." >&2
  exit 1
fi
cp --no-clobber /etc/fstab "/etc/fstab.pre-rtbcat-app-data-${VOLUME_ID}"
sed -i \
  -e "\\|HC_Volume_${VOLUME_ID}|d" \
  -e "\\|UUID=${volume_uuid} |d" \
  /etc/fstab
echo "UUID=${volume_uuid} ${TARGET_MOUNT} xfs defaults,noatime,nofail,x-systemd.device-timeout=30s 0 2" >> /etc/fstab
systemctl daemon-reload
mount "$TARGET_MOUNT"
chown "$CONTAINER_UID:$CONTAINER_GID" "$TARGET_MOUNT"
chmod 0750 "$TARGET_MOUNT"

cat > "$VOLUME_MARKER" <<EOF
RTBCAT_APP_DATA_VOLUME_ID=${VOLUME_ID}
RTBCAT_APP_DATA_MOUNT=${TARGET_MOUNT}
EOF
chmod 0644 "$VOLUME_MARKER"

verify_mount
echo "App-data Volume is mounted at ${TARGET_MOUNT}; data transfer is intentionally separate."
