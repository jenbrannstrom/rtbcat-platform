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

    # Preview normalization plan for mixed markers
    python scripts/postgres_migrate.py --normalize-versions

    # Apply normalization (dedupe numeric/canonical duplicates)
    python scripts/postgres_migrate.py --normalize-versions-apply
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

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
    """Create schema_migrations table if it doesn't exist.

    Also adds the ``description`` column for existing tables that were
    created before migrations 027/039/040 started referencing it.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            description TEXT
        )
    """)
    # Existing tables may lack the column — add idempotently.
    conn.execute("""
        ALTER TABLE schema_migrations
        ADD COLUMN IF NOT EXISTS description TEXT
    """)
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


def get_canonical_versions_by_number() -> dict[int, str]:
    """Map migration number -> canonical version marker from SQL filenames."""
    mapping: dict[int, str] = {}
    for version, _ in get_pending_migrations():
        number = extract_migration_number(version)
        if number is not None and number not in mapping:
            mapping[number] = version
    return mapping


def normalize_version_markers(apply_changes: bool = False) -> int:
    """Normalize mixed schema_migrations markers to canonical filename-based versions.

    This repairs historical cases like:
      - 27 + 027_schema_alignment
      - 39 + 039_ingestion_runs_extend

    Args:
        apply_changes: False = dry run (preview), True = apply updates/deletes.

    Returns:
        0 when table is clean after operation, 1 when anomalies remain/pending.
    """
    conn = get_connection()
    try:
        ensure_migrations_table(conn)
        canonical_by_number = get_canonical_versions_by_number()

        cursor = conn.execute(
            "SELECT version, applied_at, description FROM schema_migrations ORDER BY applied_at, version"
        )
        rows = [
            {"version": str(row[0]), "applied_at": row[1], "description": row[2]}
            for row in cursor.fetchall()
        ]

        if not rows:
            print("No schema_migrations rows found.")
            return 0

        grouped: dict[int, list[dict[str, Any]]] = {}
        unparseable: list[str] = []
        for row in rows:
            number = extract_migration_number(row["version"])
            if number is None:
                unparseable.append(row["version"])
                continue
            grouped.setdefault(number, []).append(row)

        plans: list[dict[str, Any]] = []
        unresolved: list[tuple[int, list[str]]] = []

        for number in sorted(grouped):
            entries = grouped[number]
            markers = sorted({str(e["version"]) for e in entries})
            canonical = canonical_by_number.get(number)

            if not canonical:
                if len(markers) > 1:
                    unresolved.append((number, markers))
                continue

            # Already clean for this migration number.
            if markers == [canonical]:
                continue

            sorted_entries = sorted(
                entries,
                key=lambda e: (e["applied_at"] is None, e["applied_at"], e["version"]),
            )
            oldest = sorted_entries[0]
            canonical_entry = next((e for e in entries if e["version"] == canonical), None)

            rename_from: Optional[str] = None
            remove_versions = [m for m in markers if m != canonical]
            update_applied_at = False
            description_to_set: Optional[str] = None

            if canonical_entry is None:
                # No canonical marker yet: rename oldest marker to canonical.
                rename_from = str(oldest["version"])
                remove_versions = [
                    m for m in remove_versions if m != rename_from
                ]
            else:
                # Canonical exists: preserve earliest observed applied_at.
                if oldest["applied_at"] and canonical_entry["applied_at"] and oldest["applied_at"] < canonical_entry["applied_at"]:
                    update_applied_at = True

            # Preserve a non-empty description if canonical row lacks one.
            canonical_desc = canonical_entry["description"] if canonical_entry else oldest["description"]
            best_desc = next((e["description"] for e in sorted_entries if e["description"]), None)
            if (not canonical_desc) and best_desc:
                description_to_set = str(best_desc)

            plans.append(
                {
                    "number": number,
                    "canonical": canonical,
                    "markers": markers,
                    "rename_from": rename_from,
                    "remove_versions": remove_versions,
                    "update_applied_at": update_applied_at,
                    "applied_at_value": oldest["applied_at"],
                    "description_to_set": description_to_set,
                }
            )

        mode = "APPLY" if apply_changes else "DRY-RUN"
        print(f"\n=== schema_migrations normalization ({mode}) ===\n")
        print(f"Canonical migration IDs known from files: {len(canonical_by_number)}")
        print(f"Normalization plans: {len(plans)}")

        if plans:
            for p in plans:
                print(f"- {p['number']}: {', '.join(p['markers'])} -> {p['canonical']}")
                if p["rename_from"]:
                    print(f"    rename: {p['rename_from']} -> {p['canonical']}")
                if p["remove_versions"]:
                    print(f"    delete: {', '.join(p['remove_versions'])}")
                if p["update_applied_at"]:
                    print("    update: canonical applied_at to earliest marker timestamp")
                if p["description_to_set"]:
                    print("    update: fill missing canonical description")
        else:
            print("No canonicalization actions needed.")

        if unresolved:
            print("\nUnresolved mixed markers (no matching SQL file number):")
            for number, markers in unresolved:
                print(f"  - {number}: {', '.join(markers)}")

        if unparseable:
            print("\nUnparseable markers:")
            for marker in sorted(set(unparseable)):
                print(f"  - {marker}")

        if not apply_changes:
            print("\nDry run only. Re-run with --normalize-versions-apply to execute changes.\n")
            return 1 if (plans or unresolved or unparseable) else 0

        # Apply canonicalization.
        renamed = 0
        deleted = 0
        updated_applied_at = 0
        updated_description = 0

        try:
            for p in plans:
                canonical = p["canonical"]

                if p["rename_from"]:
                    conn.execute(
                        "UPDATE schema_migrations SET version = %s WHERE version = %s",
                        (canonical, p["rename_from"]),
                    )
                    renamed += 1

                if p["update_applied_at"]:
                    conn.execute(
                        "UPDATE schema_migrations SET applied_at = %s WHERE version = %s",
                        (p["applied_at_value"], canonical),
                    )
                    updated_applied_at += 1

                if p["description_to_set"]:
                    conn.execute(
                        """
                        UPDATE schema_migrations
                        SET description = %s
                        WHERE version = %s AND (description IS NULL OR description = '')
                        """,
                        (p["description_to_set"], canonical),
                    )
                    updated_description += 1

                for version in p["remove_versions"]:
                    res = conn.execute(
                        "DELETE FROM schema_migrations WHERE version = %s",
                        (version,),
                    )
                    deleted += res.rowcount

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        print("\nApplied changes:")
        print(f"  - Renamed markers: {renamed}")
        print(f"  - Deleted duplicate markers: {deleted}")
        print(f"  - applied_at updates: {updated_applied_at}")
        print(f"  - description updates: {updated_description}")
        print()

        return 1 if (unresolved or unparseable) else 0

    finally:
        conn.close()


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

    Uses a PostgreSQL advisory lock to prevent multiple workers from
    applying migrations concurrently (avoids deadlocks when
    UVICORN_WORKERS > 1).

    Args:
        dry_run: If True, only show what would be applied.

    Returns:
        Tuple of (applied_count, failed_count).
    """
    # Advisory lock ID — arbitrary fixed constant for migration exclusivity.
    MIGRATION_LOCK_ID = 7483640  # ascii sum of "catscan_migrate"

    conn = get_connection()

    try:
        # Acquire advisory lock (blocks until available; released on conn close).
        # pg_advisory_lock is session-level: held until connection closes.
        conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
        logger.info("Acquired migration advisory lock.")

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
        conn.close()  # Also releases the advisory lock


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

    if mixed:
        print("\nNext step:")
        print("  python scripts/postgres_migrate.py --normalize-versions")

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
    parser.add_argument(
        "--normalize-versions",
        action="store_true",
        help="Preview schema_migrations marker normalization plan (no writes)",
    )
    parser.add_argument(
        "--normalize-versions-apply",
        action="store_true",
        help="Apply schema_migrations marker normalization (writes to DB)",
    )

    args = parser.parse_args()

    try:
        if args.status:
            show_status()
            return 0

        if args.audit_versions:
            return audit_version_markers()

        if args.normalize_versions_apply:
            return normalize_version_markers(apply_changes=True)

        if args.normalize_versions:
            return normalize_version_markers(apply_changes=False)

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
