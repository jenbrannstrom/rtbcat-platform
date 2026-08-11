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

Restatements are reported ONCE per winning batch: the --json-out file doubles
as state between runs (the wrapper always passes it), so an already-reported
restated day stays muted until another re-delivery changes its winning batch.
The differing batches themselves stay in BigQuery forever — without the mute,
every run would repeat the full list for the whole trailing window.

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


def evaluate_spend_lane(summaries: list[dict]) -> tuple[str, bool]:
    """Classify one (seat, day)'s spend-lane batches under winner semantics.

    Returns (status_label, restated). Identical duplicate batches are fine
    — the batch-aware readers serve exactly one. Differing totals mean the day
    was restated: the newest batch serves, but flag it so a human knows the
    number changed and can confirm the day was re-materialized afterwards.
    """
    if not summaries:
        return "missing", False
    if len(summaries) == 1:
        return "ok", False
    totals = {b["spend_micros"] for b in summaries}
    if len(totals) == 1:
        return f"ok ({len(summaries)} identical batches; newest serves)", False
    return f"RESTATED({len(summaries)} batches)", True


def summarize_days(days: list[str]) -> str:
    """Render a day list compactly: few days verbatim, many as a range."""
    days = sorted(days)
    if len(days) <= 3:
        return ", ".join(days)
    return f"{days[0]} to {days[-1]} ({len(days)} days)"


def render_alert_body(
    metric_d: date,
    delivery_d: date,
    missing_email: list[tuple[str, str, bool]],
    missing_rows: list[str],
    new_restated: dict[str, list[str]],
) -> str | None:
    """Compose the human-readable alert body, or None when all clear.

    The Matrix wrapper posts this verbatim after swapping seat ids for customer
    names, so write for the finance room: plain sentences, one line per
    customer, no batch ids. Policy: dates and seat ids only — never monetary
    values (see the deploy script header).
    """
    money_missing: dict[str, bool] = {}  # seat -> spend rows exist anyway
    secondary: dict[str, list[str]] = defaultdict(list)
    for seat, kind, lane_ok in missing_email:
        if kind == CANONICAL_KIND:
            money_missing[seat] = lane_ok
        else:
            secondary[seat].append(kind)

    sections: list[str] = []
    if money_missing or missing_rows or secondary:
        lines = [f"Report emails from Google for {metric_d} (expected {delivery_d}):"]
        for seat, lane_ok in sorted(money_missing.items()):
            if lane_ok:
                lines.append(
                    f"  - {seat}: the MONEY report email did not arrive, but spend "
                    f"numbers for {metric_d} are already on record — nothing to do."
                )
            else:
                lines.append(
                    f"  - {seat}: the MONEY report email did not arrive and there are "
                    f"no spend numbers for {metric_d} yet. The sheet cannot update "
                    f"until the report is re-sent — re-run the saved report in the "
                    f"Authorized Buyers console (it arrives by email). It may also "
                    f"still arrive late on its own."
                )
        for seat in sorted(missing_rows):
            if seat in money_missing:
                continue  # its line above already says rows are missing
            lines.append(
                f"  - {seat}: the money report email arrived but no spend numbers "
                f"are on record for {metric_d} — the import may have failed."
            )
        for seat, kinds in sorted(secondary.items()):
            lines.append(
                f"  - {seat}: secondary report missing ({', '.join(sorted(kinds))}) "
                f"— the money sheet is not affected."
            )
        sections.append("\n".join(lines))

    if new_restated:
        lines = [
            "Google re-sent money reports for earlier days and the totals CHANGED. "
            "The newest report is now the one served for each day:"
        ]
        for seat, days in sorted(new_restated.items()):
            lines.append(f"  - {seat}: {summarize_days(days)}")
        lines.append(
            "Check those days on the customer sheets after the next update. Each "
            "restatement is reported once — if a day shows up again, Google re-sent "
            "it again."
        )
        sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else None


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

    # --json-out doubles as report-once state for restatements.
    prev_restatements: dict[str, str] = {}
    if args.json_out and Path(args.json_out).exists():
        try:
            prev_restatements = dict(
                json.loads(Path(args.json_out).read_text()).get("restatements") or {}
            )
        except (OSError, ValueError):
            prev_restatements = {}

    missing_email: list[tuple[str, str, bool]] = []  # (seat, kind, lane_ok)
    missing_rows: list[str] = []
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
        spend_lane, _ = evaluate_spend_lane(batches.get((seat, metric_d.isoformat()), []))
        result["seats"][seat] = {
            "expected_kinds": sorted(expected.get(seat, set())),
            "arrived_kinds": sorted(arrived),
            "missing_deliveries": missing,
            "spend_lane": spend_lane,
        }
        for kind in missing:
            missing_email.append((seat, kind, spend_lane.startswith("ok")))
        if spend_lane == "missing" and CANONICAL_KIND in expected.get(seat, set()):
            missing_rows.append(seat)

    # Trailing-window restatement sweep (includes metric_d): a re-delivery is
    # served immediately by the batch-aware readers; surface it only when the
    # batches disagree, and only once per winning batch (see docstring).
    current_restatements: dict[str, str] = {}
    new_restated: dict[str, list[str]] = defaultdict(list)
    for (seat, day), summaries in sorted(batches.items()):
        _, restated = evaluate_spend_lane(summaries)
        if not restated:
            continue
        key = f"{seat}:{day}"
        winner = summaries[0]["batch_id"]
        current_restatements[key] = winner
        if prev_restatements.get(key) != winner:
            new_restated[seat].append(day)

    # Carry known restatements forward even when a manual --date run shifts the
    # query window, dropping entries older than 60 days.
    horizon = (metric_d - timedelta(days=60)).isoformat()
    restatements = {
        k: v for k, v in prev_restatements.items() if k.split(":", 1)[1] >= horizon
    }
    restatements.update(current_restatements)

    body = render_alert_body(metric_d, delivery_d, missing_email, missing_rows, new_restated)
    result["restatements"] = restatements
    result["new_restatements"] = {s: sorted(d) for s, d in new_restated.items()}
    result["alerts"] = body.splitlines() if body else []
    result["ok"] = body is None
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2))

    print(f"Report delivery check for metric {metric_d} (delivery {delivery_d}):")
    for seat, info in result["seats"].items():
        ok = not info["missing_deliveries"] and info["spend_lane"].startswith("ok")
        print(
            f"  {seat}: {'OK' if ok else 'ALERT'} — arrived {len(info['arrived_kinds'])}/"
            f"{len(info['expected_kinds'])} expected reports, spend lane {info['spend_lane']}"
        )
    muted = len(current_restatements) - sum(len(d) for d in new_restated.values())
    if muted:
        print(f"  ({muted} already-reported restated day(s) muted)")
    if body:
        print("ALERTS:")
        print(body)
        return 1
    print("All clear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
