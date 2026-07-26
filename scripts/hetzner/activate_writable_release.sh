#!/usr/bin/env bash
# Activate the already accepted immutable release as writable while keeping
# every target scheduler disabled. This script never changes DNS or GCP.

set -euo pipefail

RELEASE_FILE=""
COMPOSE_FILE=""
CUTOVER_EVIDENCE=""
JSON_OUT=""
CONFIRM=""
CHECK_ONLY="false"
RUNTIME_ENV_FILE="/etc/rtbcat/runtime.env"
MARKER_FILE="/etc/rtbcat/app-host.env"
RUNTIME_MARKER="/etc/rtbcat/app-runtime-installed.env"
POSTGRES_PASSWORD_FILE="/etc/rtbcat/secrets/postgres-password"
POSTGRES_CA_FILE="/etc/rtbcat/secrets/postgres-ca.crt"
GOOGLE_CREDENTIALS_FILE="/etc/rtbcat/secrets/google-adc.json"
DATA_DIR="/var/lib/rtbcat/app-data"
RELEASE_DIR="/var/lib/rtbcat/releases"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_SCRIPT="${SCRIPT_DIR}/verify_app_release.sh"

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/activate_writable_release.sh \
  --release-file <accepted-digest-release.env> \
  [--compose-file <release-matched-compose.yml>] \
  [--runtime-env-file <path>] \
  --cutover-evidence <mode-0600-json> \
  --json-out <mode-0600-receipt.json> \
  --confirm ACTIVATE_WRITABLE_SCHEDULERS_OFF_NO_DNS

Rehearsal-only validation (does not inspect or change running containers):
  scripts/hetzner/activate_writable_release.sh \
    --check-only \
    --release-file <rehearsal-release.env> \
    --compose-file <compose.yml> \
    --runtime-env-file <rehearsal-runtime.env> \
    --cutover-evidence <rehearsal-evidence.json> \
    --json-out <rehearsal-receipt.json> \
    --confirm REHEARSE_WRITABLE_SCHEDULERS_OFF_NO_DNS

Live activation requires an accepted current immutable shadow release and
evidence that source writers are frozen, logical catch-up and sequence sync are
complete, reconciliation and target backup are accepted, DNS is unchanged and
no target scheduler is enabled. The resulting API remains loopback-only.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-file) RELEASE_FILE="${2:?missing release file}"; shift 2 ;;
    --compose-file) COMPOSE_FILE="${2:?missing Compose file}"; shift 2 ;;
    --runtime-env-file) RUNTIME_ENV_FILE="${2:?missing runtime env file}"; shift 2 ;;
    --cutover-evidence) CUTOVER_EVIDENCE="${2:?missing cutover evidence}"; shift 2 ;;
    --json-out) JSON_OUT="${2:?missing JSON output path}"; shift 2 ;;
    --confirm) CONFIRM="${2:?missing confirmation}"; shift 2 ;;
    --check-only) CHECK_ONLY="true"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$CHECK_ONLY" == "true" ]]; then
  if [[ "$CONFIRM" != "REHEARSE_WRITABLE_SCHEDULERS_OFF_NO_DNS" ]]; then
    echo "Exact rehearsal confirmation is required." >&2
    exit 2
  fi
elif [[ "$CONFIRM" != "ACTIVATE_WRITABLE_SCHEDULERS_OFF_NO_DNS" ]]; then
  echo "Exact writable-activation confirmation is required." >&2
  exit 2
fi

if [[ "$CHECK_ONLY" != "true" && ${EUID} -ne 0 ]]; then
  echo "Run live activation as root on the Hetzner app host." >&2
  exit 1
fi
if [[ -z "$RELEASE_FILE" || -z "$CUTOVER_EVIDENCE" || -z "$JSON_OUT" ]]; then
  echo "Release, cutover evidence and JSON output paths are required." >&2
  usage >&2
  exit 2
fi
for required_path in "$RELEASE_FILE" "$RUNTIME_ENV_FILE" "$CUTOVER_EVIDENCE"; do
  if [[ ! -f "$required_path" ]]; then
    echo "Missing required file: ${required_path}." >&2
    exit 1
  fi
