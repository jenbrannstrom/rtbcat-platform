# Claude CLI Prompt: Clean Slate - Unified Performance Data

## Context

RTBcat is being rebuilt with a clean, professional architecture suitable for distribution as a free tool to large Google Authorized Buyers accounts. The current state has accumulated technical debt:

- Two tables storing overlapping data (`performance_metrics`, `size_metrics_daily`)
- Two import paths (dashboard UI, CLI) that populate different tables
- Dashboard `/import` page with confusing "General" vs "Video" options
- Incomplete data capture in both paths

**Goal:** One table, one importer, all CSV data captured, raw storage (no aggregation at import).

**Project Location:** `/home/jen/Documents/rtbcat-platform/`
**Database:** `~/.rtbcat/rtbcat.db`

---

## Philosophy

1. **Store raw data** - No aggregation at import time. Keep every row from the CSV exactly as Google provides it.
2. **Analyze at query time** - Reports aggregate data when needed, not before.
3. **Single source of truth** - One table for all performance data.
4. **Professional quality** - This tool will be distributed to gain trust with potential enterprise clients.

---

## Part 1: Database Cleanup

### Drop Old Tables

Run this SQL to clean up:

```sql
-- Drop the QPS-specific table (data will be re-imported)
DROP TABLE IF EXISTS size_metrics_daily;

-- Drop old performance_metrics (will recreate with better schema)
DROP TABLE IF EXISTS performance_metrics;

-- Drop fraud signals (will recreate)
DROP TABLE IF EXISTS fraud_signals;

-- Keep these tables:
-- creatives (653 rows from API)
-- geographies (51 pre-populated)
-- apps, publishers (reference data)
-- import_anomalies (useful for tracking issues)
```

### Create New Unified Table

**File: `storage/migrations/003_unified_performance.sql`**

