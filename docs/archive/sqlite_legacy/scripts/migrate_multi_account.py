#!/usr/bin/env python3
"""Migration script for multi-account upload tracking.

This script:
1. Adds bidder_id column to import_history, daily_upload_summary, and rtb_daily
2. Creates account_daily_upload_summary table
3. Backfills bidder_id for existing data based on billing_id → bidder_id mappings

Usage:
    python scripts/migrate_multi_account.py [--dry-run]
"""

import sqlite3
import os
import sys
import argparse
import json
from pathlib import Path

# Database path
DB_PATH = Path.home() / ".catscan" / "catscan.db"


def run_migration(db_path: Path, dry_run: bool = False):
    """Run the multi-account migration."""
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("Multi-Account Upload Tracking Migration")
    print("=" * 60)
    print(f"Database: {db_path}")
    print(f"Dry run: {dry_run}")
    print()

    try:
        # Step 1: Add columns to existing tables
        print("Step 1: Adding columns to existing tables...")

        columns_to_add = [
            ("import_history", "bidder_id", "TEXT"),
            ("import_history", "billing_ids_found", "TEXT"),
            ("daily_upload_summary", "bidder_id", "TEXT"),
            ("rtb_daily", "bidder_id", "TEXT"),
        ]

        for table, column, col_type in columns_to_add:
            try:
                cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
                print(f"  ✓ {table}.{column} already exists")
            except sqlite3.OperationalError:
                if not dry_run:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    print(f"  + Added {table}.{column}")
                else:
                    print(f"  [DRY RUN] Would add {table}.{column}")

        # Step 2: Create indices
        print("\nStep 2: Creating indices...")

        indices = [
            ("idx_import_history_bidder", "import_history", "bidder_id"),
            ("idx_rtb_bidder", "rtb_daily", "bidder_id"),
            ("idx_rtb_date_bidder", "rtb_daily", "metric_date, bidder_id"),
        ]

        for idx_name, table, columns in indices:
            try:
                if not dry_run:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})")
                    print(f"  + Created index {idx_name}")
                else:
                    print(f"  [DRY RUN] Would create index {idx_name}")
            except sqlite3.OperationalError as e:
                print(f"  ! Index {idx_name}: {e}")

        # Step 3: Create account_daily_upload_summary table
        print("\nStep 3: Creating account_daily_upload_summary table...")

        if not dry_run:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_daily_upload_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_date DATE NOT NULL,
                    bidder_id TEXT NOT NULL,
                    total_uploads INTEGER DEFAULT 0,
                    successful_uploads INTEGER DEFAULT 0,
                    failed_uploads INTEGER DEFAULT 0,
                    total_rows_written INTEGER DEFAULT 0,
                    total_file_size_bytes INTEGER DEFAULT 0,
                    avg_rows_per_upload REAL DEFAULT 0,
                    min_rows INTEGER,
                    max_rows INTEGER,
                    has_anomaly INTEGER DEFAULT 0,
                    anomaly_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(upload_date, bidder_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_account_daily_upload_date ON account_daily_upload_summary(upload_date DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_account_daily_upload_bidder ON account_daily_upload_summary(bidder_id)")
            print("  + Created account_daily_upload_summary table")
        else:
            print("  [DRY RUN] Would create account_daily_upload_summary table")

        # Step 4: Build billing_id → bidder_id mapping from pretargeting_configs
        print("\nStep 4: Building billing_id → bidder_id mapping...")

        cursor.execute("""
            SELECT billing_id, bidder_id FROM pretargeting_configs
            WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
        """)
        mappings = {row["billing_id"]: row["bidder_id"] for row in cursor.fetchall()}
        print(f"  Found {len(mappings)} billing_id → bidder_id mappings")

        if not mappings:
            print("  ! No mappings found. Skipping backfill.")
            print("    (Run pretargeting sync first to populate mappings)")
        else:
            # Step 5: Backfill bidder_id in rtb_daily
            print("\nStep 5: Backfilling bidder_id in rtb_daily...")

            # Count rows needing update
            cursor.execute("""
                SELECT COUNT(*) FROM rtb_daily
                WHERE bidder_id IS NULL AND billing_id IS NOT NULL
            """)
            count = cursor.fetchone()[0]
            print(f"  Found {count:,} rows to update")

            if count > 0:
                # Get unique billing_ids that need updating
                cursor.execute("""
                    SELECT DISTINCT billing_id FROM rtb_daily
                    WHERE bidder_id IS NULL AND billing_id IS NOT NULL
                """)
                billing_ids_to_update = [row["billing_id"] for row in cursor.fetchall()]

                updated = 0
                for billing_id in billing_ids_to_update:
                    bidder_id = mappings.get(billing_id)
                    if bidder_id:
                        if not dry_run:
                            cursor.execute("""
                                UPDATE rtb_daily SET bidder_id = ?
                                WHERE billing_id = ? AND bidder_id IS NULL
                            """, (bidder_id, billing_id))
                            updated += cursor.rowcount
                        else:
                            # Count how many would be updated
                            cursor.execute("""
                                SELECT COUNT(*) FROM rtb_daily
                                WHERE billing_id = ? AND bidder_id IS NULL
                            """, (billing_id,))
                            updated += cursor.fetchone()[0]

                if dry_run:
                    print(f"  [DRY RUN] Would update {updated:,} rows")
                else:
                    print(f"  + Updated {updated:,} rows")

            # Step 6: Backfill bidder_id in import_history
            print("\nStep 6: Backfilling bidder_id in import_history...")

            cursor.execute("""
                SELECT id, batch_id FROM import_history
                WHERE bidder_id IS NULL
            """)
            imports_to_update = cursor.fetchall()
            print(f"  Found {len(imports_to_update)} imports to update")

            updated_imports = 0
            for import_row in imports_to_update:
                import_id = import_row["id"]
                batch_id = import_row["batch_id"]

                # Find billing_ids from rtb_daily for this batch
                cursor.execute("""
                    SELECT DISTINCT billing_id FROM rtb_daily
                    WHERE import_batch_id = ? AND billing_id IS NOT NULL
                """, (batch_id,))
                billing_ids = [row["billing_id"] for row in cursor.fetchall()]

                if billing_ids:
                    # Find common bidder_id
                    bidder_ids = set()
                    for billing_id in billing_ids:
                        bid = mappings.get(billing_id)
                        if bid:
                            bidder_ids.add(bid)

                    if len(bidder_ids) == 1:
                        bidder_id = bidder_ids.pop()
                        billing_ids_json = json.dumps(billing_ids)

                        if not dry_run:
                            cursor.execute("""
                                UPDATE import_history
                                SET bidder_id = ?, billing_ids_found = ?
                                WHERE id = ?
                            """, (bidder_id, billing_ids_json, import_id))
                        updated_imports += 1

            if dry_run:
                print(f"  [DRY RUN] Would update {updated_imports} imports")
            else:
                print(f"  + Updated {updated_imports} imports")

        # Commit changes
        if not dry_run:
            conn.commit()
            print("\n✅ Migration completed successfully!")
        else:
            print("\n[DRY RUN] No changes made. Run without --dry-run to apply.")

        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Multi-account upload tracking migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--db", type=str, help="Database path (default: ~/.catscan/catscan.db)")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DB_PATH

    success = run_migration(db_path, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