done
RELEASE_FILE="$(readlink -f "$RELEASE_FILE")"
RUNTIME_ENV_FILE="$(readlink -f "$RUNTIME_ENV_FILE")"
CUTOVER_EVIDENCE="$(readlink -f "$CUTOVER_EVIDENCE")"
if [[ "$(stat -c '%a' "$RUNTIME_ENV_FILE")" != "600" || \
      "$(stat -c '%a' "$CUTOVER_EVIDENCE")" != "600" ]]; then
  echo "Runtime env and cutover evidence must both be mode 0600." >&2
  exit 1
fi
if [[ "$CHECK_ONLY" != "true" ]] && \
   [[ "$(stat -c '%u' "$RUNTIME_ENV_FILE")" != "0" || \
      "$(stat -c '%u' "$CUTOVER_EVIDENCE")" != "0" ]]; then
  echo "Live runtime env and cutover evidence must be root-owned." >&2
  exit 1
fi
output_parent="$(dirname "$JSON_OUT")"
if [[ ! -d "$output_parent" ]]; then
  echo "JSON output parent does not exist: ${output_parent}." >&2
  exit 1
fi
JSON_OUT="$(readlink -f "$output_parent")/$(basename "$JSON_OUT")"

require_runtime_value() {
  local key="$1"
  local expected="$2"
  if ! awk -F= -v key="$key" -v expected="$expected" '
      $1 == key {count += 1; if ($2 == expected) matches += 1}
      END {exit !(count == 1 && matches == 1)}
    ' "$RUNTIME_ENV_FILE"; then
    echo "Runtime env must contain exactly one ${key}=${expected}." >&2
    exit 1
  fi
}
require_runtime_value CATSCAN_READ_ONLY_SHADOW true
require_runtime_value CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER false
require_runtime_value CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER false
require_runtime_value CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER false