```sql
-- Unified Performance Data Table
-- Stores raw CSV data from BigQuery exports
-- No aggregation - one row per CSV row
-- Analysis/aggregation happens at query time

CREATE TABLE IF NOT EXISTS performance_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Date & Identity
    metric_date DATE NOT NULL,
    creative_id TEXT NOT NULL,              -- Links to creatives.id
    billing_id TEXT NOT NULL,               -- Pretargeting config
    
    -- Dimensions (for filtering/grouping)
    creative_size TEXT,                     -- "300x250", "Interstitial", "Video 9:16"
    creative_format TEXT,                   -- "Video", "Display", "Native"
    country TEXT,                           -- "India", "Canada", "Brazil"
    platform TEXT,                          -- "High-end mobile devices", "Desktop"
    environment TEXT,                       -- "App", "Web"
    app_id TEXT,                            -- Mobile app ID (e.g., "358801284")
    app_name TEXT,                          -- Mobile app name (e.g., "Flipboard")
    publisher_id TEXT,                      -- Publisher ID
    publisher_name TEXT,                    -- Publisher name
    publisher_domain TEXT,                  -- Domain for web inventory
    
    -- Funnel Metrics (the core data)
    reached_queries INTEGER DEFAULT 0,      -- QPS that matched pretargeting
    impressions INTEGER DEFAULT 0,          -- Delivered impressions
    clicks INTEGER DEFAULT 0,               -- User clicks
    spend_micros INTEGER DEFAULT 0,         -- Spend in micros (1M = $1.00)
    
    -- Video Metrics
    video_starts INTEGER DEFAULT 0,
    video_first_quartile INTEGER DEFAULT 0,
    video_midpoint INTEGER DEFAULT 0,
    video_third_quartile INTEGER DEFAULT 0,
    video_completions INTEGER DEFAULT 0,
    vast_errors INTEGER DEFAULT 0,
    
    -- Viewability
    active_view_measurable INTEGER DEFAULT 0,
    active_view_viewable INTEGER DEFAULT 0,
    
    -- Deal Info
    deal_id TEXT,
    deal_name TEXT,
    transaction_type TEXT,                  -- "Open auction", "Private auction"
    
    -- Additional Context
    advertiser TEXT,
    buyer_account_id TEXT,
    buyer_account_name TEXT,
    gma_sdk INTEGER DEFAULT 0,              -- 1 if GMA SDK, 0 otherwise
    
    -- Metadata
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    import_batch_id TEXT,                   -- To track which import added this row
    
    -- Unique constraint prevents duplicate imports
    -- Same creative + date + billing + country + app = same row
    UNIQUE(metric_date, creative_id, billing_id, country, app_id, deal_id)
);

-- Indices for common query patterns
CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_data(metric_date);
CREATE INDEX IF NOT EXISTS idx_perf_creative ON performance_data(creative_id);
CREATE INDEX IF NOT EXISTS idx_perf_billing ON performance_data(billing_id);
CREATE INDEX IF NOT EXISTS idx_perf_size ON performance_data(creative_size);
CREATE INDEX IF NOT EXISTS idx_perf_country ON performance_data(country);
CREATE INDEX IF NOT EXISTS idx_perf_app ON performance_data(app_id);
CREATE INDEX IF NOT EXISTS idx_perf_date_billing ON performance_data(metric_date, billing_id);
CREATE INDEX IF NOT EXISTS idx_perf_date_size ON performance_data(metric_date, creative_size);

-- Fraud signals table (clean version)
CREATE TABLE IF NOT EXISTS fraud_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- What's suspicious
    entity_type TEXT NOT NULL,              -- 'app', 'publisher', 'creative', 'size'
    entity_id TEXT NOT NULL,
    entity_name TEXT,
    
    -- Signal details
    signal_type TEXT NOT NULL,              -- 'high_ctr', 'clicks_exceed_impressions', etc.
    signal_strength TEXT NOT NULL,          -- 'LOW', 'MEDIUM', 'HIGH'
    evidence TEXT,                          -- JSON with supporting data
    
    -- Context
    days_observed INTEGER DEFAULT 1,
    first_seen DATE,
    last_seen DATE,
    
    -- Status tracking
    status TEXT DEFAULT 'pending',          -- 'pending', 'reviewed', 'blocked', 'cleared'
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    notes TEXT,
    
    UNIQUE(entity_type, entity_id, signal_type)
);

CREATE INDEX IF NOT EXISTS idx_fraud_status ON fraud_signals(status);
CREATE INDEX IF NOT EXISTS idx_fraud_entity ON fraud_signals(entity_type, entity_id);
```

---

## Part 2: Unified CSV Importer

**File: `qps/importer.py`** (REPLACE entire file)

