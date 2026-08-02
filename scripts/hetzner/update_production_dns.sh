#!/usr/bin/env bash
# Guarded Cloudflare API update for the single RTBcat production A record.

set -euo pipefail

HOSTNAME=""
EXPECTED_CURRENT_IP=""
NEW_IP=""
JSON_OUT=""
TOKEN_ENV="CLOUDFLARE_API_TOKEN"
ZONE_ID_ENV="CLOUDFLARE_ZONE_ID"
TTL=300
APPLY="false"
CONFIRM=""
API_BASE="${CLOUDFLARE_API_BASE:-https://api.cloudflare.com/client/v4}"

usage() {
  cat <<'EOF'
Read-only record preflight:
  CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ZONE_ID=... \
  scripts/hetzner/update_production_dns.sh \
    --hostname scan.rtb.cat \
    --expected-current-ip SOURCE_IPV4 \
    --new-ip TARGET_IPV4 \
    --json-out /secure/evidence/dns-preflight.json

Guarded update (the same command supports an exact rollback by reversing IPs):
  CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ZONE_ID=... \
  scripts/hetzner/update_production_dns.sh \
    --hostname scan.rtb.cat \
    --expected-current-ip SOURCE_IPV4 \
    --new-ip TARGET_IPV4 \
    --json-out /secure/evidence/dns-update.json \
    --apply \
    --confirm UPDATE_SCAN_RTB_CAT_A_RECORD

The script requires exactly one DNS-only A record with the expected current
IPv4. Apply mode writes a mode-0600 prepared recovery receipt before PATCHing
only content, TTL and proxied state, then reads the record back and verifies it.
It never creates or deletes a DNS record.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hostname) HOSTNAME="${2:?missing hostname}"; shift 2 ;;
    --expected-current-ip) EXPECTED_CURRENT_IP="${2:?missing expected IP}"; shift 2 ;;
    --new-ip) NEW_IP="${2:?missing new IP}"; shift 2 ;;
    --json-out) JSON_OUT="${2:?missing JSON output path}"; shift 2 ;;
    --token-env) TOKEN_ENV="${2:?missing token env name}"; shift 2 ;;
    --zone-id-env) ZONE_ID_ENV="${2:?missing zone-id env name}"; shift 2 ;;
    --ttl) TTL="${2:?missing TTL}"; shift 2 ;;
    --apply) APPLY="true"; shift ;;
    --confirm) CONFIRM="${2:?missing confirmation}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$HOSTNAME" != "scan.rtb.cat" ]]; then
  echo "This guarded path is restricted to scan.rtb.cat." >&2
  exit 2
fi
if [[ -z "$EXPECTED_CURRENT_IP" || -z "$NEW_IP" || -z "$JSON_OUT" ]]; then
  echo "Hostname, both IPs and --json-out are required." >&2
  usage >&2
  exit 2
fi
if [[ "$EXPECTED_CURRENT_IP" == "$NEW_IP" ]]; then
  echo "Expected current and new IPs must differ." >&2
  exit 2
fi
ipv4_pattern='^([0-9]{1,3}\.){3}[0-9]{1,3}$'
if ! [[ "$EXPECTED_CURRENT_IP" =~ $ipv4_pattern && "$NEW_IP" =~ $ipv4_pattern ]]; then
  echo "Both addresses must be IPv4 literals." >&2
  exit 2
