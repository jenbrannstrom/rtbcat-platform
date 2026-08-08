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
    batches for (seat, D) agree with each other. Multiple batches per day are
    normal since the batch-aware readers landed (redundant schedules,
    re-deliveries) — the readers serve only the newest batch; an alert fires
    only when batches carry DIFFERING totals (a restatement to confirm).

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


def spend_lane_batches(
    project: str, dataset: str, metric_date: date, window_days: int = 14
) -> dict[tuple[str, str], list[dict]]:
    """Map (seat, iso date) -> per-batch spend summaries in the canonical spend
    lane over a trailing window, winner first (the readers' ordering: newest
    created_at, batch id as tiebreak). Since the batch-aware readers landed,
    multiple batches per day are NORMAL (redundant schedules, re-deliveries);
    what matters is whether the batches agree and which one the readers serve."""
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    sql = f"""
        SELECT buyer_account_id, metric_date, import_batch_id,
               SUM(spend_micros) AS spend_micros,
               MAX(created_at) AS batch_created_at
        FROM `{project}.{dataset}.rtb_daily`
        WHERE report_type = 'buyer_spend' AND metric_date BETWEEN @s AND @d
        GROUP BY buyer_account_id, metric_date, import_batch_id
    """
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("s", "DATE", metric_date - timedelta(days=window_days - 1)),
                bigquery.ScalarQueryParameter("d", "DATE", metric_date),
            ]
        ),
    )
    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in job.result():
        out[(row.buyer_account_id, row.metric_date.isoformat())].append(
            {
                "batch_id": row.import_batch_id or "",
                "spend_micros": int(row.spend_micros or 0),
                "created_at": row.batch_created_at,
            }
        )
    for summaries in out.values():
        summaries.sort(
            key=lambda b: (
                b["created_at"] or datetime(1970, 1, 1, tzinfo=timezone.utc),
                b["batch_id"],
            ),
            reverse=True,
        )
    return dict(out)


def evaluate_spend_lane(summaries: list[dict], day: str, seat: str) -> tuple[str, str | None]:
    """Classify one (seat, day)'s spend-lane batches under winner semantics.

    Returns (status_label, alert_or_None). Identical duplicate batches are fine
    — the batch-aware readers serve exactly one. Differing totals mean the day
    was restated: the newest batch serves, but flag it so a human knows the
    number changed and can confirm the day was re-materialized afterwards.
    """
    if not summaries:
        return "missing", None
    if len(summaries) == 1:
        return "ok", None
    totals = {b["spend_micros"] for b in summaries}
    if len(totals) == 1:
        return f"ok ({len(summaries)} identical batches; newest serves)", None
    winner = summaries[0]
    return (
        f"RESTATED({len(summaries)} batches)",
        f"{seat}: metric {day} has {len(summaries)} spend-lane batches with "
        f"DIFFERING totals — the newest (batch {winner['batch_id']}) is the one "
        f"served; confirm the day was re-materialized after it arrived",
    )


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
        # Strict same-day check: subjects carry no metric date ("yesterday-UTC"),
        # so an email on D+2 is normally the NEXT day's report, not a late one.
        # A late-but-recovered day shows up here as missing email + spend lane ok.
        arrived = deliveries.get(delivery_d, {}).get(seat, set())
        missing = sorted(expected.get(seat, set()) - arrived)
        summaries = batches.get((seat, metric_d.isoformat()), [])
        spend_lane, lane_alert = evaluate_spend_lane(summaries, metric_d.isoformat(), seat)
        result["seats"][seat] = {
            "expected_kinds": sorted(expected.get(seat, set())),
            "arrived_kinds": sorted(arrived),
            "missing_deliveries": missing,
            "spend_lane": spend_lane,
        }
        for kind in missing:
            sev = "CANONICAL-SPEND" if kind == CANONICAL_KIND else "report"
            alerts.append(
                f"{seat}: {sev} email did not arrive on its normal day ({delivery_d}) "
                f"for metric {metric_d} ({kind}) — may still arrive late; spend-lane "
                f"status is the ground truth"
            )
        if spend_lane == "missing" and (
            CANONICAL_KIND in expected.get(seat, set()) or (seat, metric_d.isoformat()) in batches
        ):
            alerts.append(f"{seat}: no canonical spend rows in BigQuery for metric {metric_d}")
        if lane_alert:
            alerts.append(lane_alert)

    # Trailing-window restatement sweep: a re-delivery landing on an OLD metric
    # date is served immediately by the batch-aware readers; surface it only
    # when the batches disagree (a genuine restatement someone should confirm).
    seat_set = set(seats)
    for (seat, day), summaries in sorted(batches.items()):
        if day == metric_d.isoformat() and seat in seat_set:
            continue  # already evaluated above
        _, lane_alert = evaluate_spend_lane(summaries, day, seat)
        if lane_alert:
            alerts.append(lane_alert)

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