```python
"""Unified BigQuery CSV Importer.

Imports daily CSV exports from Google Authorized Buyers BigQuery.
Stores raw data - no aggregation at import time.

The BigQuery CSV has 46 columns. We capture all the important ones
and store each row as-is for maximum analysis flexibility.

Usage:
    from qps.importer import import_bigquery_csv
    result = import_bigquery_csv("/path/to/export.csv")
    print(f"Imported {result.rows_imported} rows")
"""

import csv
import sqlite3
import os
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.rtbcat/rtbcat.db")


@dataclass
class ImportResult:
    """Result of a CSV import operation."""
    
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    creative_ids_found: int = 0
    billing_ids_found: List[str] = field(default_factory=list)
    sizes_found: List[str] = field(default_factory=list)
    countries_found: List[str] = field(default_factory=list)
    total_reached_queries: int = 0
    total_impressions: int = 0
    total_spend_usd: float = 0.0
    import_batch_id: str = ""
    errors: List[str] = field(default_factory=list)


# BigQuery CSV column names (exact as exported)
# Map from CSV header → our column name
COLUMN_MAP = {
    "#Day": "metric_date",
    "Creative ID": "creative_id",
    "Billing ID": "billing_id",
    "Creative size": "creative_size",
    "Creative format": "creative_format",
    "Country": "country",
    "Platform": "platform",
    "Environment": "environment",
    "Mobile app ID": "app_id",
    "Mobile app name": "app_name",
    "Publisher ID": "publisher_id",
    "Publisher name": "publisher_name",
    "Publisher domain": "publisher_domain",
    "Reached queries": "reached_queries",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Spend _buyer currency_": "spend",
    "Video starts": "video_starts",
    "Video reached first quartile": "video_first_quartile",
    "Video reached midpoint": "video_midpoint",
    "Video reached third quartile": "video_third_quartile",
    "Video completions": "video_completions",
    "VAST error count": "vast_errors",
    "Active view measurable": "active_view_measurable",
    "Active view viewable": "active_view_viewable",
    "Deal ID": "deal_id",
    "Deal name": "deal_name",
    "Transaction type": "transaction_type",
    "Advertiser": "advertiser",
    "Buyer account ID": "buyer_account_id",
    "Buyer account name": "buyer_account_name",
    "GMA SDK": "gma_sdk",
}


def parse_date(date_str: str) -> str:
    """Parse date from MM/DD/YYYY to YYYY-MM-DD format."""
    if not date_str:
        return ""
    
    formats = [
        "%m/%d/%Y",   # 11/30/2025 (BigQuery default)
        "%m/%d/%y",   # 11/30/25
        "%Y-%m-%d",   # 2025-11-30 (already correct)
        "%d/%m/%Y",   # 30/11/2025 (European)
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return date_str


def parse_int(value) -> int:
    """Parse integer from string or number."""
    if value is None or value == "":
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def parse_float(value) -> float:
    """Parse float from string or number."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return 0.0


def parse_bool(value) -> int:
    """Parse boolean to int (1 or 0)."""
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return 1 if value else 0
    val_str = str(value).strip().upper()
    return 1 if val_str in ("TRUE", "1", "YES") else 0


def ensure_table_exists(conn: sqlite3.Connection) -> None:
    """Create the performance_data table if it doesn't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS performance_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date DATE NOT NULL,
            creative_id TEXT NOT NULL,
            billing_id TEXT NOT NULL,
            creative_size TEXT,
            creative_format TEXT,
            country TEXT,
            platform TEXT,
            environment TEXT,
            app_id TEXT,
            app_name TEXT,
            publisher_id TEXT,
            publisher_name TEXT,
            publisher_domain TEXT,
            reached_queries INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            spend_micros INTEGER DEFAULT 0,
            video_starts INTEGER DEFAULT 0,
            video_first_quartile INTEGER DEFAULT 0,
            video_midpoint INTEGER DEFAULT 0,
            video_third_quartile INTEGER DEFAULT 0,
            video_completions INTEGER DEFAULT 0,
            vast_errors INTEGER DEFAULT 0,
            active_view_measurable INTEGER DEFAULT 0,
            active_view_viewable INTEGER DEFAULT 0,
            deal_id TEXT,
            deal_name TEXT,
            transaction_type TEXT,
            advertiser TEXT,
            buyer_account_id TEXT,
            buyer_account_name TEXT,
            gma_sdk INTEGER DEFAULT 0,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            import_batch_id TEXT,
            UNIQUE(metric_date, creative_id, billing_id, country, app_id, deal_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_data(metric_date);
        CREATE INDEX IF NOT EXISTS idx_perf_creative ON performance_data(creative_id);
        CREATE INDEX IF NOT EXISTS idx_perf_billing ON performance_data(billing_id);
        CREATE INDEX IF NOT EXISTS idx_perf_size ON performance_data(creative_size);
        CREATE INDEX IF NOT EXISTS idx_perf_country ON performance_data(country);
        CREATE INDEX IF NOT EXISTS idx_perf_app ON performance_data(app_id);
    """)
    conn.commit()


def import_bigquery_csv(csv_path: str, db_path: str = DB_PATH) -> ImportResult:
    """
    Import a BigQuery CSV file into performance_data table.
    
    Stores raw data - no aggregation. Each CSV row becomes one database row.
    Uses UPSERT to handle re-imports gracefully (updates existing rows).
    
    Args:
        csv_path: Path to the BigQuery CSV export file
        db_path: Path to the SQLite database
    
    Returns:
        ImportResult with statistics about the import
    """
    result = ImportResult()
    result.import_batch_id = str(uuid.uuid4())[:8]
    
    if not os.path.exists(csv_path):
        result.errors.append(f"File not found: {csv_path}")
        return result
    
    file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    logger.info(f"Starting import of {csv_path} ({file_size_mb:.1f} MB)")
    
    conn = sqlite3.connect(db_path)
    ensure_table_exists(conn)
    cursor = conn.cursor()
    
    # Track unique values
    creative_ids = set()
    billing_ids = set()
    sizes = set()
    countries = set()
    min_date = None
    max_date = None
    
    # Batch insert for performance
    BATCH_SIZE = 1000
    batch = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):
                result.rows_read += 1
                
                try:
                    # Parse required fields
                    metric_date = parse_date(row.get("#Day", ""))
                    creative_id = str(row.get("Creative ID", "")).strip()
                    billing_id = str(row.get("Billing ID", "")).strip()
                    
                    if not metric_date or not creative_id or not billing_id:
                        result.rows_skipped += 1
                        continue
                    
                    # Track date range
                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date
                    
                    # Parse all fields
                    creative_size = row.get("Creative size", "").strip() or None
                    creative_format = row.get("Creative format", "").strip() or None
                    country = row.get("Country", "").strip() or None
                    platform = row.get("Platform", "").strip() or None
                    environment = row.get("Environment", "").strip() or None
                    app_id = row.get("Mobile app ID", "").strip() or None
                    app_name = row.get("Mobile app name", "").strip() or None
                    publisher_id = row.get("Publisher ID", "").strip() or None
                    publisher_name = row.get("Publisher name", "").strip() or None
                    publisher_domain = row.get("Publisher domain", "").strip() or None
                    
                    reached_queries = parse_int(row.get("Reached queries", 0))
                    impressions = parse_int(row.get("Impressions", 0))
                    clicks = parse_int(row.get("Clicks", 0))
                    spend_usd = parse_float(row.get("Spend _buyer currency_", 0))
                    spend_micros = int(spend_usd * 1_000_000)
                    
                    video_starts = parse_int(row.get("Video starts", 0))
                    video_first_quartile = parse_int(row.get("Video reached first quartile", 0))
                    video_midpoint = parse_int(row.get("Video reached midpoint", 0))
                    video_third_quartile = parse_int(row.get("Video reached third quartile", 0))
                    video_completions = parse_int(row.get("Video completions", 0))
                    vast_errors = parse_int(row.get("VAST error count", 0))
                    
                    active_view_measurable = parse_int(row.get("Active view measurable", 0))
                    active_view_viewable = parse_int(row.get("Active view viewable", 0))
                    
                    deal_id = row.get("Deal ID", "").strip() or None
                    if deal_id == "0":
                        deal_id = None
                    deal_name = row.get("Deal name", "").strip() or None
                    if deal_name == "(none)":
                        deal_name = None
                    transaction_type = row.get("Transaction type", "").strip() or None
                    
                    advertiser = row.get("Advertiser", "").strip() or None
                    buyer_account_id = row.get("Buyer account ID", "").strip() or None
                    buyer_account_name = row.get("Buyer account name", "").strip() or None
                    gma_sdk = parse_bool(row.get("GMA SDK", False))
                    
                    # Track unique values
                    creative_ids.add(creative_id)
                    billing_ids.add(billing_id)
                    if creative_size:
                        sizes.add(creative_size)
                    if country:
                        countries.add(country)
                    
                    # Track totals
                    result.total_reached_queries += reached_queries
                    result.total_impressions += impressions
                    result.total_spend_usd += spend_usd
                    
                    # Add to batch
                    batch.append((
                        metric_date, creative_id, billing_id,
                        creative_size, creative_format, country, platform, environment,
                        app_id, app_name, publisher_id, publisher_name, publisher_domain,
                        reached_queries, impressions, clicks, spend_micros,
                        video_starts, video_first_quartile, video_midpoint,
                        video_third_quartile, video_completions, vast_errors,
                        active_view_measurable, active_view_viewable,
                        deal_id, deal_name, transaction_type,
                        advertiser, buyer_account_id, buyer_account_name, gma_sdk,
                        result.import_batch_id
                    ))
                    
                    # Insert batch when full
                    if len(batch) >= BATCH_SIZE:
                        inserted, duplicates = _insert_batch(cursor, batch)
                        result.rows_imported += inserted
                        result.rows_duplicate += duplicates
                        batch = []
                        
                        # Progress logging for large files
                        if result.rows_read % 50000 == 0:
                            logger.info(f"Progress: {result.rows_read:,} rows read, {result.rows_imported:,} imported")
                
                except Exception as e:
                    result.rows_skipped += 1
                    if len(result.errors) < 50:
                        result.errors.append(f"Row {row_num}: {str(e)}")
        
        # Insert remaining batch
        if batch:
            inserted, duplicates = _insert_batch(cursor, batch)
            result.rows_imported += inserted
            result.rows_duplicate += duplicates
        
        conn.commit()
        
    except Exception as e:
        result.errors.append(f"Fatal error: {str(e)}")
        logger.error(f"Import failed: {e}")
    
    finally:
        conn.close()
    
    # Populate result
    result.date_range_start = min_date
    result.date_range_end = max_date
    result.creative_ids_found = len(creative_ids)
    result.billing_ids_found = sorted(list(billing_ids))
    result.sizes_found = sorted(list(sizes))
    result.countries_found = sorted(list(countries))
    
    logger.info(
        f"Import complete: {result.rows_imported:,} imported, "
        f"{result.rows_duplicate:,} duplicates, {result.rows_skipped:,} skipped"
    )
    
    return result


def _insert_batch(cursor: sqlite3.Cursor, batch: list) -> tuple:
    """Insert a batch of rows, returning (inserted_count, duplicate_count)."""
    inserted = 0
    duplicates = 0
    
    for row in batch:
        try:
            cursor.execute("""
                INSERT INTO performance_data (
                    metric_date, creative_id, billing_id,
                    creative_size, creative_format, country, platform, environment,
                    app_id, app_name, publisher_id, publisher_name, publisher_domain,
                    reached_queries, impressions, clicks, spend_micros,
                    video_starts, video_first_quartile, video_midpoint,
                    video_third_quartile, video_completions, vast_errors,
                    active_view_measurable, active_view_viewable,
                    deal_id, deal_name, transaction_type,
                    advertiser, buyer_account_id, buyer_account_name, gma_sdk,
                    import_batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric_date, creative_id, billing_id, country, app_id, deal_id)
                DO UPDATE SET
                    reached_queries = excluded.reached_queries,
                    impressions = excluded.impressions,
                    clicks = excluded.clicks,
                    spend_micros = excluded.spend_micros,
                    video_starts = excluded.video_starts,
                    video_completions = excluded.video_completions,
                    vast_errors = excluded.vast_errors,
                    imported_at = CURRENT_TIMESTAMP,
                    import_batch_id = excluded.import_batch_id
            """, row)
            inserted += 1
        except sqlite3.IntegrityError:
            duplicates += 1
        except Exception as e:
            logger.warning(f"Insert error: {e}")
    
    return inserted, duplicates


def get_data_summary(db_path: str = DB_PATH) -> Dict:
    """Get summary statistics of imported data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT metric_date) as unique_dates,
                COUNT(DISTINCT creative_id) as unique_creatives,
                COUNT(DISTINCT billing_id) as unique_billing_ids,
                COUNT(DISTINCT creative_size) as unique_sizes,
                COUNT(DISTINCT country) as unique_countries,
                MIN(metric_date) as min_date,
                MAX(metric_date) as max_date,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                SUM(spend_micros) as total_spend_micros
            FROM performance_data
        """)
        row = cursor.fetchone()
        
        return {
            "total_rows": row[0] or 0,
            "unique_dates": row[1] or 0,
            "unique_creatives": row[2] or 0,
            "unique_billing_ids": row[3] or 0,
            "unique_sizes": row[4] or 0,
            "unique_countries": row[5] or 0,
            "date_range": {
                "start": row[6],
                "end": row[7],
            },
            "total_reached_queries": row[8] or 0,
            "total_impressions": row[9] or 0,
            "total_clicks": row[10] or 0,
            "total_spend_usd": (row[11] or 0) / 1_000_000,
        }
    finally:
        conn.close()


# Keep backward compatibility
def get_import_summary(db_path: str = DB_PATH) -> Dict:
    """Alias for get_data_summary for backward compatibility."""
    return get_data_summary(db_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m qps.importer <csv_file>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    print(f"Importing {csv_path}...")
    
    result = import_bigquery_csv(csv_path)
    
    print(f"\n{'='*60}")
    print("IMPORT COMPLETE")
    print(f"{'='*60}")
    print(f"  Rows read:        {result.rows_read:,}")
    print(f"  Rows imported:    {result.rows_imported:,}")
    print(f"  Rows duplicates:  {result.rows_duplicate:,}")
    print(f"  Rows skipped:     {result.rows_skipped:,}")
    print(f"  Date range:       {result.date_range_start} to {result.date_range_end}")
    print(f"  Unique creatives: {result.creative_ids_found:,}")
    print(f"  Unique sizes:     {len(result.sizes_found)}")
    print(f"  Countries:        {len(result.countries_found)}")
    print(f"  Billing IDs:      {', '.join(result.billing_ids_found[:5])}")
    print(f"  Total reached:    {result.total_reached_queries:,}")
    print(f"  Total impressions:{result.total_impressions:,}")
    print(f"  Total spend:      ${result.total_spend_usd:,.2f}")
    
    if result.errors:
        print(f"\n  Errors ({len(result.errors)}):")
        for err in result.errors[:5]:
            print(f"    - {err}")
```