fi
for ip in "$EXPECTED_CURRENT_IP" "$NEW_IP"; do
  IFS=. read -r a b c d <<<"$ip"
  for octet in "$a" "$b" "$c" "$d"; do
    if (( 10#$octet > 255 )); then
      echo "Invalid IPv4 address: ${ip}" >&2
      exit 2
    fi
  done
done
if ! [[ "$TTL" =~ ^[0-9]+$ ]] || (( TTL < 60 || TTL > 86400 )); then
  echo "TTL must be an integer from 60 through 86400 seconds." >&2
  exit 2
fi
if [[ "$APPLY" == "true" && "$CONFIRM" != "UPDATE_SCAN_RTB_CAT_A_RECORD" ]]; then
  echo "Exact DNS-update confirmation is required." >&2
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

token="${!TOKEN_ENV:-}"
zone_id="${!ZONE_ID_ENV:-}"
if [[ -z "$token" || -z "$zone_id" ]]; then
  echo "Cloudflare token or zone ID environment is empty." >&2
  exit 2
fi
if ! [[ "$zone_id" =~ ^[A-Za-z0-9]{20,64}$ ]]; then
  echo "Cloudflare zone ID is malformed." >&2
  exit 2
fi
for command_name in curl jq install mktemp; do
  if ! command -v "$command_name" >/dev/null; then
    echo "Missing required command: ${command_name}" >&2
    exit 1
  fi
done

tmp_dir="$(mktemp -d)"
cleanup() {
  unset token
  rm -rf -- "$tmp_dir"
}
trap cleanup EXIT

auth_header="Authorization: Bearer ${token}"
records_url="${API_BASE}/zones/${zone_id}/dns_records"
list_response="$(
  curl -fsS --get "$records_url" \
    -H "$auth_header" \
    -H 'Content-Type: application/json' \
    --data-urlencode 'type=A' \
    --data-urlencode "name=${HOSTNAME}"
)"
if ! jq -e '
    .success == true
    and (.errors | length) == 0
    and (.result | length) == 1
  ' <<<"$list_response" >/dev/null; then
  echo "Cloudflare did not return exactly one matching A record." >&2
  exit 1
fi

record="$(jq -c '.result[0]' <<<"$list_response")"
record_id="$(jq -r '.id' <<<"$record")"
if ! jq -e \
    --arg hostname "$HOSTNAME" \
    --arg current "$EXPECTED_CURRENT_IP" '
      .type == "A"
      and .name == $hostname
      and .content == $current
      and .proxied == false
    ' <<<"$record" >/dev/null; then
  echo "DNS record does not match the expected name, current IP or DNS-only state." >&2
  exit 1
fi

write_receipt() {
  local status="$1"
  local applied="$2"
  local after_json="$3"
  local receipt_tmp="$tmp_dir/receipt.json"
  jq -n \
    --arg generated_at "$(date -u +%FT%TZ)" \
    --arg status "$status" \
    --arg hostname "$HOSTNAME" \
    --arg expected_current_ip "$EXPECTED_CURRENT_IP" \
    --arg new_ip "$NEW_IP" \
    --argjson ttl "$TTL" \
    --argjson applied "$applied" \
    --argjson before "$record" \
    --argjson after "$after_json" \
    '{
      report_version: "rtbcat-cloudflare-dns-update.v1",
      generated_at: $generated_at,
      status: $status,
      hostname: $hostname,
      expected_current_ip: $expected_current_ip,
      new_ip: $new_ip,
      ttl: $ttl,
      applied: $applied,
      before: $before,
      after: $after,
      rollback: {
        expected_current_ip: $new_ip,
        new_ip: $expected_current_ip
      }
    }' >"$receipt_tmp"
  install -m 0600 "$receipt_tmp" "$JSON_OUT"
}

if [[ "$APPLY" != "true" ]]; then
  write_receipt accepted false null
  echo "Production DNS read-only preflight accepted; no record changed."
  exit 0
fi

write_receipt prepared false null
payload="$(
  jq -nc \
    --arg content "$NEW_IP" \
    --argjson ttl "$TTL" \
    '{content: $content, ttl: $ttl, proxied: false}'
)"
update_response="$(
  curl -fsS --request PATCH "${records_url}/${record_id}" \
    -H "$auth_header" \
    -H 'Content-Type: application/json' \
    --data "$payload"
)"
if ! jq -e \
    --arg hostname "$HOSTNAME" \
    --arg new_ip "$NEW_IP" \
    --argjson ttl "$TTL" '
      .success == true
      and (.errors | length) == 0
      and .result.type == "A"
      and .result.name == $hostname
      and .result.content == $new_ip
      and .result.ttl == $ttl
      and .result.proxied == false
    ' <<<"$update_response" >/dev/null; then
  echo "Cloudflare PATCH did not return the required updated record." >&2
  exit 1
fi

verify_response="$(
  curl -fsS "${records_url}/${record_id}" \
    -H "$auth_header" \
    -H 'Content-Type: application/json'
)"
if ! jq -e \
    --arg new_ip "$NEW_IP" \
    --argjson ttl "$TTL" '
      .success == true
      and .result.content == $new_ip
      and .result.ttl == $ttl
      and .result.proxied == false
    ' <<<"$verify_response" >/dev/null; then
  echo "Cloudflare read-after-write verification failed; use the prepared receipt for recovery." >&2
  exit 1
fi

updated_record="$(jq -c '.result' <<<"$verify_response")"
write_receipt accepted true "$updated_record"
echo "Updated scan.rtb.cat to the accepted target IP; mode-0600 rollback evidence was preserved."
