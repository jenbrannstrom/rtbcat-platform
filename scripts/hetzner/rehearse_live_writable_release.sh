#!/usr/bin/env bash
# Run a bounded, private writable rehearsal against the stale Hetzner rehearsal
# database, then restore both the application and database to read-only shadow
# posture. This is not the final cutover activation path.

set -euo pipefail

RELEASE_FILE=""
COMPOSE_FILE=""
RUNTIME_ENV_FILE="/etc/rtbcat/runtime.env"
JSON_OUT=""
CONFIRM=""
RESTORE_ONLY="false"
PREFLIGHT_ONLY="false"
MARKER_FILE="/etc/rtbcat/app-host.env"
RUNTIME_MARKER="/etc/rtbcat/app-runtime-installed.env"
POSTGRES_PASSWORD_FILE="/etc/rtbcat/secrets/postgres-password"
POSTGRES_CA_FILE="/etc/rtbcat/secrets/postgres-ca.crt"
GOOGLE_CREDENTIALS_FILE="/etc/rtbcat/secrets/google-adc.json"
DATA_DIR="/var/lib/rtbcat/app-data"
RELEASE_DIR="/var/lib/rtbcat/releases"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_SELF="$(readlink -f "${BASH_SOURCE[0]}")"
VERIFY_SCRIPT="${SCRIPT_DIR}/verify_app_release.sh"
EXPECTED_DATABASE="rtbcat_serving_rehearsal"
DEADMAN_UNIT=""
DB_TOUCHED="false"
SHADOW_RESTORED="false"
DB_BEFORE='{}'
DB_AFTER='{}'
MIGRATIONS_BEFORE='[]'
MIGRATIONS_AFTER='[]'
SCHEDULER_RESULTS='{}'
WRITABLE_PROBE='{}'

usage() {
  cat <<'EOF'
Usage: sudo scripts/hetzner/rehearse_live_writable_release.sh \
  --release-file <accepted-digest-release.env> \
  [--compose-file <release-matched-compose.yml>] \
  [--runtime-env-file <path>] \
  --json-out <mode-0600-receipt.json> \
  --confirm REHEARSE_LIVE_WRITABLE_SCHEDULERS_OFF_NO_DNS

Preflight-only validation:
  sudo scripts/hetzner/rehearse_live_writable_release.sh \
    --preflight-only \
    --release-file <accepted-digest-release.env> \
    [--compose-file <release-matched-compose.yml>] \
    [--runtime-env-file <path>] \
    --json-out <mode-0600-preflight.json> \
    --confirm PREFLIGHT_B1_LIVE_WRITABLE

This command briefly starts the accepted, loopback-only Hetzner release in
writable mode against rtbcat_serving_rehearsal, with every scheduler disabled.
It verifies a rollback-only database write and scheduler refusal, then always
returns the database and application to read-only shadow posture.

It does not change DNS, GCP, Cloud SQL, source writers, or scheduler ownership.
It is not a substitute for activate_writable_release.sh and its final-sync
evidence gates.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-file) RELEASE_FILE="${2:?missing release file}"; shift 2 ;;
    --compose-file) COMPOSE_FILE="${2:?missing Compose file}"; shift 2 ;;
    --runtime-env-file) RUNTIME_ENV_FILE="${2:?missing runtime env file}"; shift 2 ;;
    --json-out) JSON_OUT="${2:?missing JSON output path}"; shift 2 ;;
    --confirm) CONFIRM="${2:?missing confirmation}"; shift 2 ;;
    --restore-only) RESTORE_ONLY="true"; shift ;;
    --preflight-only) PREFLIGHT_ONLY="true"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$RESTORE_ONLY" == "true" ]]; then
  if [[ "$CONFIRM" != "RESTORE_B1_READ_ONLY_SHADOW" ]]; then
    echo "Exact B1 shadow-restoration confirmation is required." >&2
    exit 2
  fi