---

## Part 3: Update QPS Analyzers

Update each analyzer to query `performance_data` instead of `size_metrics_daily`.

**File: `qps/size_analyzer.py`** - Update the `get_traffic_sizes` method:

```python
def get_traffic_sizes(self, days: int = 7) -> Dict[str, Dict]:
    """
    Get sizes from imported traffic data (performance_data table).
    Aggregates at query time, not import time.
    """
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    sizes: Dict[str, Dict] = {}
    
    try:
        cursor.execute("""
            SELECT 
                creative_size,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                SUM(spend_micros) as total_spend
            FROM performance_data
            WHERE metric_date >= ?
              AND creative_size IS NOT NULL 
              AND creative_size != ''
            GROUP BY creative_size
            ORDER BY SUM(reached_queries) DESC
        """, (cutoff_date,))
        
        for row in cursor.fetchall():
            size_str = row[0]
            sizes[size_str] = {
                "reached_queries": row[1] or 0,
                "impressions": row[2] or 0,
                "clicks": row[3] or 0,
                "spend_micros": row[4] or 0,
            }
    
    finally:
        conn.close()
    
    return sizes
```

**File: `qps/config_tracker.py`** - Update the `get_config_metrics` method:

```python
def get_config_metrics(self, days: int = 7) -> Dict[str, Dict]:
    """
    Get aggregated metrics by billing_id from performance_data.
    """
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    metrics: Dict[str, Dict] = {}
    
    try:
        cursor.execute("""
            SELECT 
                billing_id,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                SUM(spend_micros) as total_spend_micros
            FROM performance_data
            WHERE metric_date >= ?
              AND billing_id IS NOT NULL
            GROUP BY billing_id
        """, (cutoff_date,))
        
        for row in cursor.fetchall():
            billing_id = str(row[0])
            metrics[billing_id] = {
                "reached_queries": row[1] or 0,
                "impressions": row[2] or 0,
                "clicks": row[3] or 0,
                "spend_micros": row[4] or 0,
            }
    
    finally:
        conn.close()
    
    return metrics
```

