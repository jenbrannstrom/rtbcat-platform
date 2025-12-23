#!/usr/bin/env python3
"""
Schema Migration v12: Rename tables for clarity

This migration:
1. Renames performance_data → rtb_daily
2. Renames ai_campaigns → campaigns (after dropping old campaigns)
3. Drops unused legacy tables
4. Updates all indexes

Run with: python scripts/migrate_schema_v12.py

IMPORTANT: Back up database first!
    cp ~/.catscan/catscan.db ~/.catscan/catscan.db.backup
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime


def backup_database(db_path: Path) -> Path:
    """Create timestamped backup before migration."""
    backup_path = db_path.with_suffix(f'.db.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    shutil.copy(db_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def migrate(db_path: str = "~/.catscan/catscan.db"):
    """Run the full migration."""

    db_path = Path(db_path).expanduser()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    # Backup first
    backup_database(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("SCHEMA MIGRATION v12")
    print("=" * 60)

    # Check current state
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables_before = [row[0] for row in cursor.fetchall()]
    print(f"\nTables before: {len(tables_before)}")
    for t in tables_before:
        print(f"  - {t}")

    try:
        # =========================================================
        # STEP 1: Rename performance_data → rtb_daily
        # =========================================================
        print("\n[1/5] Renaming performance_data -> rtb_daily...")

        if 'performance_data' in tables_before:
            cursor.execute("ALTER TABLE performance_data RENAME TO rtb_daily")
            print("  Table renamed")

            # Recreate indexes with new names
            cursor.execute("DROP INDEX IF EXISTS idx_perf_date")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_creative")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_billing")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_size")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_country")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_app")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_batch")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_date_billing")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_date_size")
            cursor.execute("DROP INDEX IF EXISTS idx_perf_date_creative")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_date ON rtb_daily(metric_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_creative ON rtb_daily(creative_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_billing ON rtb_daily(billing_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_size ON rtb_daily(creative_size)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_country ON rtb_daily(country)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_app ON rtb_daily(app_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_batch ON rtb_daily(import_batch_id)")
            # Composite indexes for common query patterns
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_date_billing ON rtb_daily(metric_date, billing_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_date_size ON rtb_daily(metric_date, creative_size)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_date_creative ON rtb_daily(metric_date, creative_id)")
            print("  Indexes recreated")
        elif 'rtb_daily' in tables_before:
            print("  - performance_data not found (already migrated)")
        else:
            print("  - performance_data not found")

        # =========================================================
        # STEP 2: Drop unused performance_metrics and video_metrics
        # =========================================================
        print("\n[2/5] Dropping legacy performance_metrics...")

        if 'video_metrics' in tables_before:
            cursor.execute("DROP TABLE video_metrics")
            print("  Dropped video_metrics")

        if 'performance_metrics' in tables_before:
            # Check if it has any data we care about
            cursor.execute("SELECT COUNT(*) FROM performance_metrics")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"  WARNING: performance_metrics has {count} rows - archiving to performance_metrics_archive")
                cursor.execute("ALTER TABLE performance_metrics RENAME TO performance_metrics_archive")
            else:
                cursor.execute("DROP TABLE performance_metrics")
                print("  Dropped performance_metrics (was empty)")
        else:
            print("  - performance_metrics not found")

        # =========================================================
        # STEP 3: Handle campaigns table rename
        # =========================================================
        print("\n[3/5] Consolidating campaign tables...")

        # Refresh tables list after potential changes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        current_tables = [row[0] for row in cursor.fetchall()]

        has_campaigns = 'campaigns' in current_tables
        has_ai_campaigns = 'ai_campaigns' in current_tables

        if has_campaigns and has_ai_campaigns:
            # Check if old campaigns has data
            cursor.execute("SELECT COUNT(*) FROM campaigns")
            old_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM ai_campaigns")
            new_count = cursor.fetchone()[0]

            print(f"  Old campaigns: {old_count} rows, ai_campaigns: {new_count} rows")

            if old_count > 0 and new_count == 0:
                # Keep old campaigns, drop ai_campaigns
                cursor.execute("DROP TABLE ai_campaigns")
                print("  Keeping campaigns, dropped empty ai_campaigns")
            elif new_count > 0:
                # Keep ai_campaigns, rename to campaigns
                cursor.execute("ALTER TABLE campaigns RENAME TO campaigns_legacy")
                cursor.execute("ALTER TABLE ai_campaigns RENAME TO campaigns")
                print("  Renamed ai_campaigns -> campaigns, old campaigns -> campaigns_legacy")
            else:
                # Both empty, keep structure from ai_campaigns
                cursor.execute("DROP TABLE campaigns")
                cursor.execute("ALTER TABLE ai_campaigns RENAME TO campaigns")
                print("  Renamed ai_campaigns -> campaigns")
        elif has_ai_campaigns:
            cursor.execute("ALTER TABLE ai_campaigns RENAME TO campaigns")
            print("  Renamed ai_campaigns -> campaigns")
        else:
            print("  - No campaign table changes needed")

        # =========================================================
        # STEP 4: Consolidate junction tables
        # =========================================================
        print("\n[4/5] Consolidating creative-campaign junction tables...")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        current_tables = [row[0] for row in cursor.fetchall()]

        has_campaign_creatives = 'campaign_creatives' in current_tables
        has_creative_campaigns = 'creative_campaigns' in current_tables

        if has_campaign_creatives and has_creative_campaigns:
            cursor.execute("SELECT COUNT(*) FROM campaign_creatives")
            cc_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM creative_campaigns")
            crc_count = cursor.fetchone()[0]

            print(f"  campaign_creatives: {cc_count}, creative_campaigns: {crc_count}")

            # Keep creative_campaigns (newer), drop campaign_creatives
            if cc_count > 0 and crc_count == 0:
                cursor.execute("DROP TABLE creative_campaigns")
                cursor.execute("ALTER TABLE campaign_creatives RENAME TO creative_campaigns")
                print("  Renamed campaign_creatives -> creative_campaigns")
            else:
                cursor.execute("DROP TABLE IF EXISTS campaign_creatives")
                print("  Dropped campaign_creatives, keeping creative_campaigns")
        elif has_campaign_creatives and not has_creative_campaigns:
            cursor.execute("ALTER TABLE campaign_creatives RENAME TO creative_campaigns")
            print("  Renamed campaign_creatives -> creative_campaigns")
        else:
            print("  - No junction table changes needed")

        # =========================================================
        # STEP 5: Drop redundant tables
        # =========================================================
        print("\n[5/5] Cleaning up redundant tables...")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        current_tables = [row[0] for row in cursor.fetchall()]

        # rtb_traffic is redundant with rtb_daily.creative_size
        if 'rtb_traffic' in current_tables:
            cursor.execute("SELECT COUNT(*) FROM rtb_traffic")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"  WARNING: rtb_traffic has {count} rows - keeping as rtb_traffic_archive")
                cursor.execute("ALTER TABLE rtb_traffic RENAME TO rtb_traffic_archive")
            else:
                cursor.execute("DROP TABLE rtb_traffic")
                print("  Dropped rtb_traffic (was empty)")

        # daily_creative_summary - check if being used
        if 'daily_creative_summary' in current_tables:
            cursor.execute("SELECT COUNT(*) FROM daily_creative_summary")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("DROP TABLE daily_creative_summary")
                print("  Dropped daily_creative_summary (was empty)")
            else:
                print(f"  - Keeping daily_creative_summary ({count} rows)")

        # campaign_daily_summary - check if being used
        if 'campaign_daily_summary' in current_tables:
            cursor.execute("SELECT COUNT(*) FROM campaign_daily_summary")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("DROP TABLE campaign_daily_summary")
                print("  Dropped campaign_daily_summary (was empty)")
            else:
                print(f"  - Keeping campaign_daily_summary ({count} rows)")

        # size_metrics_daily - legacy table
        if 'size_metrics_daily' in current_tables:
            cursor.execute("SELECT COUNT(*) FROM size_metrics_daily")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("DROP TABLE size_metrics_daily")
                print("  Dropped size_metrics_daily (was empty)")
            else:
                print(f"  - Keeping size_metrics_daily ({count} rows)")

        # Commit all changes
        conn.commit()

        # Final state
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables_after = [row[0] for row in cursor.fetchall()]

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"\nTables before: {len(tables_before)}")
        print(f"Tables after:  {len(tables_after)}")

        removed = set(tables_before) - set(tables_after)
        added = set(tables_after) - set(tables_before)

        if removed:
            print(f"\nRemoved/Renamed: {removed}")
        if added:
            print(f"Added: {added}")

        print("\nFinal tables:")
        for t in tables_after:
            print(f"  - {t}")

        print("\nMigration successful!")
        print(f"  Backup at: ~/.catscan/catscan.db.backup_*")

        return True

    except Exception as e:
        conn.rollback()
        print(f"\nMigration failed: {e}")
        print("  Database unchanged. Check backup.")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("RTBcat Schema Migration v12")
    print("=" * 60)
    print()
    print("This migration will:")
    print("  1. Rename performance_data -> rtb_daily")
    print("  2. Rename ai_campaigns -> campaigns")
    print("  3. Drop/archive unused legacy tables")
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        migrate()
    else:
        confirm = input("Continue? (yes/no): ")
        if confirm.lower() == "yes":
            migrate()
        else:
            print("Cancelled.")
