#!/usr/bin/env python3
"""Retention for the partitioned rtb_daily: DROP old partitions, create ahead.

Replaces DELETE-based retention for the raw fact table once the partition
cutover has happened (004_cutover.sql). DROP PARTITION is instant and leaves
no bloat behind.

Dry-run by default; pass --apply to execute drops/creates.

Usage:
    python scripts/partition_migration/partition_retention.py --keep-days 90
    python scripts/partition_migration/partition_retention.py --from-config --apply

--from-config reads raw_retention_days from the global row of the
retention_config table (the same setting the dashboard retention page
writes), so operators keep a single knob.

A whole month is only dropped when every day in it is past the cutoff, so
the effective retention is keep-days rounded up to the month boundary.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, timedelta

import psycopg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", default="rtb_daily",
                        help="Partitioned parent table (default: rtb_daily)")
    keep = parser.add_mutually_exclusive_group(required=True)
    keep.add_argument("--keep-days", type=int,
                      help="Days of raw data to keep")
    keep.add_argument("--from-config", action="store_true",
                      help="Read raw_retention_days from retention_config")
    parser.add_argument("--create-ahead", type=int, default=3,
                        help="Months of future partitions to ensure (default: 3)")
    parser.add_argument("--dsn-env", default="POSTGRES_DSN",
                        help="Env var holding the DB DSN (default: POSTGRES_DSN)")
    parser.add_argument("--apply", action="store_true",
                        help="Execute changes (default: dry-run)")
    return parser.parse_args()


def month_of(partition_name: str, parent: str) -> date | None:
    m = re.fullmatch(re.escape(parent) + r"_(\d{4})(\d{2})", partition_name)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), 1)


def next_month(d: date) -> date:
    return date(d.year + d.month // 12, d.month % 12 + 1, 1)


def main() -> None:
    args = parse_args()
    dsn = os.getenv(args.dsn_env)
    if not dsn:
        sys.exit(f"ERROR: env var {args.dsn_env} is not set")

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_partitioned_table WHERE partrelid = %s::regclass",
            (args.parent,),
        )
        if cur.fetchone() is None:
            sys.exit(f"ERROR: {args.parent} is not partitioned; nothing to do "
                     "(has 004_cutover.sql run?)")

        keep_days = args.keep_days
        if args.from_config:
            cur.execute("SELECT raw_retention_days FROM retention_config "
                        "WHERE seat_id IS NULL")
            row = cur.fetchone()
            if row is None:
                sys.exit("ERROR: --from-config: no global retention_config row")
            keep_days = int(row[0])
        cutoff = date.today() - timedelta(days=keep_days)
        print(f"retention: keep {keep_days} days -> dropping months entirely "
              f"before {cutoff}")

        cur.execute(
            """
            SELECT c.relname, pg_total_relation_size(c.oid)
            FROM pg_inherits i
            JOIN pg_class c ON c.oid = i.inhrelid
            WHERE i.inhparent = %s::regclass
            ORDER BY c.relname
            """,
            (args.parent,),
        )
        partitions = cur.fetchall()

        dropped_bytes = 0
        for name, size in partitions:
            month = month_of(name, args.parent)
            if month is None:
                print(f"  skip {name}: name does not match <parent>_YYYYMM")
                continue
            if next_month(month) <= cutoff:
                dropped_bytes += size
                print(f"  DROP {name} ({size / 1024**3:.1f} GB)")
                if args.apply:
                    cur.execute(
                        psycopg.sql.SQL("DROP TABLE {}").format(
                            psycopg.sql.Identifier(name)))

        cur.execute("SELECT ensure_month_partitions(%s::regclass, "
                    "CURRENT_DATE, %s)", (args.parent, args.create_ahead + 1))
        created = cur.fetchone()[0]
        print(f"  ensured partitions through +{args.create_ahead} months "
              f"({created} created)")

        if args.apply:
            conn.commit()
            print(f"APPLIED: freed {dropped_bytes / 1024**3:.1f} GB")
        else:
            conn.rollback()
            print(f"DRY-RUN: would free {dropped_bytes / 1024**3:.1f} GB "
                  "(pass --apply to execute)")


if __name__ == "__main__":
    main()
