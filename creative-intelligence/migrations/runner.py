"""Migration runner for RTBcat database.

Handles applying SQL migrations in order, tracking which have been applied,
and providing status/create commands.

The migration tracking table stores:
- Migration name (filename without .sql)
- Applied timestamp
- Checksum (to detect if migration was modified after applying)
"""

import argparse
import hashlib
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Default database paths
CREATIVES_DB = Path.home() / ".catscan" / "catscan.db"
MIGRATIONS_DIR = Path(__file__).parent


def get_migration_files() -> list[tuple[int, str, Path]]:
    """Get all migration files sorted by number.

    Returns:
        List of (number, name, path) tuples sorted by number.
    """
    migrations = []
    pattern = re.compile(r"^(\d{3})_(.+)\.sql$")

    for file in MIGRATIONS_DIR.glob("*.sql"):
        match = pattern.match(file.name)
        if match:
            number = int(match.group(1))
            name = match.group(2)
            migrations.append((number, name, file))

    return sorted(migrations, key=lambda x: x[0])


def compute_checksum(content: str) -> str:
    """Compute MD5 checksum of migration content."""
    return hashlib.md5(content.encode()).hexdigest()


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    """Create the schema_migrations table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def get_applied_migrations(conn: sqlite3.Connection) -> dict[int, dict]:
    """Get all applied migrations.

    Returns:
        Dict mapping version number to {name, checksum, applied_at}.
    """
    ensure_migrations_table(conn)
    cursor = conn.execute(
        "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
    )
    return {
        row[0]: {"name": row[1], "checksum": row[2], "applied_at": row[3]}
        for row in cursor.fetchall()
    }


def apply_migration(
    conn: sqlite3.Connection,
    version: int,
    name: str,
    path: Path,
    dry_run: bool = False,
) -> bool:
    """Apply a single migration.

    Args:
        conn: Database connection.
        version: Migration version number.
        name: Migration name.
        path: Path to SQL file.
        dry_run: If True, don't actually apply.

    Returns:
        True if successful.
    """
    content = path.read_text()
    checksum = compute_checksum(content)

    if dry_run:
        print(f"  [DRY RUN] Would apply: {version:03d}_{name}")
        return True

    try:
        # Execute the migration SQL
        conn.executescript(content)

        # Record in schema_migrations
        conn.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum)
            VALUES (?, ?, ?)
            """,
            (version, name, checksum),
        )
        conn.commit()
        print(f"  Applied: {version:03d}_{name}")
        return True

    except sqlite3.Error as e:
        conn.rollback()
        print(f"  FAILED: {version:03d}_{name} - {e}")
        return False


def run_migrations(
    db_path: Path = CREATIVES_DB,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Run all pending migrations.

    Args:
        db_path: Path to database.
        dry_run: If True, don't actually apply.

    Returns:
        Tuple of (applied_count, failed_count).
    """
    # Ensure database directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        applied = get_applied_migrations(conn)
        migrations = get_migration_files()

        if not migrations:
            print("No migration files found.")
            return 0, 0

        pending = [
            (v, n, p) for v, n, p in migrations
            if v not in applied
        ]

        if not pending:
            print("All migrations already applied.")
            return 0, 0

        print(f"Found {len(pending)} pending migration(s):")

        applied_count = 0
        failed_count = 0

        for version, name, path in pending:
            if apply_migration(conn, version, name, path, dry_run):
                applied_count += 1
            else:
                failed_count += 1
                # Stop on first failure
                break

        return applied_count, failed_count

    finally:
        conn.close()


def show_status(db_path: Path = CREATIVES_DB) -> None:
    """Show migration status."""
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run migrations to create it.")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        applied = get_applied_migrations(conn)
        migrations = get_migration_files()

        print(f"Database: {db_path}")
        print(f"Migrations directory: {MIGRATIONS_DIR}")
        print()

        if not migrations:
            print("No migration files found.")
            return

        print("Migration Status:")
        print("-" * 60)

        for version, name, path in migrations:
            content = path.read_text()
            current_checksum = compute_checksum(content)

            if version in applied:
                info = applied[version]
                status = "APPLIED"
                if info["checksum"] != current_checksum:
                    status = "MODIFIED!"
                print(f"  [{status}] {version:03d}_{name} ({info['applied_at'][:19]})")
            else:
                print(f"  [PENDING] {version:03d}_{name}")

        print("-" * 60)
        print(f"Applied: {len(applied)}, Pending: {len(migrations) - len(applied)}")

    finally:
        conn.close()


def create_migration(name: str) -> Path:
    """Create a new migration file.

    Args:
        name: Name for the migration (will be slugified).

    Returns:
        Path to created file.
    """
    # Slugify the name
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

    # Get next version number
    migrations = get_migration_files()
    next_version = max([v for v, _, _ in migrations], default=0) + 1

    filename = f"{next_version:03d}_{slug}.sql"
    filepath = MIGRATIONS_DIR / filename

    # Create template
    template = f"""-- Migration: {name}
-- Created: {datetime.now().isoformat()[:19]}

-- Write your SQL here
-- Each statement should end with a semicolon

-- Example:
-- CREATE TABLE IF NOT EXISTS new_table (
--     id INTEGER PRIMARY KEY,
--     name TEXT NOT NULL
-- );

"""

    filepath.write_text(template)
    print(f"Created: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Database migration runner")
    parser.add_argument(
        "--db",
        type=Path,
        default=CREATIVES_DB,
        help=f"Database path (default: {CREATIVES_DB})",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be applied without applying",
    )
    parser.add_argument(
        "--create",
        metavar="NAME",
        help="Create a new migration with the given name",
    )

    args = parser.parse_args()

    if args.create:
        create_migration(args.create)
    elif args.status:
        show_status(args.db)
    else:
        applied, failed = run_migrations(args.db, args.dry_run)
        if failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
