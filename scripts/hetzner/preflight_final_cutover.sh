#!/usr/bin/env bash
# Read-only final-cutover preflight. This script never pauses schedulers, stops
# containers, changes PostgreSQL, changes DNS, or enables the Hetzner app.

set -euo pipefail

JSON_OUT=""

usage() {
  cat <<'EOF'
Usage:
  CUTOVER_GCP_ACCOUNT=... \
  CUTOVER_GCP_PROJECT=... \
  CUTOVER_GCP_ZONE=... \
  CUTOVER_GCP_VM=... \
  CUTOVER_CLOUD_SQL_INSTANCE=... \
  CUTOVER_DB_SSH=user@host \
  CUTOVER_APP_SSH=user@host \
  CUTOVER_PRODUCTION_HOSTNAME=... \
  CUTOVER_TEMP_HOSTNAME=... \
  CUTOVER_EXPECTED_RELEASE_PREFIX=... \
  CUTOVER_EXPECTED_GCP_IPV4=... \
  CUTOVER_EXPECTED_HETZNER_IPV4=... \
  CUTOVER_EXPECTED_BACKUP_LABEL=... \
  scripts/hetzner/preflight_final_cutover.sh \
    --json-out /secure/evidence/final-cutover-preflight.json

This command is read-only. It verifies the authoritative GCP release/VM/Cloud
SQL/schedulers/import-idle state, both DNS records, the continuously catching
up target subscription and backup repository, and the sealed Hetzner app.

The output parent must already exist. The receipt is written mode 0600.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json-out) JSON_OUT="${2:?missing JSON output path}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

required_env=(
  CUTOVER_GCP_ACCOUNT
  CUTOVER_GCP_PROJECT
  CUTOVER_GCP_ZONE
  CUTOVER_GCP_VM
  CUTOVER_CLOUD_SQL_INSTANCE
  CUTOVER_DB_SSH
  CUTOVER_APP_SSH
  CUTOVER_PRODUCTION_HOSTNAME
  CUTOVER_TEMP_HOSTNAME
  CUTOVER_EXPECTED_RELEASE_PREFIX
  CUTOVER_EXPECTED_GCP_IPV4
  CUTOVER_EXPECTED_HETZNER_IPV4
  CUTOVER_EXPECTED_BACKUP_LABEL
)
for env_name in "${required_env[@]}"; do
  if [[ -z "${!env_name:-}" ]]; then
    echo "Required environment variable is empty: ${env_name}" >&2
    exit 2
  fi
done

if [[ -z "$JSON_OUT" ]]; then
  echo "--json-out is required." >&2
  usage >&2
  exit 2
