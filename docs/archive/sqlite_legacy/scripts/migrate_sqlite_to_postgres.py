#!/usr/bin/env python3
"""Migrate data from SQLite to PostgreSQL for Cat-Scan.

This script copies all data from the SQLite database to PostgreSQL,
maintaining referential integrity by processing tables in dependency order.

Usage:
    POSTGRES_DSN="postgresql://user:pass@host:5432/dbname" \
    python scripts/migrate_sqlite_to_postgres.py --sqlite /path/to/catscan.db

    # With report output
    python scripts/migrate_sqlite_to_postgres.py --report /tmp/migration_report.json
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg
    from psycopg import sql
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install psycopg[binary]")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default SQLite path
DEFAULT_SQLITE_PATH = "/home/catscan/.catscan/catscan.db"

# Tables in dependency order (parents before children)
# Tables with foreign keys must come after their referenced tables
TABLES_IN_ORDER = [
    # Core tables (no dependencies)
    "schema_migrations",
    "system_settings",
    "retention_config",
    "geographies",

    # Service accounts and users (needed for foreign keys)
    "service_accounts",
    "users",
    "user_sessions",

    # Seats and buyer relationships
    "seats",
    "billing_accounts",
    "buyer_seats",
    "user_service_account_permissions",

    # Creatives and campaigns
    "creatives",
    "campaigns",
    "clusters",
    "campaign_creatives",
    "creative_campaigns",
    "ai_campaigns",

    # Apps and publishers
    "apps",
    "publishers",

    # Performance and metrics
    "performance_metrics",
    "video_metrics",
    "thumbnail_status",

    # RTB data (largest tables)
    "rtb_traffic",
    "rtb_endpoints",
    "rtb_endpoints_current",
    "rtb_quality",
    "rtb_bid_filtering",
    "rtb_funnel_daily",
    "rtb_geo_daily",
    "rtb_publisher_daily",
    "rtb_app_daily",
    "rtb_app_country_daily",
    "rtb_app_creative_daily",
    "rtb_app_size_daily",
    "rtb_bidstream",
    "rtb_daily",

    # Daily summaries
    "daily_creative_summary",
    "daily_upload_summary",
    "account_daily_upload_summary",
    "campaign_daily_summary",

    # Config daily tables
    "config_creative_daily",
    "config_geo_daily",
    "config_publisher_daily",
    "config_size_daily",

    # Home page precomputed tables
    "home_config_daily",
    "home_geo_daily",
    "home_publisher_daily",
    "home_seat_daily",
    "home_size_daily",

    # Import and history
    "gmail_import_runs",
    "import_history",
    "import_anomalies",

    # Pretargeting
    "pretargeting_configs",
    "pretargeting_history",
    "pretargeting_snapshots",
    "pretargeting_change_log",
    "pretargeting_pending_changes",

    # Other
    "recommendations",
    "snapshot_comparisons",
    "audit_log",
    "precompute_refresh_log",
]

# Tables to skip (views or not needed)
SKIP_TABLES = {
    "v_hourly_patterns",
    "v_pending_changes_summary",
    "v_platform_efficiency",
    "v_publisher_waste",
    "v_rtb_bidstream_production",
    "v_rtb_daily_production",
    "sqlite_sequence",
}

# Batch size for large tables
BATCH_SIZE = 10000


def get_postgres_dsn() -> str:
    """Get PostgreSQL connection string from environment."""
    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("POSTGRES_DSN or DATABASE_URL environment variable must be set")
    return dsn


def get_sqlite_tables(sqlite_conn: sqlite3.Connection) -> list[str]:
    """Get list of tables in SQLite database."""
    cursor = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row[0] for row in cursor.fetchall()]


def get_table_columns(sqlite_conn: sqlite3.Connection, table: str) -> list[str]:
    """Get column names for a table."""
    cursor = sqlite_conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def get_row_count(sqlite_conn: sqlite3.Connection, table: str) -> int:
    """Get row count for a table."""
    cursor = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]


def table_exists_in_postgres(pg_conn: psycopg.Connection, table: str) -> bool:
    """Check if table exists in PostgreSQL."""
    cursor = pg_conn.execute(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
        (table,)
    )
    return cursor.fetchone()[0]


def get_postgres_columns(pg_conn: psycopg.Connection, table: str) -> list[str]:
    """Get column names from PostgreSQL table."""
    cursor = pg_conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [row[0] for row in cursor.fetchall()]


def get_postgres_column_types(pg_conn: psycopg.Connection, table: str) -> dict[str, str]:
    """Get column types from PostgreSQL table."""
    cursor = pg_conn.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table,)
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_serial_columns(pg_conn: psycopg.Connection, table: str) -> set[str]:
    """Get columns that use SERIAL/auto-increment in PostgreSQL."""
    cursor = pg_conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_default LIKE 'nextval%%'
        """,
        (table,)
    )
    return {row[0] for row in cursor.fetchall()}


