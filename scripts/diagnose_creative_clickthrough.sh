#!/usr/bin/env bash
set -euo pipefail

CREATIVE_ID="${CATSCAN_CREATIVE_ID:-}"
BASE_URL="${CATSCAN_API_BASE_URL:-https://scan.rtb.cat/api}"
CANARY_EMAIL="${CATSCAN_CANARY_EMAIL:-${CATSCAN_CANARY_BEARER_TOKEN:-}}"
SESSION_COOKIE="${CATSCAN_SESSION_COOKIE:-${CATSCAN_CANARY_SESSION_COOKIE:-}}"
TIMEOUT_SECONDS="${CATSCAN_CANARY_TIMEOUT_SECONDS:-60}"
OUTPUT_DIR="${CATSCAN_OUTPUT_DIR:-/tmp}"

usage() {
  cat <<'EOF'
Usage:
  scripts/diagnose_creative_clickthrough.sh --creative-id <id> [options]

Diagnoses creative clickthrough resolution using:
  GET /creatives/{creative_id}/destination-diagnostics

Options:
  --creative-id <id>      Creative ID (required)
  --base-url <url>        API base URL (default: https://scan.rtb.cat/api)
  --email <email>         X-Email identity (default: CATSCAN_CANARY_EMAIL or CATSCAN_CANARY_BEARER_TOKEN)
  --session-cookie <val>  Cookie header value (default: CATSCAN_SESSION_COOKIE/CATSCAN_CANARY_SESSION_COOKIE)
  --timeout <seconds>     Request timeout (default: 60)
  --out-dir <dir>         Artifact directory root (default: /tmp)
  -h, --help              Show help

Examples:
  export CATSCAN_CANARY_EMAIL="cat-scan@rtb.cat"
  scripts/diagnose_creative_clickthrough.sh --creative-id 207574524_intertplmraidexp_274444172_1784661_banner_intertplmraidexp_9259
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --creative-id)
      CREATIVE_ID="${2:-}"
      shift 2
      ;;
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --email)
      CANARY_EMAIL="${2:-}"
      shift 2
      ;;
    --session-cookie)
      SESSION_COOKIE="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$CREATIVE_ID" ]]; then
  echo "--creative-id is required." >&2
  exit 2
fi
if [[ -z "$CANARY_EMAIL" && -z "$SESSION_COOKIE" ]]; then
  echo "Provide --email (preferred) or --session-cookie for authenticated API access." >&2
  exit 2
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "'curl' is required." >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "'jq' is required." >&2
  exit 2
fi
if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 5 )); then
  echo "Invalid --timeout '${TIMEOUT_SECONDS}'. Expected integer >= 5." >&2
  exit 2
fi

BASE_URL="${BASE_URL%/}"
RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${OUTPUT_DIR%/}/creative-clickthrough-${RUN_STAMP}"
mkdir -p "$RUN_DIR"

BODY_FILE="${RUN_DIR}/destination_diagnostics.json"
META_FILE="${RUN_DIR}/destination_diagnostics.meta"
ERR_FILE="${RUN_DIR}/destination_diagnostics.err"

ENCODED_CREATIVE_ID="$(jq -rn --arg v "$CREATIVE_ID" '$v|@uri')"
TARGET_URL="${BASE_URL}/creatives/${ENCODED_CREATIVE_ID}/destination-diagnostics"

curl_args=(
  -sS
  -m "$TIMEOUT_SECONDS"
  -o "$BODY_FILE"
  -w "http=%{http_code} connect=%{time_connect} ttfb=%{time_starttransfer} total=%{time_total}\n"
)
if [[ -n "$CANARY_EMAIL" ]]; then
  curl_args+=(-H "X-Email: ${CANARY_EMAIL}")
fi
if [[ -n "$SESSION_COOKIE" ]]; then
  curl_args+=(-H "Cookie: ${SESSION_COOKIE}")
fi

set +e
curl "${curl_args[@]}" "$TARGET_URL" >"$META_FILE" 2>"$ERR_FILE"
curl_status=$?
set -e

echo "Run dir: ${RUN_DIR}"
echo "Creative ID: ${CREATIVE_ID}"
echo "Base URL: ${BASE_URL}"
if [[ -n "$CANARY_EMAIL" ]]; then
  echo "X-Email: ${CANARY_EMAIL}"
fi
echo

if [[ "$curl_status" -ne 0 ]]; then
  echo "request_status=curl_exit_${curl_status}"
  if [[ -s "$ERR_FILE" ]]; then
    echo "curl_error=$(tr '\n' ' ' < "$ERR_FILE")"
  fi
  echo "Result: FAIL"
  exit 1
fi

echo "request_meta: $(cat "$META_FILE")"
HTTP_CODE="$(sed -n '1s/.*http=\([^ ]*\).*/\1/p' "$META_FILE")"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "request_http=${HTTP_CODE}"
  preview="$(head -c 500 "$BODY_FILE" | tr '\n' ' ')"
  if [[ -n "$preview" ]]; then
    echo "response_preview=${preview}"
  fi
  echo "Result: FAIL"
  exit 1
fi

if ! jq -e . "$BODY_FILE" >/dev/null 2>&1; then
  echo "response_error=non_json_payload"
  echo "Result: FAIL"
  exit 1
fi

resolved_url="$(jq -r '.resolved_destination_url // ""' "$BODY_FILE")"
candidate_count="$(jq -r '.candidate_count // 0' "$BODY_FILE")"
eligible_count="$(jq -r '.eligible_count // 0' "$BODY_FILE")"
first_eligible_source="$(jq -r '.candidates[] | select(.eligible == true) | .source' "$BODY_FILE" | head -n1)"
if [[ -z "${first_eligible_source}" ]]; then
  first_eligible_source="(none)"
fi

echo
echo "=== Destination Resolution Summary ==="
echo "resolved_destination_url=${resolved_url:-"(none)"}"
echo "candidate_count=${candidate_count}"
echo "eligible_count=${eligible_count}"
echo "first_eligible_source=${first_eligible_source}"
echo
echo "=== Candidate Breakdown ==="
jq -r '
  (.candidates // [])
  | if length == 0 then
      "(none)"
    else
      .[] | [
        .source,
        (if .eligible then "eligible" else "rejected" end),
        (.reason // "-"),
        .url
      ] | @tsv
    end
' "$BODY_FILE" | sed 's/\t/ | /g'

macro_count="$(jq -r '[.candidates[]? | select(.reason == "contains_click_macro")] | length' "$BODY_FILE")"
asset_count="$(jq -r '[.candidates[]? | select(.reason == "asset_url")] | length' "$BODY_FILE")"
duplicate_count="$(jq -r '[.candidates[]? | select(.reason == "duplicate")] | length' "$BODY_FILE")"

echo
echo "=== RCA Hint ==="
if [[ -z "$resolved_url" ]]; then
  echo "No eligible click destination resolved."
  if (( macro_count > 0 )); then
    echo "- Found macro-only URLs. Click macros were not resolved into concrete destination URLs."
  fi
  if (( asset_count > 0 )); then
    echo "- Found asset URLs (image/video/font/script) that are not valid click-through destinations."
  fi
  echo "- Action: verify final URL / declared click-through URLs in Google buyer creative."
  echo "- Action: if HTML creative, ensure clickable href contains a real landing page URL."
  echo "Result: FAIL"
  exit 1
fi

if (( asset_count > 0 )); then
  echo "Resolved destination is valid, but asset URLs were also present and filtered out."
fi
if (( duplicate_count > 0 )); then
  echo "Multiple sources pointed to the same destination URL."
fi
echo "Result: PASS"