**File: `qps/fraud_detector.py`** - Update queries similarly to use `performance_data`.

---

## Part 4: Update qps/__init__.py

```python
"""QPS Optimization Module for RTBcat.

Unified data storage with analysis at query time.

Example:
    >>> from qps import import_bigquery_csv, SizeCoverageAnalyzer
    >>> 
    >>> result = import_bigquery_csv("/path/to/export.csv")
    >>> print(f"Imported {result.rows_imported} rows")
    >>> 
    >>> analyzer = SizeCoverageAnalyzer()
    >>> print(analyzer.generate_report(days=7))
"""

from qps.importer import import_bigquery_csv, get_data_summary, get_import_summary, ImportResult
from qps.size_analyzer import SizeCoverageAnalyzer, CoverageReport
from qps.config_tracker import ConfigPerformanceTracker, ConfigReport
from qps.fraud_detector import FraudSignalDetector, FraudReport
from qps.models import (
    CreativeSizeInfo,
    SizeCoverageResult,
    ConfigPerformance,
    FraudSignal,
)
from qps.constants import (
    GOOGLE_AVAILABLE_SIZES,
    PRETARGETING_CONFIGS,
    ENDPOINTS,
    TOTAL_ENDPOINT_QPS,
    ACCOUNT_ID,
    ACCOUNT_NAME,
)

__all__ = [
    # Importer
    "import_bigquery_csv",
    "get_data_summary",
    "get_import_summary",
    "ImportResult",
    # Analyzers
    "SizeCoverageAnalyzer",
    "CoverageReport",
    "ConfigPerformanceTracker",
    "ConfigReport",
    "FraudSignalDetector",
    "FraudReport",
    # Models
    "CreativeSizeInfo", 
    "SizeCoverageResult",
    "ConfigPerformance",
    "FraudSignal",
    # Constants
    "GOOGLE_AVAILABLE_SIZES",
    "PRETARGETING_CONFIGS",
    "ENDPOINTS",
    "TOTAL_ENDPOINT_QPS",
    "ACCOUNT_ID",
    "ACCOUNT_NAME",
]
```

