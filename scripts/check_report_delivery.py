#!/usr/bin/env python3
"""Watchdog for Authorized Buyers scheduled-report delivery breakdowns.

Catches the three failure modes from the 2026-07 MobYoung incident
(investigations/RCA-mobyoung-daily-spend-2026-07-13.md):

1. Google never delivered a report email (metric 2026-07-05: 4 of 5 reports
   arrived, the canonical bidsinauction/spend report was silently skipped).
2. A delivered report never became canonical spend rows (import failure).
3. A report was ingested more than once into BigQuery (metric 2026-07-01:
   replayed batch double-counted the published day).

For each seat in CATSCAN_GMAIL_SEAT_IDS and one metric date D (default:
yesterday UTC) it checks:
  - mailbox: which report kinds arrived on delivery days D+1/D+2, vs the
    kinds this seat normally receives (learned from a lookback window, so
    per-seat schedule differences don't need hardcoding);
  - BigQuery rtb_daily: canonical spend lane (report_type='buyer_spend')
    has exactly ONE import batch for (seat, D).

Runs inside the catscan-api container (uses the worker's Gmail token and the
container's BigQuery credentials). Read-only; writes only the --json-out file.

Usage:
  PYTHONPATH=/app python3 scripts/check_report_delivery.py            # yesterday
  PYTHONPATH=/app python3 scripts/check_report_delivery.py --date 2026-07-05
  ... --json-out /home/rtbcat/.catscan/report_delivery_status.json

Exit codes: 0 all clear; 1 alerts found; 2 checker itself failed.
Schedule after the 12:00 UTC import run (e.g. 13:45 UTC) so a normal D+1
delivery has had time to arrive and import.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

REPORT_SENDER = "noreply-google-display-ads-managed-reports@google.com"
SUBJECT_RE = re.compile(r"Authorized Buyers Scheduled Report - (catscan-[a-z-]*?)-(\d{6,})-", re.I)
CANONICAL_KIND = "catscan-bidsinauction"  # feeds report_type='buyer_spend'
# A kind is "expected" for a seat if seen on at least this share of lookback days.
EXPECTED_THRESHOLD = 0.6


def gmail_deliveries(svc, start: date, end: date) -> dict[date, dict[str, set[str]]]:
    """Map delivery-date -> seat -> set of report kinds seen in the mailbox."""
    out: dict[date, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    q = (
        f"from:{REPORT_SENDER} "
        f"after:{start.strftime('%Y/%m/%d')} before:{(end + timedelta(days=1)).strftime('%Y/%m/%d')}"
    )
    token = None
    while True:
        res = (
            svc.users()
            .messages()
            .list(userId="me", q=q, maxResults=100, pageToken=token, includeSpamTrash=True)
            .execute()
        )
        for m in res.get("messages", []):
            meta = (
                svc.users()
                .messages()
                .get(userId="me", id=m["id"], format="metadata", metadataHeaders=["Subject"])
                .execute()
            )
            hdrs = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
            match = SUBJECT_RE.search(hdrs.get("Subject", ""))
            if not match:
                continue
            kind, seat = match.group(1), match.group(2)
            when = datetime.fromtimestamp(int(meta["internalDate"]) / 1000, tz=timezone.utc).date()
            out[when][seat].add(kind)
        token = res.get("nextPageToken")
        if not token:
            return out


def spend_lane_batches(project: str, dataset: str, metric_date: date) -> dict[str, int]:
    """Map seat -> distinct import batch count in the canonical spend lane."""
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    sql = f"""
        SELECT buyer_account_id, COUNT(DISTINCT import_batch_id) AS batches
        FROM `{project}.{dataset}.rtb_daily`
        WHERE report_type = 'buyer_spend' AND metric_date = @d
        GROUP BY buyer_account_id
    """
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("d", "DATE", metric_date)]
        ),
    )
    return {row.buyer_account_id: row.batches for row in job.result()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", help="Metric date YYYY-MM-DD (default: yesterday UTC)")
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--json-out", help="Write machine-readable result here")
    args = parser.parse_args()

    metric_d = (
        date.fromisoformat(args.date)
        if args.date
        else datetime.now(timezone.utc).date() - timedelta(days=1)
    )
    delivery_d = metric_d + timedelta(days=1)  # metric D arrives D+1 (late: D+2)

    seats = [s.strip() for s in os.getenv("CATSCAN_GMAIL_SEAT_IDS", "").split(",") if s.strip()]
    if not seats:
        print("CHECK-ERROR: CATSCAN_GMAIL_SEAT_IDS is empty")
        return 2

    from scripts.gmail_import import get_gmail_service

    svc, _ = get_gmail_service()
    lookback_start = delivery_d - timedelta(days=args.lookback_days)
    deliveries = gmail_deliveries(svc, lookback_start, delivery_d + timedelta(days=1))

    # Learn which kinds each seat normally receives (per delivery day).
    days_seen: dict[str, int] = defaultdict(int)
    kind_days: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for day, per_seat in deliveries.items():
        if day > delivery_d - timedelta(days=1):
            continue  # learn only from days before the one under test
        for seat, kinds in per_seat.items():
            days_seen[seat] += 1
            for kind in kinds:
                kind_days[seat][kind] += 1
    expected = {
        seat: {
            k
            for k, n in kind_days[seat].items()
            if days_seen[seat] and n / days_seen[seat] >= EXPECTED_THRESHOLD
        }
        for seat in seats
    }

    project = os.getenv("BIGQUERY_PROJECT_ID") or os.getenv("GCP_PROJECT_ID", "")
    dataset = os.getenv("BIGQUERY_DATASET", "rtbcat_analytics")
    batches = spend_lane_batches(project, dataset, metric_d)

    alerts: list[str] = []
    result: dict = {
        "metric_date": metric_d.isoformat(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "seats": {},
    }
    for seat in seats:
        arrived = deliveries.get(delivery_d, {}).get(seat, set()) | deliveries.get(
            delivery_d + timedelta(days=1), {}
        ).get(seat, set())
        missing = sorted(expected.get(seat, set()) - arrived)
        n_batches = batches.get(seat, 0)
        if n_batches == 0:
            spend_lane = "missing"
        elif n_batches == 1:
            spend_lane = "ok"
        else:
            spend_lane = f"DUPLICATE({n_batches} batches)"
        result["seats"][seat] = {
            "expected_kinds": sorted(expected.get(seat, set())),
            "arrived_kinds": sorted(arrived),
            "missing_deliveries": missing,
            "spend_lane": spend_lane,
        }
        for kind in missing:
            sev = "CANONICAL-SPEND" if kind == CANONICAL_KIND else "report"
            alerts.append(f"{seat}: {sev} email never arrived for metric {metric_d} ({kind})")
        if spend_lane == "missing" and (
            CANONICAL_KIND in expected.get(seat, set()) or seat in batches
        ):
            alerts.append(f"{seat}: no canonical spend rows in BigQuery for metric {metric_d}")
        if n_batches > 1:
            alerts.append(
                f"{seat}: metric {metric_d} ingested {n_batches}x in spend lane — "
                f"published value is multiplied; dedupe before any refresh"
            )

    result["alerts"] = alerts
    result["ok"] = not alerts
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2))

    print(f"Report delivery check for metric {metric_d} (delivery {delivery_d}):")
    for seat, info in result["seats"].items():
        status = "OK" if not info["missing_deliveries"] and info["spend_lane"] == "ok" else "ALERT"
        print(
            f"  {seat}: {status} — arrived {len(info['arrived_kinds'])}/"
            f"{len(info['expected_kinds'])} expected reports, spend lane {info['spend_lane']}"
        )
    if alerts:
        print("ALERTS:")
        for a in alerts:
            print("  - " + a)
        return 1
    print("All clear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
