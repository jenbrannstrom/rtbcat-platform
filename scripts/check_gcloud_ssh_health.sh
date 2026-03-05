#!/usr/bin/env bash
#
# Diagnose where `gcloud compute ssh` is failing:
# 1) DNS resolution (compute.googleapis.com)
# 2) HTTPS reachability to Compute API
# 3) gcloud auth/account/token
# 4) VM SSH/IAP path
#
# Default target matches current prod VM usage, but can be overridden.

set -u

INSTANCE="catscan-vm-prod"
ZONE="asia-southeast1-b"
PROJECT=""
API_HOST="compute.googleapis.com"
SSH_COMMAND="echo ok"
TIMEOUT_SECS="30"
CHECK_SSH="1"

usage() {
  cat <<'EOF'
Usage: scripts/check_gcloud_ssh_health.sh [options]

Options:
  --instance NAME         VM instance name (default: catscan-vm-prod)
  --zone ZONE             GCE zone (default: asia-southeast1-b)
  --project PROJECT       GCP project (optional)
  --api-host HOST         API hostname to test (default: compute.googleapis.com)
  --ssh-command CMD       Command to run over gcloud ssh (default: "echo ok")
  --timeout SECONDS       Per-check timeout (default: 30)
  --skip-ssh              Skip the final VM SSH check (DNS/API/auth only)
  --help                  Show this help

Exit codes:
  0  ok
  2  dependency missing
  10 dns failure
  11 api reachability failure
  12 gcloud auth failure
  13 vm ssh / iap failure
  14 usage error
EOF
}

log() {
  printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"
}

pass() {
  log "PASS: $*"
}

fail() {
  local code="$1"
  shift
  log "FAIL: $*"
  exit "$code"
}

need_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || fail 2 "missing dependency: $cmd"
}