release_value() {
  local key="$1"
  awk -F= -v key="$key" \
    '$1 == key {sub(/^[^=]*=/, ""); print; found=1; exit} END {if (!found) exit 1}' \
    "$RELEASE_FILE"
}
RELEASE_GIT_SHA="$(release_value RELEASE_GIT_SHA)"
RELEASE_VERSION="$(release_value RELEASE_VERSION)"
DEPLOY_COMPOSE_SHA256="$(release_value DEPLOY_COMPOSE_SHA256)"
API_IMAGE="$(release_value API_IMAGE)"
DASHBOARD_IMAGE="$(release_value DASHBOARD_IMAGE)"
if ! [[ "$RELEASE_GIT_SHA" =~ ^[a-f0-9]{40}$ ]] || \
   ! [[ "$RELEASE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || \
   ! [[ "$DEPLOY_COMPOSE_SHA256" =~ ^[a-f0-9]{64}$ ]]; then
  echo "Release SHA, version or Compose checksum is malformed." >&2
  exit 1
fi
if ! [[ "$API_IMAGE" =~ ^ghcr\.io/[a-z0-9._-]+/catscan-api@sha256:[a-f0-9]{64}$ ]] || \
   ! [[ "$DASHBOARD_IMAGE" =~ ^ghcr\.io/[a-z0-9._-]+/catscan-dashboard@sha256:[a-f0-9]{64}$ ]]; then
  echo "Only the expected digest-pinned GHCR images are accepted." >&2
  exit 1
fi

if [[ -z "$COMPOSE_FILE" ]]; then
  artifact_compose="$(dirname "$RELEASE_FILE")/hetzner-compose.yml"
  archived_compose="${RELEASE_DIR}/compose-${RELEASE_GIT_SHA}.yml"
  if [[ -f "$artifact_compose" ]]; then
    COMPOSE_FILE="$artifact_compose"
  elif [[ -f "$archived_compose" ]]; then
    COMPOSE_FILE="$archived_compose"
  else
    echo "No release-matched Compose file is available." >&2
    exit 1
  fi
fi
if [[ ! -f "$COMPOSE_FILE" ]] || \
   [[ "$(sha256sum "$COMPOSE_FILE" | awk '{print $1}')" != "$DEPLOY_COMPOSE_SHA256" ]]; then
  echo "Compose file does not match the immutable release manifest." >&2
  exit 1
fi
COMPOSE_FILE="$(readlink -f "$COMPOSE_FILE")"

expected_rehearsal="false"
if [[ "$CHECK_ONLY" == "true" ]]; then
  expected_rehearsal="true"
fi
if ! jq -e \
  --arg sha "$RELEASE_GIT_SHA" \
  --argjson rehearsal "$expected_rehearsal" \
  '
    .accepted == true
    and .rehearsal == $rehearsal
    and .release_git_sha == $sha
    and .source_writers_frozen == true
    and .source_active_writer_sessions == 0
    and .subscriber_caught_up == true
    and .sequence_sync_exact_match == true
    and .final_reconciliation_accepted == true
    and .target_backup_accepted == true
    and .dns_changed == false
    and .target_scheduler_enabled == false
    and (.source_freeze_lsn | test("^[0-9A-F]+/[0-9A-F]+$"))
    and (.subscriber_replay_lsn | test("^[0-9A-F]+/[0-9A-F]+$"))
  ' "$CUTOVER_EVIDENCE" >/dev/null; then
  echo "Cutover evidence does not satisfy every writable-activation gate." >&2
  exit 1
fi

if [[ "$CHECK_ONLY" != "true" ]]; then
  for required_path in "$MARKER_FILE" "$RUNTIME_MARKER" "$VERIFY_SCRIPT"; do
    if [[ ! -f "$required_path" ]]; then
      echo "Missing live-host marker or verifier: ${required_path}." >&2
      exit 1
    fi
  done
  # shellcheck source=/dev/null
  source "$MARKER_FILE"
  current_release="$(readlink -f "${RELEASE_DIR}/current.env" 2>/dev/null || true)"
  if [[ -z "$current_release" || \
        "$current_release" != "$(readlink -f "$RELEASE_FILE")" || \
        ! -f "${RELEASE_DIR}/accepted-${RELEASE_GIT_SHA}.marker" ]]; then
    echo "Release is not the currently accepted immutable shadow." >&2
    exit 1
  fi
else
  RTBCAT_DATABASE_PRIVATE_IP="127.0.0.1"
  RTBCAT_DATABASE_NAME="rtbcat_rehearsal"
  RTBCAT_DATABASE_OWNER="rtbcat_rehearsal"
  POSTGRES_PASSWORD_FILE="${POSTGRES_PASSWORD_FILE}.rehearsal"
  POSTGRES_CA_FILE="${POSTGRES_CA_FILE}.rehearsal"
  GOOGLE_CREDENTIALS_FILE="${GOOGLE_CREDENTIALS_FILE}.rehearsal"
  DATA_DIR="/tmp/rtbcat-writable-activation-rehearsal-data"
fi

export API_IMAGE DASHBOARD_IMAGE RELEASE_GIT_SHA RELEASE_VERSION
export RTBCAT_RUNTIME_ENV_FILE="$RUNTIME_ENV_FILE"
export RTBCAT_POSTGRES_PASSWORD_FILE="$POSTGRES_PASSWORD_FILE"
export RTBCAT_POSTGRES_CA_FILE="$POSTGRES_CA_FILE"
export RTBCAT_GOOGLE_CREDENTIALS_FILE="$GOOGLE_CREDENTIALS_FILE"
export RTBCAT_DATA_DIR="$DATA_DIR"
export RTBCAT_DATABASE_PRIVATE_IP RTBCAT_DATABASE_NAME RTBCAT_DATABASE_OWNER
export RTBCAT_DEPLOY_READ_ONLY_SHADOW=false
export RTBCAT_DEPLOY_GMAIL_SCHEDULER=false
export RTBCAT_DEPLOY_PRECOMPUTE_SCHEDULER=false
export RTBCAT_DEPLOY_CREATIVE_CACHE_SCHEDULER=false

rendered_config="$(mktemp)"
receipt_tmp="$(mktemp)"
cleanup() {
  rm -f -- "$rendered_config" "$receipt_tmp"
}
trap cleanup EXIT

docker compose --project-name rtbcat-hetzner -f "$COMPOSE_FILE" \
  config --format json > "$rendered_config"
if ! jq -e \
  --arg api "$API_IMAGE" \
  --arg dashboard "$DASHBOARD_IMAGE" \
  '
    .services.api.image == $api
    and .services.dashboard.image == $dashboard
    and (.services.api | has("build") | not)
    and (.services.dashboard | has("build") | not)
    and .services.api.environment.CATSCAN_READ_ONLY_SHADOW == "false"
    and .services.api.environment.CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER == "false"
    and .services.api.environment.CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER == "false"
    and .services.api.environment.CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER == "false"
    and (.services.api.ports | length == 1)
    and any(.services.api.ports[];
      .host_ip == "127.0.0.1"
      and (.target | tostring) == "8000"
      and (.published | tostring) == "8000")
    and (.services.dashboard.ports | length == 1)
    and any(.services.dashboard.ports[];
      .host_ip == "127.0.0.1"
      and (.target | tostring) == "3000"
      and (.published | tostring) == "3000")
  ' "$rendered_config" >/dev/null; then
  echo "Rendered writable Compose violates image, listener or scheduler guards." >&2
  exit 1
fi

cutover_evidence_sha256="$(sha256sum "$CUTOVER_EVIDENCE" | awk '{print $1}')"
rendered_compose_sha256="$(sha256sum "$rendered_config" | awk '{print $1}')"

write_receipt() {
  local status="$1"
  local activated="$2"
  local shadow_restored="$3"
  jq -n \
    --arg generated_at "$(date -u +%FT%TZ)" \
    --arg status "$status" \
    --arg release_git_sha "$RELEASE_GIT_SHA" \
    --arg release_version "$RELEASE_VERSION" \
    --arg api_image "$API_IMAGE" \
    --arg dashboard_image "$DASHBOARD_IMAGE" \
    --arg compose_sha256 "$DEPLOY_COMPOSE_SHA256" \
    --arg rendered_compose_sha256 "$rendered_compose_sha256" \
    --arg cutover_evidence_sha256 "$cutover_evidence_sha256" \
    --argjson rehearsal "$expected_rehearsal" \
    --argjson activated "$activated" \
    --argjson shadow_restored "$shadow_restored" \
    '{
      generated_at: $generated_at,
      status: $status,
      rehearsal: $rehearsal,
      activated: $activated,
      release_git_sha: $release_git_sha,
      release_version: $release_version,
      api_image: $api_image,
      dashboard_image: $dashboard_image,
      compose_sha256: $compose_sha256,
      rendered_compose_sha256: $rendered_compose_sha256,
      cutover_evidence_sha256: $cutover_evidence_sha256,
      mode: "writable-schedulers-off",
      read_only_shadow: false,
      scheduler_flags: {
        gmail_import: false,
        precompute: false,
        creative_cache: false
      },
      listeners: {
        api: "127.0.0.1:8000",
        dashboard: "127.0.0.1:3000"
      },
      dns_changed: false,
      shadow_restored_after_failure: $shadow_restored
    }' > "$receipt_tmp"
  install -m 0600 "$receipt_tmp" "$JSON_OUT"
}

if [[ "$CHECK_ONLY" == "true" ]]; then
  write_receipt accepted false false
  printf '%s\n' "Writable activation rehearsal accepted; no containers, DNS, writers or schedulers changed."
  exit 0
fi

"$VERIFY_SCRIPT" --release-file "$RELEASE_FILE" --mode shadow --with-google
if ! docker exec rtbcat-api python /app/scripts/check_gmail_import_idle.py; then
  echo "Current Gmail import is active or could not be proven idle." >&2
  exit 1
fi
write_receipt prepared false false

activation_ok="true"
if ! docker compose --project-name rtbcat-hetzner -f "$COMPOSE_FILE" \
  up -d --no-build --remove-orphans; then
  activation_ok="false"
elif ! "$VERIFY_SCRIPT" \
  --release-file "$RELEASE_FILE" \
  --mode writable-schedulers-off \
  --with-google; then
  activation_ok="false"
fi

if [[ "$activation_ok" != "true" ]]; then
  export RTBCAT_DEPLOY_READ_ONLY_SHADOW=true
  shadow_restored="false"
  if docker compose --project-name rtbcat-hetzner -f "$COMPOSE_FILE" \
      up -d --no-build --remove-orphans && \
     "$VERIFY_SCRIPT" --release-file "$RELEASE_FILE" --mode shadow --with-google; then
    shadow_restored="true"
  fi
  write_receipt failed false "$shadow_restored"
  echo "Writable activation failed; shadow restoration=${shadow_restored}." >&2
  exit 1
fi

write_receipt accepted true false
echo "Activated immutable writable release ${RELEASE_GIT_SHA} with every scheduler disabled. DNS and GCP were unchanged."
