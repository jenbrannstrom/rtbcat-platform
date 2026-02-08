"""Backfill buyer_account_id from import_history filenames.

Uses the seat ID encoded in Cat-Scan filenames (e.g. catscan-quality-<seat>-...).
Only fills rows where buyer_account_id is NULL or empty.
"""

import argparse
import sqlite3
from pathlib import Path

from importers.unified_importer import parse_bidder_id_from_filename

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


def _load_batch_seat_map(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT batch_id, filename FROM import_history WHERE filename IS NOT NULL"
    ).fetchall()
    mapping: dict[str, str] = {}
    for row in rows:
        batch_id = row["batch_id"]
        seat_id = parse_bidder_id_from_filename(row["filename"])
        if batch_id and seat_id:
            mapping[batch_id] = seat_id
    return mapping


def _count_rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS cnt FROM ({sql})", params).fetchone()
    return int(row["cnt"]) if row else 0


def backfill(dry_run: bool = False):
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")

        batch_to_seat = _load_batch_seat_map(conn)
        batch_ids = list(batch_to_seat.keys())

        targets = ["rtb_daily", "rtb_bidstream"]
        for table in targets:
            if not table_exists(conn, table) or not column_exists(conn, table, "buyer_account_id"):
                print(f"{table}: skipped (table/column missing)")
                continue

            if dry_run:
                count = 0
                if batch_ids:
                    placeholders = ",".join("?" for _ in batch_ids)
                    sql = f"""
                        SELECT 1
                        FROM {table}
                        WHERE (buyer_account_id IS NULL OR buyer_account_id = '')
                          AND import_batch_id IN ({placeholders})
                    """
                    count += _count_rows(conn, sql, tuple(batch_ids))

                if column_exists(conn, table, "bidder_id"):
                    sql = f"""
                        SELECT 1
                        FROM {table}
                        WHERE (buyer_account_id IS NULL OR buyer_account_id = '')
                          AND bidder_id IS NOT NULL
                          AND bidder_id != ''
                    """
                    count += _count_rows(conn, sql)

                if table == "rtb_daily" and table_exists(conn, "pretargeting_configs"):
                    sql = """
                        WITH mapping AS (
                            SELECT TRIM(billing_id) AS billing_id, bidder_id
                            FROM pretargeting_configs
                            WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
                            GROUP BY TRIM(billing_id)
                            HAVING COUNT(DISTINCT bidder_id) = 1
                        )
                        SELECT 1
                        FROM rtb_daily d
                        WHERE (d.buyer_account_id IS NULL OR d.buyer_account_id = '')
                          AND d.billing_id IS NOT NULL
                          AND EXISTS (
                              SELECT 1 FROM mapping m
                              WHERE m.billing_id = TRIM(d.billing_id)
                          )
                    """
                    count += _count_rows(conn, sql)

                print(f"{table}: would backfill buyer_account_id for {count} rows")
                continue

            updated = 0
            for batch_id, seat_id in batch_to_seat.items():
                updated += conn.execute(
                    f"""
                    UPDATE {table}
                    SET buyer_account_id = ?
                    WHERE (buyer_account_id IS NULL OR buyer_account_id = '')
                      AND import_batch_id = ?
                    """,
                    (seat_id, batch_id),
                ).rowcount

            if column_exists(conn, table, "bidder_id"):
                updated += conn.execute(
                    f"""
                    UPDATE {table}
                    SET buyer_account_id = bidder_id
                    WHERE (buyer_account_id IS NULL OR buyer_account_id = '')
                      AND bidder_id IS NOT NULL
                      AND bidder_id != ''
                    """
                ).rowcount

            if table == "rtb_daily" and table_exists(conn, "pretargeting_configs"):
                updated += conn.execute(
                    """
                    WITH mapping AS (
                        SELECT TRIM(billing_id) AS billing_id, bidder_id
                        FROM pretargeting_configs
                        WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
                        GROUP BY TRIM(billing_id)
                        HAVING COUNT(DISTINCT bidder_id) = 1
                    )
                    UPDATE rtb_daily
                    SET buyer_account_id = (
                        SELECT bidder_id FROM mapping
                        WHERE mapping.billing_id = TRIM(rtb_daily.billing_id)
                    )
                    WHERE (buyer_account_id IS NULL OR buyer_account_id = '')
                      AND billing_id IS NOT NULL
                      AND EXISTS (
                          SELECT 1 FROM mapping
                          WHERE mapping.billing_id = TRIM(rtb_daily.billing_id)
                      )
                    """
                ).rowcount
            print(f"{table}: backfilled buyer_account_id for {updated} rows")

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
