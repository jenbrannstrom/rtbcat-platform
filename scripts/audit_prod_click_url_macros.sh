#!/usr/bin/env bash
set -euo pipefail

INSTANCE="${CATSCAN_GCP_INSTANCE:-catscan-production-sg}"
ZONE="${CATSCAN_GCP_ZONE:-asia-southeast1-b}"
PROJECT="${CATSCAN_GCP_PROJECT:-}"
CONTAINER="${CATSCAN_API_CONTAINER:-catscan-api}"
SEAT_LIMIT="${CATSCAN_AUDIT_SEAT_LIMIT:-4}"
PER_SEAT_LIMIT="${CATSCAN_AUDIT_PER_SEAT_LIMIT:-40}"
DAYS="${CATSCAN_AUDIT_DAYS:-30}"
SAMPLE_LIMIT="${CATSCAN_AUDIT_SAMPLE_LIMIT:-8}"
BUYER_IDS="${CATSCAN_AUDIT_BUYER_IDS:-}"
OUT_DIR="${CATSCAN_AUDIT_OUT_DIR:-/tmp}"

usage() {
  cat <<'EOF'
Usage:
  scripts/audit_prod_click_url_macros.sh [options]

Audits real click URL patterns from production creatives and checks Google click macro usage.
By default, scans the 4 most recent active seats and the latest 40 creatives per seat from
the last 30 days.

Options:
  --instance <name>         VM instance (default: catscan-production-sg)
  --zone <zone>             GCP zone (default: asia-southeast1-b)
  --project <id>            Optional GCP project id
  --container <name>        Docker container name (default: catscan-api)
  --seat-limit <n>          Number of active seats to scan (default: 4)
  --per-seat-limit <n>      Recent creatives per seat (default: 40)
  --days <n>                Recency window in days (default: 30)
  --sample-limit <n>        Macro URL samples per seat (default: 8)
  --buyer-ids <csv>         Comma-separated buyer_ids to scan (overrides seat-limit)
  --out-dir <dir>           Local report output dir (default: /tmp)
  -h, --help                Show help

Examples:
  scripts/audit_prod_click_url_macros.sh
  scripts/audit_prod_click_url_macros.sh --project your-project-id --days 14
  scripts/audit_prod_click_url_macros.sh --buyer-ids 1111111111,1234567890 --per-seat-limit 80
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      INSTANCE="${2:-}"
      shift 2
      ;;
    --zone)
      ZONE="${2:-}"
      shift 2
      ;;
    --project)
      PROJECT="${2:-}"
      shift 2
      ;;
    --container)
      CONTAINER="${2:-}"
      shift 2
      ;;
    --seat-limit)
      SEAT_LIMIT="${2:-}"
      shift 2
      ;;
    --per-seat-limit)
      PER_SEAT_LIMIT="${2:-}"
      shift 2
      ;;
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    --sample-limit)
      SAMPLE_LIMIT="${2:-}"
      shift 2
      ;;
    --buyer-ids)
      BUYER_IDS="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
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

if ! command -v gcloud >/dev/null 2>&1; then
  echo "'gcloud' is required but not installed." >&2
  exit 2
fi

if ! gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q .; then
  echo "No active gcloud login found. Run: gcloud auth login" >&2
  exit 2
fi

for v in SEAT_LIMIT PER_SEAT_LIMIT DAYS SAMPLE_LIMIT; do
  if ! [[ "${!v}" =~ ^[0-9]+$ ]] || (( "${!v}" <= 0 )); then
    echo "Invalid ${v}='${!v}'. Expected positive integer." >&2
    exit 2
  fi
done

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR%/}/click_macro_audit_${STAMP}.md"

