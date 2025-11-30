# ChatGPT Codex CLI Prompt: Schema Audit & Optimization

**Project:** RTB.cat Creative Intelligence Platform  
**Context:** Database has test data with duplicates. Schema needs verification.  
**Goal:** Clean data, fix UPSERT, optimize schema for production use

---

## 🎯 Current Problems

### Problem 1: Duplicate Rows
```sql
-- Same row appears 3 times!
144634|2025-11-29|50000|800|200000000
144634|2025-11-29|50000|800|200000000
144634|2025-11-29|50000|800|200000000
```

**Cause:** Import ran multiple times without proper UPSERT logic.

### Problem 2: Test Data (Not Real)
```
50000, 30000, 5000 impressions ← Too round, fake test data
```

### Problem 3: Schema Mismatch
The handover docs describe tables/columns that don't exist. Need to verify what's actually there.

---

## 📋 Part 1: Current Schema (Actual)

### creatives table
```sql
CREATE TABLE creatives (
    id TEXT PRIMARY KEY,                    -- Google's creative ID (e.g., "144634")
    name TEXT,                              -- Full path: "buyers/299038253/creatives/144634"
    format TEXT,                            -- NATIVE, DISPLAY, VIDEO, etc.
    account_id TEXT,                        -- Buyer account: "299038253"
    approval_status TEXT,                   -- APPROVED, DISAPPROVED, etc.
    width INTEGER,
    height INTEGER,
    final_url TEXT,                         -- Landing page URL
    display_url TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    utm_content TEXT,
    utm_term TEXT,
    advertiser_name TEXT,
    campaign_id TEXT,                       -- FK to campaigns (manual grouping)
    cluster_id TEXT,                        -- FK to clusters (AI grouping)
    raw_data TEXT,                          -- JSON blob of original API response
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    canonical_size TEXT,                    -- e.g., "300x250"
    size_category TEXT,                     -- e.g., "medium_rectangle"
    buyer_id TEXT
);
```

### performance_metrics table
```sql
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id TEXT NOT NULL,              -- FK to creatives.id
    campaign_id TEXT,
    metric_date DATE NOT NULL,
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    spend_micros INTEGER NOT NULL DEFAULT 0, -- Spend in micros (÷ 1,000,000 for dollars)
    cpm_micros INTEGER,
    cpc_micros INTEGER,
    geography TEXT,                         -- Country name or code
    device_type TEXT,
    placement TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    geo_id INTEGER,                         -- FK to geographies (not yet used)
    app_id_fk INTEGER,                      -- FK to apps (not yet used)
    billing_account_id INTEGER,             -- FK to billing accounts
    publisher_id_fk INTEGER,                -- FK to publishers
    seat_id INTEGER,                        -- FK to seats
    reached_queries INTEGER DEFAULT 0       -- QPS metric
);

-- Unique constraint (should prevent duplicates, but may have NULLs)
CREATE UNIQUE INDEX idx_perf_unique_daily ON performance_metrics(
    creative_id, metric_date, geography, device_type, placement
);
```

---

## 📋 Part 2: Why Duplicates Happened

The unique index includes `geography`, `device_type`, and `placement`. 

If ANY of these are NULL, SQLite treats each NULL as unique!

```sql
-- These are ALL considered different rows:
('144634', '2025-11-29', NULL, NULL, NULL)  -- Row 1
('144634', '2025-11-29', NULL, NULL, NULL)  -- Row 2 (NULL ≠ NULL in SQL!)
('144634', '2025-11-29', NULL, NULL, NULL)  -- Row 3
```

**Fix:** Either:
1. Don't allow NULLs in unique constraint columns
2. Use COALESCE to convert NULLs to a default value
3. Change the unique constraint

---

## 📋 Part 3: Schema Fixes

### Fix 1: Clean Up Duplicates

