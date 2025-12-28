# Claude CLI Prompt 1/4: Database Reset & New Schema

## Context

RTBcat is being rebuilt with a unified data architecture. This prompt:
1. Drops old/conflicting tables
2. Creates new `performance_data` table
3. Creates validation helper views

**Project:** `/home/jen/Documents/rtbcat-platform/creative-intelligence/`
**Database:** `~/.rtbcat/rtbcat.db`

---

## Task

### Step 1: Create Database Reset Script

**File: `scripts/reset_database.py`**

```python
#!/usr/bin/env python3
"""Reset database tables for clean unified architecture."""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.rtbcat/rtbcat.db")

def backup_database():
    """Create backup before destructive changes."""
    if os.path.exists(DB_PATH):
        backup_path = DB_PATH.replace(".db", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        import shutil
        shutil.copy(DB_PATH, backup_path)
        print(f"Backup created: {backup_path}")
        return backup_path
    return None

def reset_tables():
    """Drop old tables and create new unified schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n1. Dropping old tables...")
    cursor.executescript("""
        DROP TABLE IF EXISTS size_metrics_daily;
        DROP TABLE IF EXISTS performance_metrics;
        DROP TABLE IF EXISTS fraud_signals;
    """)
    print("   ✓ Dropped: size_metrics_daily, performance_metrics, fraud_signals")
    
    print("\n2. Creating unified performance_data table...")
    cursor.executescript("""
        -- Unified Performance Data Table
        -- Stores raw CSV data from Authorized Buyers exports
        -- No aggregation at import - one CSV row = one DB row
        
        CREATE TABLE IF NOT EXISTS performance_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- REQUIRED: Date (every export has this)
            metric_date DATE NOT NULL,
            
            -- DIMENSIONS (all optional - depend on export config)
            -- Identity
            creative_id TEXT,
            billing_id TEXT,
            
            -- Creative info
            creative_size TEXT,
            creative_format TEXT,
            
            -- Geography/Platform
            country TEXT,
            platform TEXT,
            environment TEXT,
            
            -- App info (Mobile app ID is package name like "com.spotify.music")
            app_id TEXT,
            app_name TEXT,
            
            -- Publisher info
            publisher_id TEXT,
            publisher_name TEXT,
            publisher_domain TEXT,
            
            -- Deal info
            deal_id TEXT,
            deal_name TEXT,
            transaction_type TEXT,
            
            -- Buyer/Advertiser
            advertiser TEXT,
            buyer_account_id TEXT,
            buyer_account_name TEXT,
            
            -- METRICS (store what's available)
            reached_queries INTEGER,
            impressions INTEGER,
            clicks INTEGER,
            spend_micros INTEGER,
            
            -- Video metrics
            video_starts INTEGER,
            video_first_quartile INTEGER,
            video_midpoint INTEGER,
            video_third_quartile INTEGER,
            video_completions INTEGER,
            vast_errors INTEGER,
            engaged_views INTEGER,
            
            -- Viewability
            active_view_measurable INTEGER,
            active_view_viewable INTEGER,
            
            -- Flags
            gma_sdk INTEGER DEFAULT 0,
            buyer_sdk INTEGER DEFAULT 0,
            
            -- METADATA
            row_hash TEXT,
            import_batch_id TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Prevent exact duplicate rows
            UNIQUE(row_hash)
        );
        
        -- Indices for common queries
        CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_data(metric_date);
        CREATE INDEX IF NOT EXISTS idx_perf_creative ON performance_data(creative_id);
        CREATE INDEX IF NOT EXISTS idx_perf_billing ON performance_data(billing_id);
        CREATE INDEX IF NOT EXISTS idx_perf_size ON performance_data(creative_size);
        CREATE INDEX IF NOT EXISTS idx_perf_country ON performance_data(country);
        CREATE INDEX IF NOT EXISTS idx_perf_app ON performance_data(app_id);
        CREATE INDEX IF NOT EXISTS idx_perf_batch ON performance_data(import_batch_id);
        
        -- Compound indices for reports
        CREATE INDEX IF NOT EXISTS idx_perf_date_billing ON performance_data(metric_date, billing_id);
        CREATE INDEX IF NOT EXISTS idx_perf_date_size ON performance_data(metric_date, creative_size);
        CREATE INDEX IF NOT EXISTS idx_perf_date_creative ON performance_data(metric_date, creative_id);
    """)
    print("   ✓ Created: performance_data with indices")
    
    print("\n3. Creating fraud_signals table...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS fraud_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            entity_name TEXT,
            
            signal_type TEXT NOT NULL,
            signal_strength TEXT NOT NULL,
            evidence TEXT,
            
            days_observed INTEGER DEFAULT 1,
            first_seen DATE,
            last_seen DATE,
            
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            notes TEXT,
            
            UNIQUE(entity_type, entity_id, signal_type)
        );
        
        CREATE INDEX IF NOT EXISTS idx_fraud_status ON fraud_signals(status);
        CREATE INDEX IF NOT EXISTS idx_fraud_entity ON fraud_signals(entity_type, entity_id);
    """)
    print("   ✓ Created: fraud_signals")
    
    print("\n4. Creating import_history table...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL UNIQUE,
            filename TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            rows_read INTEGER DEFAULT 0,
            rows_imported INTEGER DEFAULT 0,
            rows_skipped INTEGER DEFAULT 0,
            rows_duplicate INTEGER DEFAULT 0,
            
            date_range_start DATE,
            date_range_end DATE,
            
            columns_found TEXT,
            columns_missing TEXT,
            
            total_reached INTEGER DEFAULT 0,
            total_impressions INTEGER DEFAULT 0,
            total_spend_usd REAL DEFAULT 0,
            
            status TEXT DEFAULT 'complete',
            error_message TEXT
        );
    """)
    print("   ✓ Created: import_history")
    
    conn.commit()
    
    # Verify creatives table still exists
    cursor.execute("SELECT COUNT(*) FROM creatives")
    creative_count = cursor.fetchone()[0]
    print(f"\n5. Verified: creatives table intact ({creative_count} rows)")
    
    conn.close()
    print("\n✅ Database reset complete!")

if __name__ == "__main__":
    print("=" * 60)
    print("RTBcat Database Reset")
    print("=" * 60)
    
    confirm = input("\nThis will DELETE performance data (creatives preserved).\nContinue? (yes/no): ")
    
    if confirm.lower() == "yes":
        backup_database()
        reset_tables()
        print("\nNext: Run the CSV importer")
        print("  python cli/qps_analyzer.py import <your_csv_file>")
    else:
        print("Cancelled.")
```

### Step 2: Run the Script

```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python scripts/reset_database.py
```

---

## Success Criteria

- [ ] Backup created
- [ ] Old tables dropped (size_metrics_daily, performance_metrics, fraud_signals)
- [ ] New performance_data table created with all columns
- [ ] fraud_signals table created
- [ ] import_history table created
- [ ] creatives table preserved (653 rows)

---

## After Completing

Tell Jen: "Database reset complete. Ready for Prompt 2 (CSV Importer)."