def convert_row(row: tuple, columns: list[str], pg_types: dict[str, str]) -> tuple:
    """Convert SQLite row values to PostgreSQL compatible types.

    Handles:
    - Boolean: SQLite uses 0/1, PostgreSQL needs True/False
    - Large integers: Ensure they fit in BIGINT
    """
    converted = []
    for i, (col, val) in enumerate(zip(columns, row)):
        if val is None:
            converted.append(None)
            continue

        pg_type = pg_types.get(col, "")

        # Convert SQLite integer booleans to Python bool
        if pg_type == "boolean":
            if isinstance(val, int):
                converted.append(bool(val))
            elif isinstance(val, str):
                converted.append(val.lower() in ("true", "1", "yes"))
            else:
                converted.append(bool(val))
        else:
            converted.append(val)

    return tuple(converted)


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn: psycopg.Connection,
    table: str,
    batch_size: int = BATCH_SIZE
) -> dict[str, Any]:
    """Migrate a single table from SQLite to PostgreSQL.

    Returns:
        Dict with migration stats for this table.
    """
    result = {
        "table": table,
        "sqlite_count": 0,
        "postgres_count": 0,
        "migrated": 0,
        "skipped": False,
        "error": None,
    }

    # Check if table exists in Postgres
    if not table_exists_in_postgres(pg_conn, table):
        logger.warning(f"Table {table} does not exist in PostgreSQL, skipping")
        result["skipped"] = True
        result["error"] = "Table not in PostgreSQL schema"
        return result

    # Get SQLite row count
    sqlite_count = get_row_count(sqlite_conn, table)
    result["sqlite_count"] = sqlite_count

    if sqlite_count == 0:
        logger.info(f"Table {table}: 0 rows, skipping")
        return result

    # Get columns that exist in both databases
    sqlite_cols = set(get_table_columns(sqlite_conn, table))
    pg_cols = set(get_postgres_columns(pg_conn, table))
    common_cols = list(sqlite_cols & pg_cols)

    if not common_cols:
        logger.warning(f"Table {table}: no common columns between SQLite and PostgreSQL")
        result["skipped"] = True
        result["error"] = "No common columns"
        return result

    # Get PostgreSQL column types for conversion
    pg_types = get_postgres_column_types(pg_conn, table)

    # Skip SERIAL columns - let Postgres auto-generate them
    serial_cols = get_serial_columns(pg_conn, table)
    if serial_cols:
        logger.info(f"  Skipping SERIAL columns: {serial_cols}")
        common_cols = [c for c in common_cols if c not in serial_cols]

    if not common_cols:
        logger.warning(f"Table {table}: no columns left after removing SERIAL columns")
        result["skipped"] = True
        result["error"] = "Only SERIAL columns"
        return result

    logger.info(f"Migrating {table}: {sqlite_count} rows, {len(common_cols)} columns")

    # Build SQL statements
    cols_str = ", ".join(common_cols)
    placeholders = ", ".join(["%s"] * len(common_cols))

    # Use ON CONFLICT DO NOTHING to handle duplicates gracefully
    insert_sql = f"""
        INSERT INTO {table} ({cols_str})
        VALUES ({placeholders})
        ON CONFLICT DO NOTHING
    """

    # Migrate in batches
    total_migrated = 0
    offset = 0

    while offset < sqlite_count:
        # Fetch batch from SQLite
        cursor = sqlite_conn.execute(
            f"SELECT {cols_str} FROM {table} LIMIT {batch_size} OFFSET {offset}"
        )
        rows = cursor.fetchall()

        if not rows:
            break

        # Convert rows to PostgreSQL compatible types
        converted_rows = [convert_row(row, common_cols, pg_types) for row in rows]

        # Insert into PostgreSQL
        try:
            with pg_conn.cursor() as pg_cursor:
                pg_cursor.executemany(insert_sql, converted_rows)
            pg_conn.commit()
            total_migrated += len(rows)
        except Exception as e:
            pg_conn.rollback()
            logger.error(f"Error migrating {table} at offset {offset}: {e}")
            result["error"] = str(e)
            break

        offset += batch_size
        if offset % (batch_size * 10) == 0:
            logger.info(f"  {table}: {offset}/{sqlite_count} rows migrated")

    result["migrated"] = total_migrated

    # Get final Postgres count
    cursor = pg_conn.execute(f"SELECT COUNT(*) FROM {table}")
    result["postgres_count"] = cursor.fetchone()[0]

    logger.info(f"Completed {table}: {total_migrated} rows migrated, {result['postgres_count']} total in Postgres")

    return result


