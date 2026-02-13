#!/usr/bin/env python3
"""PostgreSQL migration runner for Cat-Scan.

Reads POSTGRES_DSN from environment and applies migrations from
storage/postgres_migrations/ in order.

Usage:
    POSTGRES_DSN="postgresql://user:pass@host:5432/dbname" python scripts/postgres_migrate.py

    # Or with DATABASE_URL
    DATABASE_URL="postgresql://..." python scripts/postgres_migrate.py

    # Dry run (show pending migrations without applying)
    python scripts/postgres_migrate.py --dry-run

    # Show current migration status
    python scripts/postgres_migrate.py --status

    # Audit schema_migrations version markers (numeric vs canonical)
    python scripts/postgres_migrate.py --audit-versions
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install psycopg[binary]")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Migration files directory
MIGRATIONS_DIR = Path(__file__).parent.parent / "storage" / "postgres_migrations"


def get_dsn() -> str:
    """Get PostgreSQL connection string from environment."""
    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "POSTGRES_DSN or DATABASE_URL environment variable must be set.\n"
            "Example: postgresql://user:pass@localhost:5432/catscan"
        )
    return dsn


def get_connection() -> psycopg.Connection:
    """Create a new PostgreSQL connection."""
    dsn = get_dsn()
    return psycopg.connect(dsn)


def ensure_migrations_table(conn: psycopg.Connection) -> None:
    """Create schema_migrations table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            description TEXT
        )
    """)
    # Backward compatibility: older installs created this table without
    # description, but newer SQL migrations insert into that column.
    conn.execute("ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS description TEXT")
    conn.commit()


def get_applied_migrations(conn: psycopg.Connection) -> set[str]:
    """Get set of already-applied migration versions."""
    cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row[0] for row in cursor.fetchall()}


def extract_migration_number(version: str) -> Optional[int]:
    """Extract numeric migration order from a version marker.

    Examples:
      - "027_schema_alignment" -> 27
      - "27" -> 27
      - "001_init" -> 1
    """
    match = re.match(r"^0*(\d+)(?:_.*)?$", str(version).strip())
    if not match:
        return None
    return int(match.group(1))


def _get_applied_migration_numbers(applied_versions: set[str]) -> set[int]:
    """Get numeric migration IDs represented by applied version markers."""
    numbers: set[int] = set()
    for version in applied_versions:
        number = extract_migration_number(version)
        if number is not None:
            numbers.add(number)
    return numbers


def filter_pending_migrations(
    pending: list[tuple[str, Path]],
    applied_versions: set[str],
) -> tuple[list[tuple[str, Path]], list[tuple[str, int]]]:
    """Filter pending migrations using exact and numeric-equivalent matching.

    Returns:
        Tuple:
        - Migrations to apply.
        - Migrations skipped because a numeric-equivalent marker already exists.
    """
    applied_numbers = _get_applied_migration_numbers(applied_versions)
    to_apply: list[tuple[str, Path]] = []
    skipped_legacy: list[tuple[str, int]] = []

    for version, filepath in pending:
        if version in applied_versions:
            continue

        number = extract_migration_number(version)
        if number is not None and number in applied_numbers:
            skipped_legacy.append((version, number))
            continue

        to_apply.append((version, filepath))

    return to_apply, skipped_legacy


def get_pending_migrations() -> list[tuple[str, Path]]:
    """Get list of pending migration files sorted by version.

    Returns:
        List of (version, filepath) tuples sorted by version.
    """
    if not MIGRATIONS_DIR.exists():
        logger.warning(f"Migrations directory not found: {MIGRATIONS_DIR}")
        return []

    migrations = []
    pattern = re.compile(r"^(\d+)_.*\.sql$")

    for filepath in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = pattern.match(filepath.name)
        if match:
            version = match.group(1) + "_" + filepath.stem.split("_", 1)[1]
            migrations.append((version, filepath))

    return migrations


def apply_migration(conn: psycopg.Connection, version: str, filepath: Path) -> bool:
    """Apply a single migration file.

    Args:
        conn: Database connection
        version: Migration version string (e.g., "001_init")
        filepath: Path to .sql file

    Returns:
        True if successful, False otherwise.
    """
    logger.info(f"Applying migration: {version}")

    try:
        sql = filepath.read_text()

        # Execute migration SQL
        conn.execute(sql)

        # Record migration (if not already in the SQL)
        conn.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
            (version,)
        )

        conn.commit()
        logger.info(f"Successfully applied: {version}")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to apply {version}: {e}")
        return False


def run_migrations(dry_run: bool = False) -> tuple[int, int]:
    """Run all pending migrations.

    Args:
        dry_run: If True, only show what would be applied.

    Returns:
        Tuple of (applied_count, failed_count).
    """
    conn = get_connection()

    try:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)
        pending = get_pending_migrations()

        # Filter to only pending migrations (including numeric-equivalent markers)
        to_apply, skipped_legacy = filter_pending_migrations(pending, applied)

        if skipped_legacy:
            for version, number in skipped_legacy:
                logger.info(
                    "Skipping %s (numeric-equivalent migration marker already present: %s)",
                    version,
                    number,
                )

        if not to_apply:
            logger.info("No pending migrations.")
            return 0, 0

        logger.info(f"Found {len(to_apply)} pending migration(s):")
        for version, filepath in to_apply:
            logger.info(f"  - {version} ({filepath.name})")

        if dry_run:
            logger.info("Dry run mode - no changes applied.")
            return 0, 0

        applied_count = 0
        failed_count = 0

        for version, filepath in to_apply:
            if apply_migration(conn, version, filepath):
                applied_count += 1
            else:
                failed_count += 1
                # Stop on first failure to maintain consistency
                logger.error("Stopping due to migration failure.")
                break

        return applied_count, failed_count

    finally:
        conn.close()


def show_status() -> None:
    """Show current migration status."""
    conn = get_connection()

    try:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)
        pending = get_pending_migrations()

        print("\n=== Migration Status ===\n")

        print("Applied migrations:")
        if applied:
            for version in sorted(applied):
                print(f"  [x] {version}")
        else:
            print("  (none)")

        print("\nPending migrations:")
        pending_versions, skipped_legacy = filter_pending_migrations(pending, applied)
        if pending_versions:
            for version, filepath in pending_versions:
                print(f"  [ ] {version} ({filepath.name})")
        else:
            print("  (none)")

        if skipped_legacy:
            print("\nSkipped due to numeric-equivalent applied marker:")
            for version, number in skipped_legacy:
                print(f"  [~] {version} (already marked by {number})")

        print()

    finally:
        conn.close()


def audit_version_markers() -> int:
    """Audit schema_migrations for mixed numeric/canonical version markers.

    Returns:
        0 when no anomalies found, 1 when mixed or unparseable markers exist.
    """
    conn = get_connection()
    try:
        ensure_migrations_table(conn)
        cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        versions = [str(row[0]) for row in cursor.fetchall()]
    finally:
        conn.close()

    if not versions:
        print("No schema_migrations rows found.")
        return 0

    by_number: dict[int, list[str]] = {}
    unparseable: list[str] = []

    for version in versions:
        number = extract_migration_number(version)
        if number is None:
            unparseable.append(version)
            continue
        by_number.setdefault(number, []).append(version)

    mixed = {
        number: sorted(set(markers))
        for number, markers in by_number.items()
        if len(set(markers)) > 1
    }

    print("\n=== schema_migrations version-marker audit ===\n")
    print(f"Total markers: {len(versions)}")
    print(f"Numeric IDs seen: {len(by_number)}")

    if mixed:
        print("\nMixed markers detected (same migration ID, different version strings):")
        for number in sorted(mixed):
            print(f"  - {number}: {', '.join(mixed[number])}")
    else:
        print("\nNo mixed markers detected.")

    if unparseable:
        print("\nUnparseable markers (cannot map to numeric migration ID):")
        for marker in sorted(unparseable):
            print(f"  - {marker}")

    print()
    return 1 if (mixed or unparseable) else 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PostgreSQL migration runner for Cat-Scan"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending migrations without applying them",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current migration status",
    )
    parser.add_argument(
        "--audit-versions",
        action="store_true",
        help="Audit schema_migrations for mixed numeric/canonical version markers",
    )

    args = parser.parse_args()

    try:
        if args.status:
            show_status()
            return 0

        if args.audit_versions:
            return audit_version_markers()

        applied, failed = run_migrations(dry_run=args.dry_run)

        if failed > 0:
            logger.error(f"Migration completed with errors: {applied} applied, {failed} failed")
            return 1

        if applied > 0:
            logger.info(f"Migration completed successfully: {applied} migration(s) applied")

        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