elif [[ "$PREFLIGHT_ONLY" == "true" ]]; then
  if [[ "$CONFIRM" != "PREFLIGHT_B1_LIVE_WRITABLE" ]]; then
    echo "Exact B1 preflight confirmation is required." >&2
    exit 2
  fi
elif [[ "$CONFIRM" != "REHEARSE_LIVE_WRITABLE_SCHEDULERS_OFF_NO_DNS" ]]; then
  echo "Exact B1 live-rehearsal confirmation is required." >&2
  exit 2
fi

if [[ ${EUID} -ne 0 ]]; then
  echo "Run the B1 rehearsal as root on the Hetzner app host." >&2
  exit 1
fi
if [[ -z "$RELEASE_FILE" || -z "$JSON_OUT" ]]; then
  echo "Release and JSON output paths are required." >&2
  usage >&2
  exit 2
fi
for required_path in \
  "$RELEASE_FILE" \
  "$RUNTIME_ENV_FILE" \
  "$MARKER_FILE" \
  "$RUNTIME_MARKER" \
  "$VERIFY_SCRIPT"; do
  if [[ ! -f "$required_path" ]]; then
    echo "Missing required B1 file: ${required_path}." >&2
    exit 1
  fi
done

RELEASE_FILE="$(readlink -f "$RELEASE_FILE")"
RUNTIME_ENV_FILE="$(readlink -f "$RUNTIME_ENV_FILE")"
if [[ "$(stat -c '%a' "$RUNTIME_ENV_FILE")" != "600" || \
      "$(stat -c '%u' "$RUNTIME_ENV_FILE")" != "0" ]]; then
  echo "The live runtime env must be root-owned mode 0600." >&2
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
  COMPOSE_FILE="${RELEASE_DIR}/compose-${RELEASE_GIT_SHA}.yml"
fi
if [[ ! -f "$COMPOSE_FILE" ]] || \
   [[ "$(sha256sum "$COMPOSE_FILE" | awk '{print $1}')" != "$DEPLOY_COMPOSE_SHA256" ]]; then
  echo "Compose file does not match the immutable release manifest." >&2
  exit 1
fi
COMPOSE_FILE="$(readlink -f "$COMPOSE_FILE")"

current_release="$(readlink -f "${RELEASE_DIR}/current.env" 2>/dev/null || true)"
if [[ "$current_release" != "$RELEASE_FILE" || \
      ! -f "${RELEASE_DIR}/accepted-${RELEASE_GIT_SHA}.marker" ]]; then
  echo "Release is not the currently accepted immutable shadow." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$MARKER_FILE"
if [[ "${RTBCAT_DATABASE_NAME:-}" != "$EXPECTED_DATABASE" ]]; then
  echo "B1 is restricted to ${EXPECTED_DATABASE}; found ${RTBCAT_DATABASE_NAME:-unset}." >&2
  exit 1
fi

export API_IMAGE DASHBOARD_IMAGE RELEASE_GIT_SHA RELEASE_VERSION
export RTBCAT_RUNTIME_ENV_FILE="$RUNTIME_ENV_FILE"
export RTBCAT_POSTGRES_PASSWORD_FILE="$POSTGRES_PASSWORD_FILE"
export RTBCAT_POSTGRES_CA_FILE="$POSTGRES_CA_FILE"
export RTBCAT_GOOGLE_CREDENTIALS_FILE="$GOOGLE_CREDENTIALS_FILE"
export RTBCAT_DATA_DIR="$DATA_DIR"
export RTBCAT_DATABASE_PRIVATE_IP RTBCAT_DATABASE_NAME RTBCAT_DATABASE_OWNER
export RTBCAT_DEPLOY_GMAIL_SCHEDULER=false
export RTBCAT_DEPLOY_PRECOMPUTE_SCHEDULER=false
export RTBCAT_DEPLOY_CREATIVE_CACHE_SCHEDULER=false

DB_HELPER="$(cat <<'PY'
import json
import os
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import sql

action = sys.argv[1]
database = os.environ["POSTGRES_DB"]
password_bytes = Path(os.environ["POSTGRES_PASSWORD_FILE"]).read_bytes()
if password_bytes.endswith(b"\r\n"):
    password_bytes = password_bytes[:-2]