```sql
-- First, see what we're dealing with
SELECT creative_id, metric_date, geography, device_type, placement, COUNT(*) as cnt
FROM performance_metrics 
GROUP BY creative_id, metric_date, geography, device_type, placement
HAVING cnt > 1;

-- Delete duplicates, keeping lowest ID
DELETE FROM performance_metrics 
WHERE id NOT IN (
    SELECT MIN(id) 
    FROM performance_metrics 
    GROUP BY creative_id, metric_date, 
             COALESCE(geography, ''), 
             COALESCE(device_type, ''), 
             COALESCE(placement, '')
);

-- Verify
SELECT COUNT(*) FROM performance_metrics;
```

### Fix 2: Prevent Future Duplicates

```sql
-- Drop old index
DROP INDEX IF EXISTS idx_perf_unique_daily;

-- Create new index with COALESCE to handle NULLs
-- SQLite doesn't support this directly, so we need a different approach

-- Option A: Add NOT NULL defaults
ALTER TABLE performance_metrics 
ADD COLUMN geography_clean TEXT 
GENERATED ALWAYS AS (COALESCE(geography, 'UNKNOWN')) STORED;

-- Option B: Create a trigger to set defaults before insert
CREATE TRIGGER IF NOT EXISTS trg_perf_defaults
BEFORE INSERT ON performance_metrics
BEGIN
    SELECT RAISE(ABORT, 'geography cannot be null') 
    WHERE NEW.geography IS NULL;
END;

-- Option C (Recommended): Handle in application code with UPSERT
```

### Fix 3: Proper UPSERT in Import Code

```python
# api/storage/performance_repository.py

def insert_performance_row(self, row: dict):
    """
    Insert or update a performance metric row.
    Uses UPSERT to prevent duplicates.
    """
    # Ensure no NULLs in key fields
    geography = row.get('geography') or 'UNKNOWN'
    device_type = row.get('device_type') or 'UNKNOWN'
    placement = row.get('placement') or 'UNKNOWN'
    
    self.db.execute("""
        INSERT INTO performance_metrics (
            creative_id, metric_date, geography, device_type, placement,
            impressions, clicks, spend_micros, reached_queries, seat_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(creative_id, metric_date, geography, device_type, placement) 
        DO UPDATE SET
            impressions = impressions + excluded.impressions,
            clicks = clicks + excluded.clicks,
            spend_micros = spend_micros + excluded.spend_micros,
            reached_queries = reached_queries + excluded.reached_queries,
            updated_at = CURRENT_TIMESTAMP
    """, (
        row['creative_id'],
        row['metric_date'],
        geography,
        device_type,
        placement,
        row.get('impressions', 0),
        row.get('clicks', 0),
        row.get('spend_micros', 0),
        row.get('reached_queries', 0),
        row.get('seat_id'),
    ))
```

---

## 📋 Part 4: Recommended Schema (Optimized)

Based on RTB.cat's actual needs:

