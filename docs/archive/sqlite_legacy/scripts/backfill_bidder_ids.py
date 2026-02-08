"""Backfill bidder_id fields with 100% accurate mappings only.

Rules:
- Use import_history.batch_id -> bidder_id when available.
- For rtb_daily, also map billing_id -> bidder_id only when unique.
- Never fill when mapping is ambiguous or missing.
"""

import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".catscan" / "catscan.db"


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _count_rows(conn: sqlite3.Connection, sql: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) as cnt FROM ({sql})", ()).fetchone()
    return int(row["cnt"]) if row else 0


def backfill(dry_run: bool = False):
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        if table_exists(conn, "rtb_bidstream") and column_exists(conn, "rtb_bidstream", "bidder_id"):
            bidstream_sql = """
                SELECT 1
                FROM rtb_bidstream
                WHERE bidder_id IS NULL
                  AND import_batch_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM import_history
                      WHERE import_history.batch_id = rtb_bidstream.import_batch_id
                        AND import_history.bidder_id IS NOT NULL
                  )
            """
            if dry_run:
                count = _count_rows(conn, bidstream_sql)
                print(f"rtb_bidstream: would backfill bidder_id for {count} rows")
            else:
                updated = conn.execute(
                    """
                    UPDATE rtb_bidstream
                    SET bidder_id = (
                        SELECT bidder_id FROM import_history
                        WHERE import_history.batch_id = rtb_bidstream.import_batch_id
                          AND import_history.bidder_id IS NOT NULL
                    )
                    WHERE bidder_id IS NULL
                      AND import_batch_id IS NOT NULL
                      AND EXISTS (
                          SELECT 1 FROM import_history
                          WHERE import_history.batch_id = rtb_bidstream.import_batch_id
                            AND import_history.bidder_id IS NOT NULL
                      )
                    """
                ).rowcount
                print(f"rtb_bidstream: backfilled bidder_id via import_history for {updated} rows")
        else:
            print("rtb_bidstream: skipped (table/column missing)")

        if table_exists(conn, "rtb_bid_filtering") and column_exists(conn, "rtb_bid_filtering", "bidder_id"):
            bid_filtering_sql = """
                SELECT 1
                FROM rtb_bid_filtering
                WHERE bidder_id IS NULL
                  AND import_batch_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM import_history
                      WHERE import_history.batch_id = rtb_bid_filtering.import_batch_id
                        AND import_history.bidder_id IS NOT NULL
                  )
            """
            if dry_run:
                count = _count_rows(conn, bid_filtering_sql)
                print(f"rtb_bid_filtering: would backfill bidder_id for {count} rows")
            else:
                updated = conn.execute(
                    """
                    UPDATE rtb_bid_filtering
                    SET bidder_id = (
                        SELECT bidder_id FROM import_history
                        WHERE import_history.batch_id = rtb_bid_filtering.import_batch_id
                          AND import_history.bidder_id IS NOT NULL
                    )
                    WHERE bidder_id IS NULL
                      AND import_batch_id IS NOT NULL
                      AND EXISTS (
                          SELECT 1 FROM import_history
                          WHERE import_history.batch_id = rtb_bid_filtering.import_batch_id
                            AND import_history.bidder_id IS NOT NULL
                      )
                    """
                ).rowcount
                print(f"rtb_bid_filtering: backfilled bidder_id via import_history for {updated} rows")
        else:
            print("rtb_bid_filtering: skipped (table/column missing)")

        if table_exists(conn, "rtb_daily") and column_exists(conn, "rtb_daily", "bidder_id"):
            daily_history_sql = """
                SELECT 1
                FROM rtb_daily
                WHERE bidder_id IS NULL
                  AND import_batch_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM import_history
                      WHERE import_history.batch_id = rtb_daily.import_batch_id
                        AND import_history.bidder_id IS NOT NULL
                  )
            """
            daily_billing_sql = """
                WITH mapping AS (
                    SELECT TRIM(billing_id) AS billing_id, bidder_id
                    FROM pretargeting_configs
                    WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
                    GROUP BY TRIM(billing_id)
                    HAVING COUNT(DISTINCT bidder_id) = 1
                )
                SELECT 1
                FROM rtb_daily
                WHERE bidder_id IS NULL
                  AND billing_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM mapping
                      WHERE mapping.billing_id = TRIM(rtb_daily.billing_id)
                  )
            """
            if dry_run:
                count_history = _count_rows(conn, daily_history_sql)
                count_billing = _count_rows(conn, daily_billing_sql)
                print(f"rtb_daily: would backfill bidder_id via import_history for {count_history} rows")
                print(f"rtb_daily: would backfill bidder_id via billing_id mapping for {count_billing} rows")
            else:
                updated_from_history = conn.execute(
                    """
                    UPDATE rtb_daily
                    SET bidder_id = (
                        SELECT bidder_id FROM import_history
                        WHERE import_history.batch_id = rtb_daily.import_batch_id
                          AND import_history.bidder_id IS NOT NULL
                    )
                    WHERE bidder_id IS NULL
                      AND import_batch_id IS NOT NULL
                      AND EXISTS (
                          SELECT 1 FROM import_history
                          WHERE import_history.batch_id = rtb_daily.import_batch_id
                            AND import_history.bidder_id IS NOT NULL
                      )
                    """
                ).rowcount
                print(f"rtb_daily: backfilled bidder_id via import_history for {updated_from_history} rows")

                updated_from_billing = conn.execute(
                    """
                    WITH mapping AS (
                        SELECT TRIM(billing_id) AS billing_id, bidder_id
                        FROM pretargeting_configs
                        WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
                        GROUP BY TRIM(billing_id)
                        HAVING COUNT(DISTINCT bidder_id) = 1
                    )
                    UPDATE rtb_daily
                    SET bidder_id = (
                        SELECT bidder_id FROM mapping
                        WHERE mapping.billing_id = TRIM(rtb_daily.billing_id)
                    )
                    WHERE bidder_id IS NULL
                      AND billing_id IS NOT NULL
                      AND EXISTS (
                          SELECT 1 FROM mapping
                          WHERE mapping.billing_id = TRIM(rtb_daily.billing_id)
                      )
                    """
                ).rowcount
                print(f"rtb_daily: backfilled bidder_id via billing_id mapping for {updated_from_billing} rows")
        else:
            print("rtb_daily: skipped (table/column missing)")

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show counts only, do not update data")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)