elif password_bytes.endswith(b"\n"):
    password_bytes = password_bytes[:-1]
password = password_bytes.decode("utf-8")

common = {
    "host": os.environ["POSTGRES_HOST"],
    "port": int(os.environ["POSTGRES_PORT"]),
    "user": os.environ["POSTGRES_USER"],
    "password": password,
    "sslmode": os.environ.get("POSTGRES_SSLMODE", "verify-full"),
    "sslrootcert": os.environ["POSTGRES_SSL_ROOT_CERT_FILE"],
    "connect_timeout": 10,
}

def connect(dbname):
    return psycopg.connect(dbname=dbname, **common)

def session_mode():
    with connect(database) as conn:
        return conn.execute("SHOW transaction_read_only").fetchone()[0]

if action in {"set-on", "set-off"}:
    expected = "on" if action == "set-on" else "off"
    with connect("postgres") as conn:
        conn.autocommit = True
        conn.execute(
            sql.SQL("ALTER DATABASE {} SET default_transaction_read_only = {}").format(
                sql.Identifier(database),
                sql.SQL(expected),
            )
        )
    actual = session_mode()
    if actual != expected:
        raise SystemExit(f"database read-only default is {actual}, expected {expected}")
    print(json.dumps({"database": database, "default_transaction_read_only": actual}))
elif action == "setting":
    print(json.dumps({"database": database, "default_transaction_read_only": session_mode()}))
elif action == "migrations":
    with connect(database) as conn:
        rows = conn.execute(
            "SELECT version FROM schema_migrations ORDER BY applied_at, version"
        ).fetchall()
    print(json.dumps([row[0] for row in rows]))
elif action == "probe":
    probe_schema = "rtbcat_b1_probe_" + uuid.uuid4().hex
    with connect(database) as conn:
        mode = conn.execute("SHOW transaction_read_only").fetchone()[0]
        if mode != "off":
            raise SystemExit(f"probe transaction is read-only: {mode}")
        conn.execute(
            sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(
                sql.Identifier(probe_schema)
            )
        )
        conn.execute(
            sql.SQL("CREATE TABLE {}.probe (id integer PRIMARY KEY)").format(
                sql.Identifier(probe_schema)
            )
        )
        conn.execute(
            sql.SQL("INSERT INTO {}.probe (id) VALUES (1)").format(
                sql.Identifier(probe_schema)
            )
        )
        count = conn.execute(
            sql.SQL("SELECT count(*) FROM {}.probe").format(
                sql.Identifier(probe_schema)
            )
        ).fetchone()[0]
        conn.rollback()
    with connect(database) as conn:
        residue = conn.execute(
            "SELECT to_regnamespace(%s)::text", (probe_schema,)
        ).fetchone()[0]
    if count != 1 or residue is not None:
        raise SystemExit("rollback-only writable probe left unexpected residue")
    print(
        json.dumps(
            {
                "transaction_read_only": mode,
                "inserted_rows": count,
                "rolled_back": True,
                "residue_absent": True,
            }
        )
    )
else:
    raise SystemExit(f"unknown database helper action: {action}")
PY
)"

compose() {
  docker compose --project-name rtbcat-hetzner -f "$COMPOSE_FILE" "$@"
}

run_db_helper() {
  local action="$1"
  compose run --rm --no-deps --entrypoint python api -c "$DB_HELPER" "$action"
}

verify_with_retry() {
  local mode="$1"
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if "$VERIFY_SCRIPT" \
        --release-file "$RELEASE_FILE" \
        --mode "$mode" \
        --with-google; then
      return 0
    fi
    if [[ "$attempt" -lt 6 ]]; then
      sleep 5
    fi
  done
  return 1
}