```sql
-- ============================================
-- LOOKUP TABLES (normalize repeated values)
-- ============================================

-- Buyer Accounts (the company)
CREATE TABLE IF NOT EXISTS buyer_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT UNIQUE NOT NULL,        -- "299038253"
    account_name TEXT,                       -- "Tuky Data Research Ltd."
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seats (bidding entities, may be same as account for small buyers)
CREATE TABLE IF NOT EXISTS seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_account_id INTEGER REFERENCES buyer_accounts(id),
    billing_id TEXT UNIQUE,                  -- From CSV: "Billing ID"
    seat_name TEXT,                          -- User-friendly name
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Geographies (store each country once)
CREATE TABLE IF NOT EXISTS geographies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT,                       -- "US", "GB", "AU"
    country_name TEXT UNIQUE NOT NULL        -- "United States"
);

-- Apps (store each app once)
CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT UNIQUE,                      -- Google's app ID
    app_name TEXT,                           -- "Candy Crush Saga"
    platform TEXT,                           -- "iOS", "Android"
    quality_tier TEXT DEFAULT 'unknown',     -- "premium", "standard", "suspicious"
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- MAIN TABLES
-- ============================================

-- Creatives (keep existing, just add seat_id)
-- ALTER TABLE creatives ADD COLUMN seat_id INTEGER REFERENCES seats(id);

-- Performance Metrics (redesigned)
CREATE TABLE IF NOT EXISTS performance_metrics_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Keys
    creative_id TEXT NOT NULL REFERENCES creatives(id),
    seat_id INTEGER REFERENCES seats(id),
    metric_date DATE NOT NULL,
    
    -- Normalized foreign keys (integers, not strings)
    geo_id INTEGER REFERENCES geographies(id),
    app_id INTEGER REFERENCES apps(id),
    
    -- Metrics
    reached_queries INTEGER DEFAULT 0,       -- Bid requests seen (QPS)
    impressions INTEGER DEFAULT 0,           -- Wins
    clicks INTEGER DEFAULT 0,
    spend_micros INTEGER DEFAULT 0,          -- Spend × 1,000,000
    
    -- Video metrics (nullable, only for video creatives)
    video_starts INTEGER,
    video_completions INTEGER,
    vast_errors INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint (NO NULLs in these columns!)
    UNIQUE(creative_id, metric_date, geo_id, app_id)
);

-- Indexes for fast queries
CREATE INDEX idx_perf_v2_seat_date ON performance_metrics_v2(seat_id, metric_date DESC);
CREATE INDEX idx_perf_v2_creative ON performance_metrics_v2(creative_id);
CREATE INDEX idx_perf_v2_geo ON performance_metrics_v2(geo_id);
CREATE INDEX idx_perf_v2_date ON performance_metrics_v2(metric_date DESC);

-- ============================================
-- AGGREGATION TABLES (for fast dashboard queries)
-- ============================================

-- Daily totals per creative (auto-updated after import)
CREATE TABLE IF NOT EXISTS creative_daily_totals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id TEXT NOT NULL,
    seat_id INTEGER,
    metric_date DATE NOT NULL,
    
    -- Aggregated metrics
    total_queries INTEGER DEFAULT 0,
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_spend_micros INTEGER DEFAULT 0,
    
    -- Calculated fields
    win_rate REAL,                           -- impressions / queries
    ctr REAL,                                -- clicks / impressions
    cpm_micros INTEGER,                      -- (spend / impressions) * 1000
    
    -- Counts
    unique_geos INTEGER,
    unique_apps INTEGER,
    
    UNIQUE(creative_id, metric_date)
);

CREATE INDEX idx_cdt_creative_date ON creative_daily_totals(creative_id, metric_date DESC);
CREATE INDEX idx_cdt_seat_date ON creative_daily_totals(seat_id, metric_date DESC);
```

---

## 📋 Part 5: Migration Strategy

Since there's only 41 rows (and they're test data), easiest approach:

### Option A: Start Fresh (Recommended)

```sql
-- Backup just in case
-- $ cp ~/.rtbcat/rtbcat.db ~/.rtbcat/rtbcat_backup_$(date +%Y%m%d).db

-- Clear test data
DELETE FROM performance_metrics;

-- Verify
SELECT COUNT(*) FROM performance_metrics;  -- Should be 0
```

Then fix the import code to use proper UPSERT before importing real data.

### Option B: Migrate Existing Data

```sql
-- 1. Create new tables
-- 2. Migrate data with deduplication
-- 3. Drop old tables
-- 4. Rename new tables

-- This is more complex - only needed if you have real data to preserve
```

---

## 📋 Part 6: Import Code Fix

The CSV import needs to:

1. **Normalize geography** → Look up or create in `geographies` table, get `geo_id`
2. **Normalize app** → Look up or create in `apps` table, get `app_id`  
3. **Use UPSERT** → Prevent duplicates, aggregate if same key exists
4. **Set defaults** → Never insert NULL for key columns

