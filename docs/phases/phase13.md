# Phase 12: Schema Cleanup - Single Source of Truth

**Objective:** Eliminate table naming confusion by renaming to clear, distinct names and removing unused tables.

---

## The Problem

Current schema has confusing overlap:

```
performance_data      ← THE actual table (CSV imports)
performance_metrics   ← Legacy/unused, causes confusion
```

Every time someone reads the code: "Wait, which one do I use?"

readme.md needs to be updated also!
---

## The Solution

### New Table Name: `rtb_daily`

**Why this name:**
- `rtb` = Real-Time Bidding (the domain)
- `daily` = the granularity (daily aggregates per dimension)
- **Sounds NOTHING like the old names**
- Short, easy to type: `SELECT * FROM rtb_daily WHERE ...`
- Unambiguous: clearly THE fact table

### Tables to Remove

| Table | Status | Action |
|-------|--------|--------|
| `performance_metrics` | Unused legacy | DROP |
| `video_metrics` | Orphaned (referenced performance_metrics) | DROP |
| `campaigns` | Superseded by ai_campaigns | DROP after migrating data |
| `campaign_creatives` | Superseded by creative_campaigns | DROP after verifying |
| `rtb_traffic` | Redundant with rtb_daily.creative_size | DROP |

### Tables to Keep (renamed)

| Old Name | New Name | Reason |
|----------|----------|--------|
| `performance_data` | `rtb_daily` | Clear, distinct, THE fact table |
| `ai_campaigns` | `campaigns` | Remove "ai_" prefix, it's just campaigns now |

---

## Part 1: Migration Script

**File:** `creative-intelligence/scripts/migrate_schema_v12.py`

```python
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
    print(f"✓ Backup created: {backup_path}")
    return backup_path


def migrate(db_path: str = "~/.catscan/catscan.db"):
    """Run the full migration."""
    
    db_path = Path(db_path).expanduser()
    
    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
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
    
    try:
        # =========================================================
        # STEP 1: Rename performance_data → rtb_daily
        # =========================================================
        print("\n[1/5] Renaming performance_data → rtb_daily...")
        
        if 'performance_data' in tables_before:
            cursor.execute("ALTER TABLE performance_data RENAME TO rtb_daily")
            print("  ✓ Table renamed")
            
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
            
            cursor.execute("CREATE INDEX idx_rtb_date ON rtb_daily(metric_date)")
            cursor.execute("CREATE INDEX idx_rtb_creative ON rtb_daily(creative_id)")
            cursor.execute("CREATE INDEX idx_rtb_billing ON rtb_daily(billing_id)")
            cursor.execute("CREATE INDEX idx_rtb_size ON rtb_daily(creative_size)")
            cursor.execute("CREATE INDEX idx_rtb_country ON rtb_daily(country)")
            cursor.execute("CREATE INDEX idx_rtb_app ON rtb_daily(app_id)")
            cursor.execute("CREATE INDEX idx_rtb_batch ON rtb_daily(import_batch_id)")
            # Composite indexes for common query patterns
            cursor.execute("CREATE INDEX idx_rtb_date_billing ON rtb_daily(metric_date, billing_id)")
            cursor.execute("CREATE INDEX idx_rtb_date_size ON rtb_daily(metric_date, creative_size)")
            cursor.execute("CREATE INDEX idx_rtb_date_creative ON rtb_daily(metric_date, creative_id)")
            print("  ✓ Indexes recreated")
        else:
            print("  - performance_data not found (already migrated?)")
        
        # =========================================================
        # STEP 2: Drop unused performance_metrics and video_metrics
        # =========================================================
        print("\n[2/5] Dropping legacy performance_metrics...")
        
        if 'video_metrics' in tables_before:
            cursor.execute("DROP TABLE video_metrics")
            print("  ✓ Dropped video_metrics")
        
        if 'performance_metrics' in tables_before:
            # Check if it has any data we care about
            cursor.execute("SELECT COUNT(*) FROM performance_metrics")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"  ⚠ performance_metrics has {count} rows - archiving to performance_metrics_archive")
                cursor.execute("ALTER TABLE performance_metrics RENAME TO performance_metrics_archive")
            else:
                cursor.execute("DROP TABLE performance_metrics")
                print("  ✓ Dropped performance_metrics (was empty)")
        else:
            print("  - performance_metrics not found")
        
        # =========================================================
        # STEP 3: Handle campaigns table rename
        # =========================================================
        print("\n[3/5] Consolidating campaign tables...")
        
        # Check if both exist
        has_campaigns = 'campaigns' in tables_before
        has_ai_campaigns = 'ai_campaigns' in tables_before
        
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
                print("  ✓ Keeping campaigns, dropped empty ai_campaigns")
            elif new_count > 0:
                # Keep ai_campaigns, rename to campaigns
                cursor.execute("ALTER TABLE campaigns RENAME TO campaigns_legacy")
                cursor.execute("ALTER TABLE ai_campaigns RENAME TO campaigns")
                print("  ✓ Renamed ai_campaigns → campaigns, old campaigns → campaigns_legacy")
            else:
                # Both empty, keep structure from ai_campaigns
                cursor.execute("DROP TABLE campaigns")
                cursor.execute("ALTER TABLE ai_campaigns RENAME TO campaigns")
                print("  ✓ Renamed ai_campaigns → campaigns")
        elif has_ai_campaigns:
            cursor.execute("ALTER TABLE ai_campaigns RENAME TO campaigns")
            print("  ✓ Renamed ai_campaigns → campaigns")
        else:
            print("  - No campaign table changes needed")
        
        # =========================================================
        # STEP 4: Consolidate junction tables
        # =========================================================
        print("\n[4/5] Consolidating creative-campaign junction tables...")
        
        has_campaign_creatives = 'campaign_creatives' in tables_before
        has_creative_campaigns = 'creative_campaigns' in tables_before
        
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
                print("  ✓ Renamed campaign_creatives → creative_campaigns")
            else:
                cursor.execute("DROP TABLE IF EXISTS campaign_creatives")
                print("  ✓ Dropped campaign_creatives, keeping creative_campaigns")
        
        # =========================================================
        # STEP 5: Drop redundant tables
        # =========================================================
        print("\n[5/5] Cleaning up redundant tables...")
        
        # rtb_traffic is redundant with rtb_daily.creative_size
        if 'rtb_traffic' in tables_before:
            cursor.execute("SELECT COUNT(*) FROM rtb_traffic")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"  ⚠ rtb_traffic has {count} rows - keeping as rtb_traffic_archive")
                cursor.execute("ALTER TABLE rtb_traffic RENAME TO rtb_traffic_archive")
            else:
                cursor.execute("DROP TABLE rtb_traffic")
                print("  ✓ Dropped rtb_traffic (was empty)")
        
        # daily_creative_summary - check if being used
        if 'daily_creative_summary' in tables_before:
            cursor.execute("SELECT COUNT(*) FROM daily_creative_summary")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("DROP TABLE daily_creative_summary")
                print("  ✓ Dropped daily_creative_summary (was empty)")
            else:
                print(f"  - Keeping daily_creative_summary ({count} rows)")
        
        # campaign_daily_summary - check if being used
        if 'campaign_daily_summary' in tables_before:
            cursor.execute("SELECT COUNT(*) FROM campaign_daily_summary")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("DROP TABLE campaign_daily_summary")
                print("  ✓ Dropped campaign_daily_summary (was empty)")
            else:
                print(f"  - Keeping campaign_daily_summary ({count} rows)")
        
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
        print(f"\nRemoved: {set(tables_before) - set(tables_after)}")
        print(f"Added:   {set(tables_after) - set(tables_before)}")
        
        print("\n✓ Migration successful!")
        print(f"  Backup at: ~/.catscan/catscan.db.backup_*")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        print("  Database unchanged. Check backup.")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
```