---

## Part 5: Simplify Dashboard Import Page

**File: `dashboard/src/app/import/page.tsx`** - Simplify to single import option

The dashboard import page should be simplified to:
1. Remove "General" vs "Video" distinction
2. Single drag-and-drop zone for BigQuery CSV
3. Use the unified importer endpoint
4. Show clear progress and results

Key changes:
- Remove tab selection between import types
- Single file upload component
- Clear instructions: "Upload your BigQuery CSV export"
- Show what will be imported (dates, rows, sizes, etc.)

---

## Part 6: Clean Up Old Files

### Files to DELETE:

```bash
# Old performance repository (replaced by unified importer)
rm -f creative-intelligence/storage/performance_repository.py

# Old migration (will be replaced)
rm -f creative-intelligence/storage/migrations/002_qps_tables.sql

# Old waste analyzer (if exists and unused)
# rm -f creative-intelligence/analytics/waste_analyzer.py
# rm -f creative-intelligence/analytics/waste_models.py

# Old QPS report files
rm -f creative-intelligence/qps_report.txt
rm -f creative-intelligence/size_coverage.txt
rm -f creative-intelligence/config_performance.txt
rm -f creative-intelligence/fraud_signals.txt
```

### Files to UPDATE:

- `api/main.py` - Remove old `/performance/import-csv` endpoint, use unified importer
- `storage/__init__.py` - Update exports
- `analytics/__init__.py` - Remove waste analyzer references if unused

