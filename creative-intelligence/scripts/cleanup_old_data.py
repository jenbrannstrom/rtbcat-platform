#!/usr/bin/env python3
"""
Database Cleanup Script for Cat-Scan

Deletes database records older than the retention period (default: 90 days).
Data is preserved in S3 archives for historical analysis.

Run weekly via cron:
    0 2 * * 0 /opt/catscan/venv/bin/python /opt/catscan/scripts/cleanup_old_data.py

Usage:
    python cleanup_old_data.py              # Run cleanup
    python cleanup_old_data.py --dry-run    # Preview what would be deleted
    python cleanup_old_data.py --days 60    # Custom retention period
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory for imports when running as script
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
CATSCAN_DIR = Path.home() / '.catscan'
DEFAULT_DB_PATH = CATSCAN_DIR / 'catscan.db'
DEFAULT_RETENTION_DAYS = int(os.environ.get('CATSCAN_RETENTION_DAYS', '90'))
LOGS_DIR = CATSCAN_DIR / 'logs'

# Tables and their date columns
TABLES_TO_CLEAN = {
    'rtb_daily': 'day',
    'rtb_funnel': 'day',
    'performance_metrics': 'date',
}

# Tables to preserve (audit/reference data)
TABLES_TO_PRESERVE = [
    'import_history',
    'creatives',
]


def get_db_path() -> Path:
    """Get the database path from environment or default."""
    env_path = os.environ.get('CATSCAN_DB_PATH')
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_DB_PATH


def log(message: str, verbose: bool = True):
    """Log a message with timestamp."""
    if verbose:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")


def get_table_row_count(cursor: sqlite3.Cursor, table: str) -> int:
    """Get the current row count for a table."""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def count_rows_to_delete(cursor: sqlite3.Cursor, table: str, date_column: str, cutoff_date: str) -> int:
    """Count how many rows would be deleted."""
    try:
        cursor.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {date_column} < ?",
            (cutoff_date,)
        )
        return cursor.fetchone()[0]
    except sqlite3.OperationalError as e:
        log(f"  Warning: Could not count {table}: {e}")
        return 0


def delete_old_rows(cursor: sqlite3.Cursor, table: str, date_column: str, cutoff_date: str) -> int:
    """Delete rows older than cutoff date. Returns number of deleted rows."""
    try:
        cursor.execute(
            f"DELETE FROM {table} WHERE {date_column} < ?",
            (cutoff_date,)
        )
        return cursor.rowcount
    except sqlite3.OperationalError as e:
        log(f"  Error deleting from {table}: {e}")
        return 0


def cleanup_database(
    db_path: Path,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    dry_run: bool = False,
    verbose: bool = True
) -> dict:
    """
    Clean up old data from the database.

    Args:
        db_path: Path to the SQLite database
        retention_days: Number of days to retain data
        dry_run: If True, only preview what would be deleted
        verbose: Print progress messages

    Returns:
        Dict with cleanup results
    """
    result = {
        "success": False,
        "dry_run": dry_run,
        "retention_days": retention_days,
        "cutoff_date": None,
        "tables_processed": 0,
        "total_rows_deleted": 0,
        "details": {},
        "errors": []
    }

    if not db_path.exists():
        error = f"Database not found: {db_path}"
        log(error, verbose)
        result["errors"].append(error)
        return result

    cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')
    result["cutoff_date"] = cutoff_date

    log("=" * 60, verbose)
    log(f"Cat-Scan Database Cleanup", verbose)
    log("=" * 60, verbose)
    log(f"Database: {db_path}", verbose)
    log(f"Retention: {retention_days} days", verbose)
    log(f"Cutoff date: {cutoff_date}", verbose)
    log(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE'}", verbose)
    log("", verbose)

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        for table, date_column in TABLES_TO_CLEAN.items():
            log(f"Processing table: {table}", verbose)

            current_count = get_table_row_count(cursor, table)
            rows_to_delete = count_rows_to_delete(cursor, table, date_column, cutoff_date)

            result["details"][table] = {
                "current_rows": current_count,
                "rows_to_delete": rows_to_delete,
                "rows_deleted": 0,
                "date_column": date_column
            }

            if rows_to_delete == 0:
                log(f"  No rows older than {cutoff_date}", verbose)
                continue

            log(f"  Current rows: {current_count:,}", verbose)
            log(f"  Rows to delete: {rows_to_delete:,}", verbose)

            if not dry_run:
                deleted = delete_old_rows(cursor, table, date_column, cutoff_date)
                result["details"][table]["rows_deleted"] = deleted
                result["total_rows_deleted"] += deleted
                log(f"  Deleted: {deleted:,} rows", verbose)
            else:
                log(f"  Would delete: {rows_to_delete:,} rows", verbose)
                result["total_rows_deleted"] += rows_to_delete

            result["tables_processed"] += 1
            log("", verbose)

        if not dry_run and result["total_rows_deleted"] > 0:
            log("Running VACUUM to reclaim disk space...", verbose)
            conn.commit()
            cursor.execute("VACUUM")
            log("VACUUM complete", verbose)
        elif not dry_run:
            conn.commit()

        conn.close()
        result["success"] = True

    except Exception as e:
        error = f"Database error: {e}"
        log(error, verbose)
        result["errors"].append(error)
        return result

    log("=" * 60, verbose)
    if dry_run:
        log(f"DRY RUN: Would delete {result['total_rows_deleted']:,} total rows", verbose)
    else:
        log(f"Cleanup complete: Deleted {result['total_rows_deleted']:,} total rows", verbose)
    log("=" * 60, verbose)

    return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Clean up old data from Cat-Scan database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cleanup_old_data.py              # Run cleanup with 90-day retention
  python cleanup_old_data.py --dry-run    # Preview what would be deleted
  python cleanup_old_data.py --days 60    # Use 60-day retention
  python cleanup_old_data.py --db ~/.catscan/catscan.db  # Specify database
        """
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Preview what would be deleted without making changes'
    )
    parser.add_argument(
        '--days', '-d',
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f'Number of days to retain data (default: {DEFAULT_RETENTION_DAYS})'
    )
    parser.add_argument(
        '--db',
        type=str,
        help=f'Path to database file (default: {DEFAULT_DB_PATH})'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress output'
    )

    args = parser.parse_args()

    db_path = Path(args.db).expanduser() if args.db else get_db_path()

    result = cleanup_database(
        db_path=db_path,
        retention_days=args.days,
        dry_run=args.dry_run,
        verbose=not args.quiet
    )

    if not result["success"]:
        sys.exit(1)


if __name__ == '__main__':
    main()