fi
if [[ "$JSON_OUT" != /* ]]; then
  echo "--json-out must be an absolute path." >&2
  exit 2
fi
output_parent="$(dirname "$JSON_OUT")"
if [[ ! -d "$output_parent" ]]; then
  echo "JSON output parent does not exist: ${output_parent}" >&2
  exit 1
fi
if [[ -L "$JSON_OUT" ]]; then
  echo "Refusing symlink JSON output: ${JSON_OUT}" >&2
  exit 1
fi

required_commands=(curl dig gcloud jq ssh install mktemp)
for command_name in "${required_commands[@]}"; do
  if ! command -v "$command_name" >/dev/null; then
    echo "Missing required command: ${command_name}" >&2
    exit 1
  fi
done

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf -- "$tmp_dir"
}
trap cleanup EXIT

ssh_options=(-o BatchMode=yes -o ConnectTimeout=12)

health_json="$(
  curl -fsS --max-time 20 \
    "https://${CUTOVER_PRODUCTION_HOSTNAME}/api/health"
)"
cloud_sql_json="$(
  gcloud --account="$CUTOVER_GCP_ACCOUNT" sql instances describe \
    "$CUTOVER_CLOUD_SQL_INSTANCE" \
    --project="$CUTOVER_GCP_PROJECT" \
    --format=json
)"
schedulers_json="$(
  gcloud --account="$CUTOVER_GCP_ACCOUNT" scheduler jobs list \
    --project="$CUTOVER_GCP_PROJECT" \
    --location="${CUTOVER_GCP_ZONE%-*}" \
    --format=json
)"
source_vm_json="$(
  gcloud --account="$CUTOVER_GCP_ACCOUNT" compute instances describe \
    "$CUTOVER_GCP_VM" \
    --project="$CUTOVER_GCP_PROJECT" \
    --zone="$CUTOVER_GCP_ZONE" \
    --format=json
)"
source_import_json="$(
  gcloud --account="$CUTOVER_GCP_ACCOUNT" compute ssh "$CUTOVER_GCP_VM" \
    --project="$CUTOVER_GCP_PROJECT" \
    --zone="$CUTOVER_GCP_ZONE" \
    --tunnel-through-iap \
    --command='sudo docker exec catscan-api python3 scripts/gmail_import.py --status'
)"

production_ipv4="$(
  dig +short A "$CUTOVER_PRODUCTION_HOSTNAME" | sort -u
)"
temp_ipv4="$(
  dig +short A "$CUTOVER_TEMP_HOSTNAME" | sort -u
)"
temp_http_code="$(
  curl -ksS --max-time 20 -o /dev/null -w '%{http_code}' \
    "https://${CUTOVER_TEMP_HOSTNAME}/"
)"

db_services="$(
  ssh "${ssh_options[@]}" "$CUTOVER_DB_SSH" \
    'sudo -n systemctl is-active postgresql rtbcat-cloudsql-logical-proxy.service rtbcat-b3c-monitor.timer rtbcat-pgbackrest-diff.timer rtbcat-pgbackrest-check.timer'
)"
target_db_json="$(
  ssh "${ssh_options[@]}" "$CUTOVER_DB_SSH" \
    "sudo -n -u postgres psql -X -d rtbcat_serving -At -c \"SELECT json_build_object('ready', count(*) FILTER (WHERE srsubstate = 'r'), 'not_ready', count(*) FILTER (WHERE srsubstate <> 'r'), 'subscription_enabled', (SELECT subenabled FROM pg_subscription WHERE subname = 'rtbcat_hetzner_migration'), 'generated_buyer', (SELECT attgenerated = 's' FROM pg_attribute WHERE attrelid = 'public.rtb_daily'::regclass AND attname = 'buyer_id' AND NOT attisdropped), 'id_bigint', (SELECT atttypid = 'bigint'::regtype FROM pg_attribute WHERE attrelid = 'public.rtb_daily'::regclass AND attname = 'id' AND NOT attisdropped), 'database_bytes', pg_database_size(current_database())) FROM pg_subscription_rel;\""
)"
monitor_json="$(
  ssh "${ssh_options[@]}" "$CUTOVER_DB_SSH" \
    'sudo -n tail -n 1 /var/log/rtbcat/logical-replication-monitor.jsonl'
)"
backup_json="$(
  ssh "${ssh_options[@]}" "$CUTOVER_DB_SSH" \
    'sudo -n -u postgres pgbackrest --stanza=rtbcat info --output=json'
)"

app_nginx="$(
  ssh "${ssh_options[@]}" "$CUTOVER_APP_SSH" \
    'sudo -n systemctl is-active nginx' || true
)"
app_oauth="$(
  ssh "${ssh_options[@]}" "$CUTOVER_APP_SSH" \
    'sudo -n systemctl is-active rtbcat-temp-oauth2-proxy.service' || true
)"
app_container_count="$(
  ssh "${ssh_options[@]}" "$CUTOVER_APP_SSH" \
    "sudo -n docker ps -q | wc -l | tr -d '[:space:]'"
)"

health_ok=false
if jq -e --arg prefix "$CUTOVER_EXPECTED_RELEASE_PREFIX" '
    (.status == "healthy")
    and (((.git_sha // .version // "") | sub("^sha-"; "")) | startswith($prefix))
  ' <<<"$health_json" >/dev/null; then
  health_ok=true
fi

cloud_sql_ok=false
if jq -e '
    .state == "RUNNABLE"
    and .databaseVersion == "POSTGRES_15"
    and any(.settings.databaseFlags[]?;
      .name == "cloudsql.logical_decoding" and .value == "on")
    and .settings.backupConfiguration.enabled == true
    and .settings.backupConfiguration.pointInTimeRecoveryEnabled == true
  ' <<<"$cloud_sql_json" >/dev/null; then
  cloud_sql_ok=true
fi

schedulers_ok=false
if jq -e --arg host "https://${CUTOVER_PRODUCTION_HOSTNAME}/" '
    length == 3
    and ([.[].name | split("/")[-1]] | sort) ==
      (["creative-cache-refresh", "gmail-import", "precompute-refresh"] | sort)
    and all(.[]; .state == "ENABLED")
    and all(.[]; (.httpTarget.uri // "") | startswith($host))
  ' <<<"$schedulers_json" >/dev/null; then
  schedulers_ok=true
fi

source_vm_ok=false
if jq -e '.status == "RUNNING"' <<<"$source_vm_json" >/dev/null; then
  source_vm_ok=true
fi

source_idle_ok=false
if jq -e '.running == false and .last_error == null' \
    <<<"$source_import_json" >/dev/null; then
  source_idle_ok=true
fi

production_dns_ok=false
if [[ "$production_ipv4" == "$CUTOVER_EXPECTED_GCP_IPV4" ]]; then
  production_dns_ok=true
fi
temp_dns_ok=false
if [[ "$temp_ipv4" == "$CUTOVER_EXPECTED_HETZNER_IPV4" ]]; then
  temp_dns_ok=true
fi

db_services_ok=false
if [[ "$(grep -cx active <<<"$db_services")" -eq 5 ]]; then
  db_services_ok=true
fi

target_db_ok=false
if jq -e '
    .ready == 98
    and .not_ready == 0
    and .subscription_enabled == true
    and .generated_buyer == true
    and .id_bigint == true
  ' <<<"$target_db_json" >/dev/null; then
  target_db_ok=true
fi

monitor_ok=false
if jq -e '
    .status == "ok"
    and .target.subscription_count == 1
    and .target.table_states.r == 98
    and ([.source_slots[].retained_bytes] | max) <= 67108864
    and .target_free_bytes >= .thresholds.target_min_free_bytes
  ' <<<"$monitor_json" >/dev/null; then
  monitor_ok=true
fi

backup_ok=false
if jq -e --arg label "$CUTOVER_EXPECTED_BACKUP_LABEL" '
    length == 1
    and .[0].status.code == 0
    and .[0].repo[0].status.code == 0
    and any(.[0].backup[]?; .label == $label and .error == false)
  ' <<<"$backup_json" >/dev/null; then
  backup_ok=true
fi

app_sealed_ok=false
if [[ "$app_nginx" == "active" && \
      "$app_oauth" == "inactive" && \
      "$app_container_count" == "0" && \
      "$temp_http_code" == "502" ]]; then
  app_sealed_ok=true
fi

report_tmp="$tmp_dir/report.json"
jq -n \
  --arg generated_at "$(date -u +%FT%TZ)" \
  --arg production_hostname "$CUTOVER_PRODUCTION_HOSTNAME" \
  --arg temp_hostname "$CUTOVER_TEMP_HOSTNAME" \
  --arg production_ipv4 "$production_ipv4" \
  --arg temp_ipv4 "$temp_ipv4" \
  --arg temp_http_code "$temp_http_code" \
  --arg app_nginx "$app_nginx" \
  --arg app_oauth "$app_oauth" \
  --argjson app_container_count "$app_container_count" \
  --argjson health_ok "$health_ok" \
  --argjson cloud_sql_ok "$cloud_sql_ok" \
  --argjson schedulers_ok "$schedulers_ok" \
  --argjson source_vm_ok "$source_vm_ok" \
  --argjson source_idle_ok "$source_idle_ok" \
  --argjson production_dns_ok "$production_dns_ok" \
  --argjson temp_dns_ok "$temp_dns_ok" \
  --argjson db_services_ok "$db_services_ok" \
  --argjson target_db_ok "$target_db_ok" \
  --argjson monitor_ok "$monitor_ok" \
  --argjson backup_ok "$backup_ok" \
  --argjson app_sealed_ok "$app_sealed_ok" \
  --argjson health "$health_json" \
  --argjson target_database "$target_db_json" \
  --argjson monitor "$monitor_json" \
  --argjson source_import "$source_import_json" \
  '{
    report_version: "rtbcat-final-cutover-preflight.v1",
    generated_at: $generated_at,
    mode: "read-only",
    authority_changed: false,
    checks: {
      production_health: $health_ok,
      cloud_sql: $cloud_sql_ok,
      schedulers: $schedulers_ok,
      source_vm: $source_vm_ok,
      source_import_idle: $source_idle_ok,
      production_dns: $production_dns_ok,
      temp_dns: $temp_dns_ok,
      target_database_services: $db_services_ok,
      target_database: $target_db_ok,
      replication_monitor: $monitor_ok,
      target_backup: $backup_ok,
      target_app_sealed: $app_sealed_ok
    },
    observed: {
      production_hostname: $production_hostname,
      temp_hostname: $temp_hostname,
      production_ipv4: $production_ipv4,
      temp_ipv4: $temp_ipv4,
      temp_http_code: $temp_http_code,
      app_nginx: $app_nginx,
      app_oauth: $app_oauth,
      app_container_count: $app_container_count,
      health: $health,
      source_import: $source_import,
      target_database: $target_database,
      monitor: $monitor
    }
  }
  | .ready_for_freeze = ([.checks[]] | all)
  ' >"$report_tmp"

install -m 0600 "$report_tmp" "$JSON_OUT"
if jq -e '.ready_for_freeze == true' "$report_tmp" >/dev/null; then
  echo "Final-cutover read-only preflight accepted: ${JSON_OUT}"
  exit 0
fi

echo "Final-cutover read-only preflight failed: ${JSON_OUT}" >&2
jq -r '.checks | to_entries[] | select(.value == false) | "failed_check=" + .key' \
  "$report_tmp" >&2
exit 1