PY_CODE=$(cat <<'PY'
import os
import re
from collections import Counter
from datetime import datetime

import psycopg

dsn = os.getenv("POSTGRES_SERVING_DSN") or os.getenv("POSTGRES_DSN")
if not dsn:
    raise SystemExit("POSTGRES_SERVING_DSN/POSTGRES_DSN not set in container")

days = int(os.getenv("CATSCAN_AUDIT_DAYS", "30"))
seat_limit = int(os.getenv("CATSCAN_AUDIT_SEAT_LIMIT", "4"))
per_seat = int(os.getenv("CATSCAN_AUDIT_PER_SEAT_LIMIT", "40"))
sample_limit = int(os.getenv("CATSCAN_AUDIT_SAMPLE_LIMIT", "8"))
buyer_csv = (os.getenv("CATSCAN_AUDIT_BUYER_IDS") or "").strip()

macro_re = re.compile(r"%%[A-Z0-9_]+%%")
google_focus = {
    "%%CLICK_URL_ESC%%",
    "%%CLICK_URL_UNESC%%",
    "%%CLICK_URL_ESC_ESC%%",
    "%%WINNING_PRICE%%",
    "%%WINNING_PRICE_ESC%%",
    "%%CACHEBUSTER%%",
    "%%ADVERTISING_IDENTIFIER%%",
}


def extract_urls(row: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if row.get("final_url"):
        out.append(("final_url", str(row["final_url"])))
    if row.get("display_url"):
        out.append(("display_url", str(row["display_url"])))
    raw = row.get("raw_data") or {}
    declared = raw.get("declaredClickThroughUrls") or []
    if isinstance(declared, list):
        for item in declared:
            if item:
                out.append(("declaredClickThroughUrls", str(item)))
    native = raw.get("native") or {}
    if isinstance(native, dict) and native.get("clickLinkUrl"):
        out.append(("native.clickLinkUrl", str(native["clickLinkUrl"])))
    html = raw.get("html") or {}
    snippet = (html.get("snippet") if isinstance(html, dict) else None) or ""
    for item in re.findall(r"https?://[^\s\"<>]+", snippet):
        out.append(("html.snippet", item.rstrip(",;)}]>")))
    return out


with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        seats = []
        if buyer_csv:
            ids = [x.strip() for x in buyer_csv.split(",") if x.strip()]
            cur.execute(
                """
                SELECT buyer_id, bidder_id, COALESCE(display_name, '')
                FROM buyer_seats
                WHERE active = TRUE AND buyer_id = ANY(%s)
                ORDER BY buyer_id
                """,
                (ids,),
            )
            seats = cur.fetchall()
        else:
            cur.execute(
                """
                SELECT buyer_id, bidder_id, COALESCE(display_name, '')
                FROM buyer_seats
                WHERE active = TRUE
                ORDER BY COALESCE(last_synced, created_at) DESC NULLS LAST, buyer_id
                LIMIT %s
                """,
                (seat_limit,),
            )
            seats = cur.fetchall()

        print("# Production Click URL Macro Audit")
        print()
        print(f"- generated_utc: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"- days_window: {days}")
        print(f"- per_seat_limit: {per_seat}")
        print(f"- seats_scanned: {len(seats)}")
        print()

        if not seats:
            print("No active seats matched filter.")
            raise SystemExit(0)

        print("## Seat Summary")
        print()
        print("| buyer_id | bidder_id | seat_name | creatives_scanned | urls_found | creatives_with_macro | creatives_with_click_url_macro | top_macros |")
        print("|---|---|---|---:|---:|---:|---:|---|")

        all_macros: Counter[str] = Counter()
        for buyer_id, bidder_id, display_name in seats:
            cur.execute(
                """
                SELECT id, name, format, COALESCE(updated_at, created_at) AS ts, final_url, display_url, raw_data
                FROM creatives
                WHERE buyer_id = %s
                  AND COALESCE(updated_at, created_at) >= NOW() - (%s::int * INTERVAL '1 day')
                ORDER BY COALESCE(updated_at, created_at) DESC NULLS LAST
                LIMIT %s
                """,
                (str(buyer_id), days, per_seat),
            )
            rows = cur.fetchall()
            if not rows:
                cur.execute(
                    """
                    SELECT id, name, format, COALESCE(updated_at, created_at) AS ts, final_url, display_url, raw_data
                    FROM creatives
                    WHERE buyer_id = %s
                    ORDER BY COALESCE(updated_at, created_at) DESC NULLS LAST
                    LIMIT %s
                    """,
                    (str(buyer_id), per_seat),
                )
                rows = cur.fetchall()

            seat_macros: Counter[str] = Counter()
            macro_samples: list[dict] = []
            url_count = 0
            creatives_with_macro: set[str] = set()
            creatives_with_click: set[str] = set()

            for cid, cname, cfmt, _cts, final_url, display_url, raw_data in rows:
                row = {"final_url": final_url, "display_url": display_url, "raw_data": raw_data}
                urls = extract_urls(row)
                if urls:
                    url_count += len(urls)
                found_for_creative = False
                click_for_creative = False
                for source, url in urls:
                    tokens = macro_re.findall(url or "")
                    if not tokens:
                        continue
                    found_for_creative = True
                    for token in tokens:
                        seat_macros[token] += 1
                        all_macros[token] += 1
                        if "CLICK_URL" in token:
                            click_for_creative = True
                    if len(macro_samples) < sample_limit:
                        macro_samples.append(
                            {
                                "creative_id": str(cid),
                                "name": str(cname or ""),
                                "format": str(cfmt or ""),
                                "source": source,
                                "tokens": sorted(set(tokens)),
                                "url": (url or "")[:280],
                            }
                        )
                if found_for_creative:
                    creatives_with_macro.add(str(cid))
                if click_for_creative:
                    creatives_with_click.add(str(cid))

            top = "; ".join([f"{k} x{v}" for k, v in seat_macros.most_common(5)]) or "(none)"
            safe_name = (display_name or "").replace("|", "/")
            print(
                f"| {buyer_id} | {bidder_id} | {safe_name} | {len(rows)} | {url_count} | "
                f"{len(creatives_with_macro)} | {len(creatives_with_click)} | {top} |"
            )
            print()
            print(f"### Seat {buyer_id} Macro Samples")
            if not macro_samples:
                print("- No macro URLs found in sampled creatives.")
                print()
                continue
            print()
            for sample in macro_samples:
                tokens_joined = ", ".join(sample["tokens"])
                print(
                    f"- creative_id={sample['creative_id']} format={sample['format']} "
                    f"source={sample['source']} tokens=[{tokens_joined}]"
                )
                print(f"  url: {sample['url']}")
            print()

        print("## Global Macro Totals")
        print()
        if not all_macros:
            print("- No macros detected in sampled click URLs.")
        else:
            for token, count in all_macros.most_common():
                focus = " (google-focus)" if token in google_focus or "CLICK_URL" in token else ""
                print(f"- {token}: {count}{focus}")
PY
)

if command -v base64 >/dev/null 2>&1; then
  PY_B64="$(printf '%s' "$PY_CODE" | base64 -w 0)"
else
  echo "'base64' is required but not installed." >&2
  exit 2
fi

REMOTE_CMD=$(cat <<EOF
sudo docker exec \
  -e CATSCAN_AUDIT_DAYS="${DAYS}" \
  -e CATSCAN_AUDIT_SEAT_LIMIT="${SEAT_LIMIT}" \
  -e CATSCAN_AUDIT_PER_SEAT_LIMIT="${PER_SEAT_LIMIT}" \
  -e CATSCAN_AUDIT_SAMPLE_LIMIT="${SAMPLE_LIMIT}" \
  -e CATSCAN_AUDIT_BUYER_IDS="${BUYER_IDS}" \
  "${CONTAINER}" \
  sh -lc '
PY_BIN=""
for cand in /opt/venv/bin/python3 /opt/venv/bin/python /usr/local/bin/python3 /usr/local/bin/python python3 python; do
  if [ "\${cand#/}" != "\$cand" ]; then
    [ -x "\$cand" ] || continue
  else
    command -v "\$cand" >/dev/null 2>&1 || continue
  fi
  if "\$cand" -c "import psycopg" >/dev/null 2>&1; then
    PY_BIN="\$cand"
    break
  fi
done
if [ -z "\$PY_BIN" ]; then
  echo "ERROR: no python with psycopg found in container" >&2
  exit 3
fi
printf %s "${PY_B64}" | base64 -d | "\$PY_BIN" -
'
EOF
)

cmd=(gcloud compute ssh "$INSTANCE" --zone "$ZONE")
if [[ -n "$PROJECT" ]]; then
  cmd+=(--project "$PROJECT")
fi
cmd+=(--tunnel-through-iap -- "$REMOTE_CMD")

echo "Target VM: ${INSTANCE} (${ZONE})"
if [[ -n "$PROJECT" ]]; then
  echo "Project: ${PROJECT}"
fi
echo "Container: ${CONTAINER}"
echo "Seat limit: ${SEAT_LIMIT}  Per-seat limit: ${PER_SEAT_LIMIT}  Days: ${DAYS}"
if [[ -n "$BUYER_IDS" ]]; then
  echo "Buyer filter: ${BUYER_IDS}"
fi
echo

"${cmd[@]}" | tee "$OUT_FILE"

echo
echo "Saved report: ${OUT_FILE}"