run_capture() {
  # Usage: run_capture OUTVAR STATUSVAR cmd ...
  local __outvar="$1"
  local __statusvar="$2"
  shift 2
  local out
  out="$("$@" 2>&1)"
  local status=$?
  printf -v "$__outvar" '%s' "$out"
  printf -v "$__statusvar" '%s' "$status"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      [[ $# -ge 2 ]] || fail 14 "--instance requires a value"
      INSTANCE="$2"
      shift 2
      ;;
    --zone)
      [[ $# -ge 2 ]] || fail 14 "--zone requires a value"
      ZONE="$2"
      shift 2
      ;;
    --project)
      [[ $# -ge 2 ]] || fail 14 "--project requires a value"
      PROJECT="$2"
      shift 2
      ;;
    --api-host)
      [[ $# -ge 2 ]] || fail 14 "--api-host requires a value"
      API_HOST="$2"
      shift 2
      ;;
    --ssh-command)
      [[ $# -ge 2 ]] || fail 14 "--ssh-command requires a value"
      SSH_COMMAND="$2"
      shift 2
      ;;
    --timeout)
      [[ $# -ge 2 ]] || fail 14 "--timeout requires a value"
      TIMEOUT_SECS="$2"
      shift 2
      ;;
    --skip-ssh)
      CHECK_SSH="0"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail 14 "unknown argument: $1 (use --help)"
      ;;
  esac
done

need_cmd timeout
need_cmd gcloud
need_cmd curl

log "Starting gcloud/SSH health check"
log "Target VM: instance=$INSTANCE zone=$ZONE project=${PROJECT:-<default>}"
log "Compute API host: $API_HOST"
log "Per-check timeout: ${TIMEOUT_SECS}s"

# 1) DNS resolution
DNS_OUT=""
DNS_STATUS=1
if command -v getent >/dev/null 2>&1; then
  run_capture DNS_OUT DNS_STATUS timeout "${TIMEOUT_SECS}s" getent ahosts "$API_HOST"
elif command -v dig >/dev/null 2>&1; then
  run_capture DNS_OUT DNS_STATUS timeout "${TIMEOUT_SECS}s" dig +short "$API_HOST"
else
  fail 2 "need either getent or dig for DNS check"
fi

if [[ "$DNS_STATUS" != "0" ]] || [[ -z "${DNS_OUT//[[:space:]]/}" ]]; then
  fail 10 "DNS resolution failed for $API_HOST${DNS_OUT:+ :: $DNS_OUT}"
fi
pass "DNS resolves $API_HOST"

# 2) Compute API HTTPS reachability (any HTTP response proves DNS/TLS/network path)
CURL_OUT=""
CURL_STATUS=1
run_capture CURL_OUT CURL_STATUS timeout "${TIMEOUT_SECS}s" curl -sS -o /dev/null -w '%{http_code}' "https://${API_HOST}/"
if [[ "$CURL_STATUS" != "0" ]]; then
  fail 11 "HTTPS reachability failed for https://${API_HOST}/ :: $CURL_OUT"
fi
if [[ ! "$CURL_OUT" =~ ^[0-9]{3}$ ]]; then
  fail 11 "unexpected HTTP code output from curl: '$CURL_OUT'"
fi
pass "Compute API host reachable over HTTPS (HTTP $CURL_OUT)"

# 3) gcloud auth/account/token
AUTH_ACCT_OUT=""
AUTH_ACCT_STATUS=1
run_capture AUTH_ACCT_OUT AUTH_ACCT_STATUS timeout "${TIMEOUT_SECS}s" gcloud auth list --filter=status:ACTIVE --format=value\(account\)
if [[ "$AUTH_ACCT_STATUS" != "0" ]] || [[ -z "${AUTH_ACCT_OUT//[[:space:]]/}" ]]; then
  fail 12 "gcloud has no active authenticated account :: $AUTH_ACCT_OUT"
fi
pass "gcloud active account detected (${AUTH_ACCT_OUT%%$'\n'*})"

AUTH_TOKEN_OUT=""
AUTH_TOKEN_STATUS=1
run_capture AUTH_TOKEN_OUT AUTH_TOKEN_STATUS timeout "${TIMEOUT_SECS}s" gcloud auth print-access-token --quiet
if [[ "$AUTH_TOKEN_STATUS" != "0" ]] || [[ -z "${AUTH_TOKEN_OUT//[[:space:]]/}" ]]; then
  fail 12 "failed to obtain gcloud access token :: $AUTH_TOKEN_OUT"
fi
pass "gcloud access token obtained"

if [[ "$CHECK_SSH" != "1" ]]; then
  pass "SSH check skipped (--skip-ssh)"
  exit 0
fi

# 4) VM SSH / IAP path
GCLOUD_SSH_CMD=(gcloud compute ssh "$INSTANCE" --zone "$ZONE" --tunnel-through-iap -- "$SSH_COMMAND")
if [[ -n "$PROJECT" ]]; then
  GCLOUD_SSH_CMD=(gcloud compute ssh "$INSTANCE" --zone "$ZONE" --project "$PROJECT" --tunnel-through-iap -- "$SSH_COMMAND")
fi

SSH_OUT=""
SSH_STATUS=1
run_capture SSH_OUT SSH_STATUS timeout "${TIMEOUT_SECS}s" "${GCLOUD_SSH_CMD[@]}"

if [[ "$SSH_STATUS" != "0" ]]; then
  if [[ "$SSH_OUT" == *"Failed to resolve '${API_HOST}'"* ]]; then
    fail 10 "intermittent DNS failure during gcloud compute ssh metadata lookup :: $SSH_OUT"
  fi
  if [[ "$SSH_OUT" == *"Reauthentication required"* ]] || [[ "$SSH_OUT" == *"There was a problem refreshing your current auth tokens"* ]]; then
    fail 12 "gcloud auth/token refresh failure during ssh :: $SSH_OUT"
  fi
  fail 13 "VM SSH/IAP failure :: $SSH_OUT"
fi

pass "gcloud compute ssh succeeded"
log "RESULT: OK"
exit 0
