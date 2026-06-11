"""Purge all Postgres report/analytics rows for a decommissioned buyer seat.

Created for the 299038253 (Tuky Display) decommission: the seat was
deactivated on 2026-06-11 with a 3-month archive window recorded in
system_settings under key 'data_deletion.299038253'. After the
archive_until date this script deletes the buyer's rows at the Postgres
level. Gmail source emails are intentionally kept (recovery source).

Usage (inside the API container, which has DB credentials):
    python scripts/purge_buyer_data.py --buyer 299038253            # dry run
    python scripts/purge_buyer_data.py --buyer 299038253 --execute  # delete

The script refuses to execute before the archive_until date in the
system_settings marker unless --force is passed.

Deliberately NOT purged (metadata/audit, tiny row counts):
    creatives, creative_live_fetch_telemetry, import_history,
    ingestion_runs, ui_page_load_metrics, pretargeting_configs,
    rtb_endpoints, rtb_endpoints_current, buyer_seats,
    user_buyer_seat_permissions, conversion_* tables
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.postgres_database import pg_execute, pg_query  # noqa: E402

# Tables are matched against information_schema at runtime; a prefix listed
# here only purges if the table actually has a buyer column.
PURGE_TABLE_PREFIXES = (
    "rtb_daily",
    "rtb_bidstream",
    "rtb_bid_filtering",
    "rtb_quality",
    "rtb_app_daily",
    "rtb_funnel_daily",
    "rtb_geo_daily",
    "rtb_publisher_daily",
    "home_",
    "seat_",
    "config_",
    "pretarg_",
    "fact_",
    "web_domain_",
    "performance_metrics",
)

EXCLUDED_TABLES = {
    "creatives",
    "creative_live_fetch_telemetry",
    "import_history",
    "ingestion_runs",
    "ui_page_load_metrics",
    "pretargeting_configs",
    "rtb_endpoints",
    "rtb_endpoints_current",
    "buyer_seats",
    "user_buyer_seat_permissions",
}

BATCH_SIZE = 100_000


async def discover_targets(buyer_id: str) -> list[tuple[str, str]]:
    rows = await pg_query(
        """
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name IN ('buyer_account_id', 'buyer_id')
        ORDER BY table_name
        """
    )
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        table, col = row["table_name"], row["column_name"]
        if table in seen or table in EXCLUDED_TABLES:
            continue
        if not any(table.startswith(p) for p in PURGE_TABLE_PREFIXES):
            continue
        seen.add(table)
        targets.append((table, col))
    return targets


async def archive_gate(buyer_id: str, force: bool) -> None:
    rows = await pg_query(
        "SELECT value FROM system_settings WHERE key = %s",
        (f"data_deletion.{buyer_id}",),
    )
    if not rows:
        if force:
            return
        raise SystemExit(
            f"No system_settings marker 'data_deletion.{buyer_id}' found. "
            "Refusing to purge without a recorded schedule (use --force to override)."
        )
    marker = json.loads(rows[0]["value"])
    archive_until = date.fromisoformat(marker["archive_until"])
    if date.today() < archive_until and not force:
        raise SystemExit(
            f"Archive window for buyer {buyer_id} runs until {archive_until}. "
            "Refusing to purge early (use --force to override)."
        )


async def purge_table(table: str, col: str, buyer_id: str, execute: bool) -> int:
    count_rows = await pg_query(
        f"SELECT COUNT(*) AS c FROM {table} WHERE {col} = %s", (buyer_id,)
    )
    total = int(count_rows[0]["c"])
    if total == 0 or not execute:
        return total

    deleted = 0
    while True:
        n = await pg_execute(
            f"""
            DELETE FROM {table}
            WHERE ctid IN (
                SELECT ctid FROM {table} WHERE {col} = %s LIMIT {BATCH_SIZE}
            )
            """,
            (buyer_id,),
        )
        deleted += n
        print(f"  {table}: deleted {deleted}/{total}", flush=True)
        if n < BATCH_SIZE:
            break
    return deleted


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buyer", required=True, help="buyer_account_id to purge")
    parser.add_argument("--execute", action="store_true", help="actually delete (default: dry run)")
    parser.add_argument("--force", action="store_true", help="skip the archive-window date gate")
    args = parser.parse_args()

    if args.execute:
        await archive_gate(args.buyer, args.force)
    targets = await discover_targets(args.buyer)

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"[{mode}] purge for buyer {args.buyer} across {len(targets)} tables")
    grand_total = 0
    for table, col in targets:
        n = await purge_table(table, col, args.buyer, args.execute)
        grand_total += n
        verb = "deleted" if args.execute else "would delete"
        if n:
            print(f"{table}.{col}: {verb} {n}")
    print(f"[{mode}] total rows: {grand_total}")
    if args.execute:
        await pg_execute(
            """
            UPDATE system_settings
            SET value = value::jsonb || jsonb_build_object('purged_at', CURRENT_DATE::text),
                updated_at = CURRENT_TIMESTAMP
            WHERE key = %s
            """,
            (f"data_deletion.{args.buyer}",),
        )
        print("system_settings marker updated with purged_at")


if __name__ == "__main__":
    asyncio.run(main())