```python
# api/lib/csv_importer.py

class PerformanceImporter:
    def __init__(self, db):
        self.db = db
        self.geo_cache = {}
        self.app_cache = {}
    
    def get_or_create_geo(self, country_name: str) -> int:
        """Get geo_id, creating if needed."""
        if not country_name:
            country_name = "Unknown"
        
        if country_name in self.geo_cache:
            return self.geo_cache[country_name]
        
        # Try to find existing
        result = self.db.execute(
            "SELECT id FROM geographies WHERE country_name = ?",
            (country_name,)
        ).fetchone()
        
        if result:
            self.geo_cache[country_name] = result[0]
            return result[0]
        
        # Create new
        cursor = self.db.execute(
            "INSERT INTO geographies (country_name) VALUES (?)",
            (country_name,)
        )
        geo_id = cursor.lastrowid
        self.geo_cache[country_name] = geo_id
        return geo_id
    
    def import_row(self, row: dict) -> bool:
        """Import a single performance row with UPSERT."""
        
        # Normalize
        geo_id = self.get_or_create_geo(row.get('country') or row.get('geography'))
        app_id = self.get_or_create_app(row.get('app_id'), row.get('app_name'))
        
        # Convert spend to micros if needed
        spend = row.get('spend', 0)
        if isinstance(spend, str):
            spend = float(spend.replace('$', '').replace(',', ''))
        spend_micros = int(spend * 1_000_000)
        
        # UPSERT
        self.db.execute("""
            INSERT INTO performance_metrics_v2 (
                creative_id, metric_date, geo_id, app_id, seat_id,
                reached_queries, impressions, clicks, spend_micros
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creative_id, metric_date, geo_id, app_id) 
            DO UPDATE SET
                reached_queries = reached_queries + excluded.reached_queries,
                impressions = impressions + excluded.impressions,
                clicks = clicks + excluded.clicks,
                spend_micros = spend_micros + excluded.spend_micros,
                updated_at = CURRENT_TIMESTAMP
        """, (
            row['creative_id'],
            row['date'],
            geo_id,
            app_id,
            row.get('seat_id'),
            row.get('reached_queries', 0),
            row.get('impressions', 0),
            row.get('clicks', 0),
            spend_micros,
        ))
        
        return True
```

---

## 📋 Part 7: Files to Modify

```
api/storage/sqlite_store.py          # Add new tables, fix schema
api/storage/performance_repository.py # Fix UPSERT logic
api/lib/csv_importer.py              # Normalize + UPSERT
dashboard/src/lib/csv-parser.ts      # Ensure clean data on frontend
```

---

## 📋 Part 8: Testing

After fixes:

```bash
# 1. Clear test data
sqlite3 ~/.rtbcat/rtbcat.db "DELETE FROM performance_metrics;"

# 2. Import real CSV
# (Use the UI at /import)

# 3. Verify no duplicates
sqlite3 ~/.rtbcat/rtbcat.db "SELECT creative_id, metric_date, COUNT(*) as cnt FROM performance_metrics GROUP BY creative_id, metric_date HAVING cnt > 1;"
# Should return nothing

# 4. Check totals make sense
sqlite3 ~/.rtbcat/rtbcat.db "SELECT creative_id, SUM(impressions), SUM(spend_micros)/1000000.0 as spend_dollars FROM performance_metrics GROUP BY creative_id;"
```

---

## 🚀 Summary

| Problem | Fix |
|---------|-----|
| Duplicate rows | Delete + fix UPSERT |
| NULL in unique columns | Default to 'Unknown' |
| Test data | Delete and import real CSV |
| Schema mismatch | Use actual schema, not docs |
| Repeated strings | Normalize to lookup tables |

**Recommended order:**
1. Clear test data
2. Fix import code with UPSERT
3. Import real Google CSV
4. Verify no duplicates

---

**Location:**
```
Database: ~/.rtbcat/rtbcat.db
Project: /home/jen/Documents/rtbcat-platform/
```

**After code changes:**
```bash
sudo systemctl restart rtbcat-api
```