write_receipt() {
  local status="$1"
  local writable_verified="$2"
  local shadow_restored="$3"
  local tmp
  tmp="$(mktemp)"
  jq -n \
    --arg generated_at "$(date -u +%FT%TZ)" \
    --arg status "$status" \
    --arg release_git_sha "$RELEASE_GIT_SHA" \
    --arg release_version "$RELEASE_VERSION" \
    --arg compose_sha256 "$DEPLOY_COMPOSE_SHA256" \
    --arg script_sha256 "$(sha256sum "$SCRIPT_SELF" | awk '{print $1}')" \
    --argjson writable_verified "$writable_verified" \
    --argjson shadow_restored "$shadow_restored" \
    --argjson database_before "$DB_BEFORE" \
    --argjson database_after "$DB_AFTER" \
    --argjson migrations_before "$MIGRATIONS_BEFORE" \
    --argjson migrations_after "$MIGRATIONS_AFTER" \
    --argjson scheduler_results "$SCHEDULER_RESULTS" \
    --argjson writable_probe "$WRITABLE_PROBE" \
    '{
      generated_at: $generated_at,
      status: $status,
      approval_gate: "B1",
      scope: "bounded live writable Hetzner rehearsal",
      release_git_sha: $release_git_sha,
      release_version: $release_version,
      compose_sha256: $compose_sha256,
      operator_script_sha256: $script_sha256,
      source_authority_changed: false,
      cloud_sql_changed: false,
      dns_changed: false,
      target_scheduler_enabled: false,
      writable_verified: $writable_verified,
      shadow_restored: $shadow_restored,
      database_before: $database_before,
      database_after: $database_after,
      migrations_before: $migrations_before,
      migrations_after: $migrations_after,
      scheduler_refusals: $scheduler_results,
      writable_probe: $writable_probe
    }' > "$tmp"
  install -m 0600 "$tmp" "$JSON_OUT"
  rm -f -- "$tmp"
}

cancel_deadman() {
  if [[ -n "$DEADMAN_UNIT" ]]; then
    systemctl stop "${DEADMAN_UNIT}.timer" >/dev/null 2>&1 || true
    systemctl reset-failed "${DEADMAN_UNIT}.service" >/dev/null 2>&1 || true
  fi
}

restore_shadow() {
  local restore_rc=0
  export RTBCAT_DEPLOY_READ_ONLY_SHADOW=true
  compose stop >/dev/null 2>&1 || restore_rc=1
  if ! DB_AFTER="$(run_db_helper set-on)"; then
    restore_rc=1
  fi
  if ! compose up -d --no-build --remove-orphans; then
    restore_rc=1
  elif ! verify_with_retry shadow; then
    restore_rc=1
  fi
  if [[ "$restore_rc" -eq 0 ]] && \
     jq -e '.default_transaction_read_only == "on"' <<<"$DB_AFTER" >/dev/null; then
    SHADOW_RESTORED="true"
  else
    SHADOW_RESTORED="false"
    restore_rc=1
  fi
  return "$restore_rc"
}