def run_migration(
    sqlite_path: str,
    report_path: str | None = None
) -> dict[str, Any]:
    """Run the full migration from SQLite to PostgreSQL.

    Returns:
        Migration report as dict.
    """
    report = {
        "started_at": datetime.utcnow().isoformat(),
        "sqlite_path": sqlite_path,
        "tables": [],
        "summary": {
            "total_tables": 0,
            "migrated_tables": 0,
            "skipped_tables": 0,
            "failed_tables": 0,
            "total_rows_migrated": 0,
        },
        "completed_at": None,
        "success": False,
    }

    # Connect to databases
    logger.info(f"Connecting to SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    logger.info("Connecting to PostgreSQL")
    pg_conn = psycopg.connect(get_postgres_dsn())

    try:
        # Get all SQLite tables
        sqlite_tables = set(get_sqlite_tables(sqlite_conn))
        logger.info(f"Found {len(sqlite_tables)} tables in SQLite")

        # Determine tables to migrate
        tables_to_migrate = []
        for table in TABLES_IN_ORDER:
            if table in sqlite_tables and table not in SKIP_TABLES:
                tables_to_migrate.append(table)

        # Add any tables not in our ordered list
        for table in sqlite_tables:
            if table not in TABLES_IN_ORDER and table not in SKIP_TABLES:
                tables_to_migrate.append(table)

        logger.info(f"Will migrate {len(tables_to_migrate)} tables")
        report["summary"]["total_tables"] = len(tables_to_migrate)

        # Migrate each table
        for table in tables_to_migrate:
            try:
                result = migrate_table(sqlite_conn, pg_conn, table)
                report["tables"].append(result)

                if result["skipped"]:
                    report["summary"]["skipped_tables"] += 1
                elif result["error"]:
                    report["summary"]["failed_tables"] += 1
                else:
                    report["summary"]["migrated_tables"] += 1
                    report["summary"]["total_rows_migrated"] += result["migrated"]

            except Exception as e:
                logger.error(f"Failed to migrate {table}: {e}")
                report["tables"].append({
                    "table": table,
                    "error": str(e),
                    "skipped": False,
                })
                report["summary"]["failed_tables"] += 1

        report["success"] = report["summary"]["failed_tables"] == 0

    finally:
        sqlite_conn.close()
        pg_conn.close()

    report["completed_at"] = datetime.utcnow().isoformat()

    # Write report if path specified
    if report_path:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report written to {report_path}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL")
    parser.add_argument(
        "--sqlite",
        default=DEFAULT_SQLITE_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_SQLITE_PATH})"
    )
    parser.add_argument(
        "--report",
        help="Path to write JSON migration report"
    )

    args = parser.parse_args()

    if not Path(args.sqlite).exists():
        logger.error(f"SQLite database not found: {args.sqlite}")
        return 1

    try:
        report = run_migration(args.sqlite, args.report)

        # Print summary
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Total tables:     {report['summary']['total_tables']}")
        print(f"Migrated:         {report['summary']['migrated_tables']}")
        print(f"Skipped:          {report['summary']['skipped_tables']}")
        print(f"Failed:           {report['summary']['failed_tables']}")
        print(f"Total rows:       {report['summary']['total_rows_migrated']:,}")
        print("=" * 60)

        if report["success"]:
            logger.info("Migration completed successfully!")
            return 0
        else:
            logger.error("Migration completed with errors")
            return 1

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