---

## Part 2: Update All Code References

After running the migration, update all code that references the old table names.

### 2.1 Find and Replace Map

| Old Reference | New Reference |
|--------------|---------------|
| `performance_data` | `rtb_daily` |
| `FROM performance_data` | `FROM rtb_daily` |
| `INTO performance_data` | `INTO rtb_daily` |
| `performance_data.` | `rtb_daily.` |
| `idx_perf_` | `idx_rtb_` |
| `ai_campaigns` | `campaigns` |
| `campaign_creatives` | `creative_campaigns` |

### 2.2 Files to Update

```bash
# Find all files referencing old table names
grep -r "performance_data" --include="*.py" creative-intelligence/
grep -r "performance_data" --include="*.ts" --include="*.tsx" dashboard/
grep -r "ai_campaigns" --include="*.py" creative-intelligence/
grep -r "ai_campaigns" --include="*.ts" --include="*.tsx" dashboard/
```

Key files likely needing updates:
- `storage/sqlite_store.py` - Database methods
- `api/main.py` - API endpoints
- `cli/qps_analyzer.py` - CLI commands
- `analysis/evaluation_engine.py` - Evaluation queries
- Dashboard API calls

### 2.3 Update CLI Help Text

In `cli/qps_analyzer.py`, update any help text that mentions table names:

```python
# Old
"""Import CSV data into performance_data table."""

# New
"""Import CSV data into rtb_daily table."""
```

---

## Part 3: Update Documentation

### 3.1 README.md

Update the schema section:

```markdown
## Database Schema

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `rtb_daily` | THE fact table - all CSV imports | metric_date, creative_id, billing_id, reached_queries, impressions |
| `creatives` | Creative inventory from API | id, format, canonical_size, approval_status |
| `campaigns` | User-defined campaign groupings | id, name, seat_id |
| `creative_campaigns` | Creative → Campaign mapping | creative_id, campaign_id |
```

### 3.2 Handover Document

Create updated `CatScan_Handover_v11.md` with:
- New table name prominently documented
- Note about the migration
- Updated example queries

---

## Part 4: Verification Queries