on_exit() {
  local rc=$?
  trap - EXIT INT TERM
  if [[ "$rc" -ne 0 && "$DB_TOUCHED" == "true" && "$SHADOW_RESTORED" != "true" ]]; then
    restore_shadow || true
  fi
  if [[ "$SHADOW_RESTORED" == "true" ]]; then
    cancel_deadman
  fi
  write_receipt failed false "$SHADOW_RESTORED" || true
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT TERM

if [[ "$RESTORE_ONLY" == "true" ]]; then
  DB_TOUCHED="true"
  if ! restore_shadow; then
    exit 1
  fi
  write_receipt restored false true
  trap - EXIT INT TERM
  echo "B1 deadman restored the read-only shadow and database default."
  exit 0
fi

export RTBCAT_DEPLOY_READ_ONLY_SHADOW=true
verify_with_retry shadow
docker exec rtbcat-api python /app/scripts/check_gmail_import_idle.py
DB_BEFORE="$(run_db_helper setting)"
MIGRATIONS_BEFORE="$(run_db_helper migrations)"
if ! jq -e '.default_transaction_read_only == "on"' <<<"$DB_BEFORE" >/dev/null; then
  echo "B1 requires the rehearsal database to start default read-only." >&2
  exit 1
fi

rendered="$(mktemp)"
export RTBCAT_DEPLOY_READ_ONLY_SHADOW=false
compose config --format json > "$rendered"
if ! jq -e \
  --arg api "$API_IMAGE" \
  --arg dashboard "$DASHBOARD_IMAGE" \
  '
    .services.api.image == $api
    and .services.dashboard.image == $dashboard
    and .services.api.environment.CATSCAN_READ_ONLY_SHADOW == "false"
    and .services.api.environment.CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER == "false"
    and .services.api.environment.CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER == "false"
    and .services.api.environment.CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER == "false"
    and all(.services.api.ports[]; .host_ip == "127.0.0.1")
    and all(.services.dashboard.ports[]; .host_ip == "127.0.0.1")
  ' "$rendered" >/dev/null; then
  rm -f -- "$rendered"
  echo "Rendered B1 Compose violates image, listener, mode or scheduler guards." >&2
  exit 1
fi
rm -f -- "$rendered"

if [[ "$PREFLIGHT_ONLY" == "true" ]]; then
  write_receipt preflight-accepted false false
  trap - EXIT INT TERM
  echo "B1 preflight accepted; no containers, database defaults, DNS, GCP or schedulers changed."
  exit 0
fi

DEADMAN_UNIT="rtbcat-b1-deadman-$(date -u +%Y%m%d%H%M%S)"
deadman_receipt="${JSON_OUT%.json}-deadman.json"
systemd-run \
  --quiet \
  --unit="$DEADMAN_UNIT" \
  --on-active=15m \
  --timer-property=AccuracySec=1s \
  "$SCRIPT_SELF" \
    --restore-only \
    --release-file "$RELEASE_FILE" \
    --compose-file "$COMPOSE_FILE" \
    --runtime-env-file "$RUNTIME_ENV_FILE" \
    --json-out "$deadman_receipt" \
    --confirm RESTORE_B1_READ_ONLY_SHADOW

write_receipt prepared false false
DB_TOUCHED="true"
compose stop
run_db_helper set-off >/dev/null
compose up -d --no-build --remove-orphans
verify_with_retry writable-schedulers-off

gmail_status="$(
  curl -sS --max-time 10 -o /dev/null -w '%{http_code}' \
    -X POST http://127.0.0.1:8000/gmail/import/scheduled
)"
precompute_status="$(
  curl -sS --max-time 10 -o /dev/null -w '%{http_code}' \
    -X POST http://127.0.0.1:8000/precompute/refresh/scheduled
)"
creative_status="$(
  curl -sS --max-time 10 -o /dev/null -w '%{http_code}' \
    -X POST http://127.0.0.1:8000/creatives/cache/refresh/scheduled
)"
SCHEDULER_RESULTS="$(
  jq -n \
    --arg gmail "$gmail_status" \
    --arg precompute "$precompute_status" \
    --arg creative "$creative_status" \
    '{gmail_import: $gmail, precompute: $precompute, creative_cache: $creative}'
)"
if ! jq -e \
  '.gmail_import == "503" and .precompute == "503" and .creative_cache == "503"' \
  <<<"$SCHEDULER_RESULTS" >/dev/null; then
  echo "One or more scheduler endpoints did not refuse B1 execution." >&2
  exit 1
fi

WRITABLE_PROBE="$(run_db_helper probe)"
MIGRATIONS_AFTER="$(run_db_helper migrations)"
if ! jq -e \
  '.transaction_read_only == "off" and .rolled_back == true and .residue_absent == true' \
  <<<"$WRITABLE_PROBE" >/dev/null; then
  echo "Rollback-only B1 writable probe failed." >&2
  exit 1
fi

if ! restore_shadow; then
  echo "B1 checks passed, but read-only shadow restoration failed." >&2
  exit 1
fi
cancel_deadman
write_receipt accepted true true
trap - EXIT INT TERM

echo "B1 accepted: writable target verified privately with all schedulers off; read-only shadow and database default were restored."