---

## Part 7: Database Reset Script

**File: `scripts/reset_performance_data.py`**

```python
#!/usr/bin/env python3
"""Reset performance data tables for clean start."""

import sqlite3
import os
from pathlib import Path

DB_PATH = os.path.expanduser("~/.rtbcat/rtbcat.db")

def reset_tables():
    """Drop and recreate performance data tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Dropping old tables...")
    cursor.executescript("""
        DROP TABLE IF EXISTS size_metrics_daily;
        DROP TABLE IF EXISTS performance_metrics;
        DROP TABLE IF EXISTS fraud_signals;
    """)
    
    print("Creating new performance_data table...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS performance_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date DATE NOT NULL,
            creative_id TEXT NOT NULL,
            billing_id TEXT NOT NULL,
            creative_size TEXT,
            creative_format TEXT,
            country TEXT,
            platform TEXT,
            environment TEXT,
            app_id TEXT,
            app_name TEXT,
            publisher_id TEXT,
            publisher_name TEXT,
            publisher_domain TEXT,
            reached_queries INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            spend_micros INTEGER DEFAULT 0,
            video_starts INTEGER DEFAULT 0,
            video_first_quartile INTEGER DEFAULT 0,
            video_midpoint INTEGER DEFAULT 0,
            video_third_quartile INTEGER DEFAULT 0,
            video_completions INTEGER DEFAULT 0,
            vast_errors INTEGER DEFAULT 0,
            active_view_measurable INTEGER DEFAULT 0,
            active_view_viewable INTEGER DEFAULT 0,
            deal_id TEXT,
            deal_name TEXT,
            transaction_type TEXT,
            advertiser TEXT,
            buyer_account_id TEXT,
            buyer_account_name TEXT,
            gma_sdk INTEGER DEFAULT 0,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            import_batch_id TEXT,
            UNIQUE(metric_date, creative_id, billing_id, country, app_id, deal_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_data(metric_date);
        CREATE INDEX IF NOT EXISTS idx_perf_creative ON performance_data(creative_id);
        CREATE INDEX IF NOT EXISTS idx_perf_billing ON performance_data(billing_id);
        CREATE INDEX IF NOT EXISTS idx_perf_size ON performance_data(creative_size);
        CREATE INDEX IF NOT EXISTS idx_perf_country ON performance_data(country);
        CREATE INDEX IF NOT EXISTS idx_perf_app ON performance_data(app_id);
        
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
    """)
    
    conn.commit()
    conn.close()
    
    print("Done! Tables reset.")
    print("\nNext: Import your BigQuery CSV:")
    print("  python cli/qps_analyzer.py import /path/to/bigquery.csv")

if __name__ == "__main__":
    confirm = input("This will DELETE all performance data. Continue? (yes/no): ")
    if confirm.lower() == "yes":
        reset_tables()
    else:
        print("Cancelled.")
```