After migration, run these to verify everything works:

```sql
-- Verify rtb_daily exists and has data
SELECT COUNT(*) as total_rows,
       MIN(metric_date) as earliest,
       MAX(metric_date) as latest
FROM rtb_daily;

-- Verify indexes exist
SELECT name FROM sqlite_master 
WHERE type='index' AND tbl_name='rtb_daily';

-- Verify old tables are gone
SELECT name FROM sqlite_master 
WHERE type='table' AND name IN ('performance_data', 'performance_metrics', 'ai_campaigns');

-- Test a typical query
SELECT creative_size,
       SUM(reached_queries) as queries,
       SUM(impressions) as impressions
FROM rtb_daily
WHERE metric_date >= date('now', '-7 days')
GROUP BY creative_size
ORDER BY queries DESC
LIMIT 10;
```

---

## Part 5: CLI Command for Migration

Add to `cli/qps_analyzer.py`:

```python
@cli.command('migrate-schema')
@click.option('--dry-run', is_flag=True, help='Show what would change without changing')
@click.confirmation_option(prompt='This will modify the database. Continue?')
def migrate_schema(dry_run):
    """
    Run schema migration v12: Rename tables for clarity.
    
    Changes:
    - performance_data → rtb_daily
    - ai_campaigns → campaigns  
    - Drops unused legacy tables
    
    IMPORTANT: Creates automatic backup before migration.
    """
    from scripts.migrate_schema_v12 import migrate
    
    if dry_run:
        click.echo("DRY RUN - No changes will be made")
        click.echo("\nWould rename:")
        click.echo("  performance_data → rtb_daily")
        click.echo("  ai_campaigns → campaigns")
        click.echo("\nWould drop (if empty):")
        click.echo("  performance_metrics, video_metrics")
        click.echo("  rtb_traffic, daily_creative_summary")
        return
    
    success = migrate()
    
    if success:
        click.echo("\n⚠️  IMPORTANT: Update your code to use new table names!")
        click.echo("   performance_data → rtb_daily")
        click.echo("   ai_campaigns → campaigns")
```

---

## Implementation Order

### Step 1: Backup (5 min)
```bash
cp ~/.catscan/catscan.db ~/.catscan/catscan.db.pre_v12_backup
```

### Step 2: Run Migration Script (10 min)
```bash
cd creative-intelligence
python scripts/migrate_schema_v12.py
```

### Step 3: Update Python Code (30 min)
- `storage/sqlite_store.py`
- `api/main.py`
- `cli/qps_analyzer.py`
- `analysis/evaluation_engine.py`
- Any other files from grep search

### Step 4: Update Dashboard Code (20 min)
- API endpoint URLs (if they reference table names)
- Any direct SQL in frontend (shouldn't be any)

### Step 5: Update Documentation (15 min)
- README.md
- Handover document
- Any inline comments

### Step 6: Test (15 min)
- Run verification queries
- Test CLI commands: `catscan summary`, `catscan coverage`
- Test dashboard loads data
- Run `catscan profile-queries` to verify performance unchanged

---

## Post-Migration Schema

After cleanup, the schema should be:

```
CORE TABLES (actively used):
├── rtb_daily                 ← THE fact table (renamed from performance_data)
├── creatives                 ← API-synced creative inventory
├── campaigns                 ← User campaign groupings (renamed from ai_campaigns)
├── creative_campaigns        ← Junction: creative → campaign
├── fraud_signals             ← Detected fraud patterns
├── import_history            ← CSV import tracking
├── troubleshooting_data      ← Phase 11: RTB troubleshooting API data
└── troubleshooting_collections

DIMENSION TABLES:
├── apps                      ← App lookup
├── publishers                ← Publisher lookup
├── geographies               ← Geo lookup
├── buyer_seats               ← Seat/account lookup
└── seats                     ← Billing ID lookup

SUPPORT TABLES:
├── thumbnail_status          ← Video thumbnail generation status
├── import_anomalies          ← Flagged import issues
├── retention_config          ← Data retention settings
└── billing_accounts          ← Billing account lookup

ARCHIVED (if had data):
├── performance_metrics_archive  ← Old table, kept for reference
├── rtb_traffic_archive          ← Old table, kept for reference
└── campaigns_legacy             ← Old campaigns if had data
```

---

## Why `rtb_daily`?

| Criterion | `rtb_daily` | `performance_data` | `bid_facts` |
|-----------|-------------|-------------------|-------------|
| Distinct from old names | ✅ Completely | ❌ Same word | ✅ Yes |
| Describes content | ✅ RTB + granularity | ⚠️ Vague | ⚠️ Partial |
| Easy to type | ✅ 9 chars | ❌ 16 chars | ✅ 9 chars |
| Domain-specific | ✅ RTB context | ❌ Generic | ✅ Yes |
| Won't be confused | ✅ No other "rtb_" | ❌ performance_metrics exists | ✅ No conflict |

---

**Version:** 12.0  
**Phase:** Schema Cleanup  
**Created:** December 3, 2025