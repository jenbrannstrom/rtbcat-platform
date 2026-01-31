#!/usr/bin/env python3
"""Backfill bidder_id fields in Postgres with 100% accurate mappings only.

Rules:
- Use import_history.batch_id -> bidder_id when available.
- For rtb_daily, also map billing_id -> bidder_id only when unique.
- Never fill when mapping is ambiguous or missing.

Run on VM with POSTGRES_DSN set:
  python scripts/backfill_bidder_ids_pg.py --dry-run
  python scripts/backfill_bidder_ids_pg.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.postgres_database import pg_query_one, pg_execute


async def table_exists(table: str) -> bool:
    """Check if table exists in Postgres."""
    row = await pg_query_one(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = %s
        ) as exists
        """,
        (table,),
    )
    return row and row.get("exists", False)


async def column_exists(table: str, column: str) -> bool:
    """Check if column exists in table."""
    row = await pg_query_one(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        ) as exists
        """,
        (table, column),
    )
    return row and row.get("exists", False)


async def count_rows(sql: str, params: tuple = ()) -> int:
    """Count rows from a SQL query."""
    row = await pg_query_one(f"SELECT COUNT(*) as cnt FROM ({sql}) sub", params)
    return row["cnt"] if row else 0


async def backfill_rtb_bidstream(dry_run: bool) -> None:
    """Backfill bidder_id in rtb_bidstream via import_history."""
    if not await table_exists("rtb_bidstream"):
        print("rtb_bidstream: skipped (table missing)")
        return
    if not await column_exists("rtb_bidstream", "bidder_id"):
        print("rtb_bidstream: skipped (bidder_id column missing)")
        return

    count_sql = """
        SELECT 1
        FROM rtb_bidstream rb
        WHERE rb.bidder_id IS NULL
          AND rb.import_batch_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM import_history ih
              WHERE ih.batch_id = rb.import_batch_id
                AND ih.bidder_id IS NOT NULL
          )
    """

    if dry_run:
        count = await count_rows(count_sql)
        print(f"rtb_bidstream: would backfill bidder_id for {count:,} rows")
    else:
        updated = await pg_execute(
            """
            UPDATE rtb_bidstream rb
            SET bidder_id = ih.bidder_id
            FROM import_history ih
            WHERE rb.import_batch_id = ih.batch_id
              AND ih.bidder_id IS NOT NULL
              AND rb.bidder_id IS NULL
            """
        )
        print(f"rtb_bidstream: backfilled bidder_id via import_history for {updated:,} rows")


async def backfill_rtb_bid_filtering(dry_run: bool) -> None:
    """Backfill bidder_id in rtb_bid_filtering via import_history."""
    if not await table_exists("rtb_bid_filtering"):
        print("rtb_bid_filtering: skipped (table missing)")
        return
    if not await column_exists("rtb_bid_filtering", "bidder_id"):
        print("rtb_bid_filtering: skipped (bidder_id column missing)")
        return

    count_sql = """
        SELECT 1
        FROM rtb_bid_filtering rbf
        WHERE rbf.bidder_id IS NULL
          AND rbf.import_batch_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM import_history ih
              WHERE ih.batch_id = rbf.import_batch_id
                AND ih.bidder_id IS NOT NULL
          )
    """

    if dry_run:
        count = await count_rows(count_sql)
        print(f"rtb_bid_filtering: would backfill bidder_id for {count:,} rows")
    else:
        updated = await pg_execute(
            """
            UPDATE rtb_bid_filtering rbf
            SET bidder_id = ih.bidder_id
            FROM import_history ih
            WHERE rbf.import_batch_id = ih.batch_id
              AND ih.bidder_id IS NOT NULL
              AND rbf.bidder_id IS NULL
            """
        )
        print(f"rtb_bid_filtering: backfilled bidder_id via import_history for {updated:,} rows")


async def backfill_rtb_quality(dry_run: bool) -> None:
    """Backfill bidder_id in rtb_quality via import_history."""
    if not await table_exists("rtb_quality"):
        print("rtb_quality: skipped (table missing)")
        return
    if not await column_exists("rtb_quality", "bidder_id"):
        print("rtb_quality: skipped (bidder_id column missing)")
        return

    count_sql = """
        SELECT 1
        FROM rtb_quality rq
        WHERE rq.bidder_id IS NULL
          AND rq.import_batch_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM import_history ih
              WHERE ih.batch_id = rq.import_batch_id
                AND ih.bidder_id IS NOT NULL
          )
    """

    if dry_run:
        count = await count_rows(count_sql)
        print(f"rtb_quality: would backfill bidder_id for {count:,} rows")
    else:
        updated = await pg_execute(
            """
            UPDATE rtb_quality rq
            SET bidder_id = ih.bidder_id
            FROM import_history ih
            WHERE rq.import_batch_id = ih.batch_id
              AND ih.bidder_id IS NOT NULL
              AND rq.bidder_id IS NULL
            """
        )
        print(f"rtb_quality: backfilled bidder_id via import_history for {updated:,} rows")


async def backfill_rtb_daily(dry_run: bool) -> None:
    """Backfill bidder_id in rtb_daily via import_history and billing_id mapping."""
    if not await table_exists("rtb_daily"):
        print("rtb_daily: skipped (table missing)")
        return
    if not await column_exists("rtb_daily", "bidder_id"):
        print("rtb_daily: skipped (bidder_id column missing)")
        return

    # Via import_history
    count_history_sql = """
        SELECT 1
        FROM rtb_daily rd
        WHERE rd.bidder_id IS NULL
          AND rd.import_batch_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM import_history ih
              WHERE ih.batch_id = rd.import_batch_id
                AND ih.bidder_id IS NOT NULL
          )
    """

    # Via billing_id -> bidder_id mapping (only when unique)
    count_billing_sql = """
        WITH mapping AS (
            SELECT TRIM(billing_id) AS billing_id, bidder_id
            FROM pretargeting_configs
            WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
            GROUP BY TRIM(billing_id), bidder_id
        ),
        unique_mapping AS (
            SELECT billing_id, MAX(bidder_id) as bidder_id
            FROM mapping
            GROUP BY billing_id
            HAVING COUNT(DISTINCT bidder_id) = 1
        )
        SELECT 1
        FROM rtb_daily rd
        WHERE rd.bidder_id IS NULL
          AND rd.billing_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM unique_mapping um
              WHERE um.billing_id = TRIM(rd.billing_id)
          )
    """

    if dry_run:
        count_history = await count_rows(count_history_sql)
        count_billing = await count_rows(count_billing_sql)
        print(f"rtb_daily: would backfill bidder_id via import_history for {count_history:,} rows")
        print(f"rtb_daily: would backfill bidder_id via billing_id mapping for {count_billing:,} rows")
    else:
        # First, via import_history
        updated_history = await pg_execute(
            """
            UPDATE rtb_daily rd
            SET bidder_id = ih.bidder_id
            FROM import_history ih
            WHERE rd.import_batch_id = ih.batch_id
              AND ih.bidder_id IS NOT NULL
              AND rd.bidder_id IS NULL
            """
        )
        print(f"rtb_daily: backfilled bidder_id via import_history for {updated_history:,} rows")

        # Then, via billing_id mapping (for remaining NULLs)
        updated_billing = await pg_execute(
            """
            WITH mapping AS (
                SELECT TRIM(billing_id) AS billing_id, bidder_id
                FROM pretargeting_configs
                WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
                GROUP BY TRIM(billing_id), bidder_id
            ),
            unique_mapping AS (
                SELECT billing_id, MAX(bidder_id) as bidder_id
                FROM mapping
                GROUP BY billing_id
                HAVING COUNT(DISTINCT bidder_id) = 1
            )
            UPDATE rtb_daily rd
            SET bidder_id = um.bidder_id
            FROM unique_mapping um
            WHERE TRIM(rd.billing_id) = um.billing_id
              AND rd.bidder_id IS NULL
            """
        )
        print(f"rtb_daily: backfilled bidder_id via billing_id mapping for {updated_billing:,} rows")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill bidder_id in Postgres raw fact tables.")
    parser.add_argument("--dry-run", action="store_true", help="Show counts only, do not update data")
    args = parser.parse_args()

    print("=" * 60)
    print("BIDDER_ID BACKFILL (Postgres)")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN - no changes will be made]\n")
    else:
        print("\n[LIVE RUN - updating data]\n")

    await backfill_rtb_bidstream(args.dry_run)
    await backfill_rtb_bid_filtering(args.dry_run)
    await backfill_rtb_quality(args.dry_run)
    await backfill_rtb_daily(args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