---

## Testing

```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate

# Reset database tables
python scripts/reset_performance_data.py

# Import CSV
python cli/qps_analyzer.py import /path/to/bigquery.csv

# Verify data
python cli/qps_analyzer.py summary

# Generate reports
python cli/qps_analyzer.py coverage --days 7
python cli/qps_analyzer.py full-report --days 7
```

---

## Success Criteria

- [ ] Old tables dropped (`size_metrics_daily`, `performance_metrics`)
- [ ] New `performance_data` table created with all CSV columns
- [ ] Unified importer stores raw data (no aggregation)
- [ ] QPS analyzers updated to query `performance_data`
- [ ] CLI works with new table
- [ ] Dashboard import simplified (single option)
- [ ] Old files cleaned up

---

## After Completing

Tell Jen:

```
Clean Slate - Unified Performance Data complete!

Changes:
1. Dropped old tables (size_metrics_daily, performance_metrics)
2. Created new performance_data table with ALL CSV columns
3. Updated importer to store raw data (no aggregation)
4. Updated all QPS analyzers to query performance_data
5. Simplified dashboard import page

To reset and re-import:
  python scripts/reset_performance_data.py
  python cli/qps_analyzer.py import /path/to/bigquery.csv

Architecture is now:
  BigQuery CSV → performance_data (raw rows) → Analysis at query time

Single source of truth, professional quality, ready for distribution.
```

---

**Priority:** HIGH
**Estimated time:** 1-2 hours
**Risk:** Medium (deletes data - backup database first!)
