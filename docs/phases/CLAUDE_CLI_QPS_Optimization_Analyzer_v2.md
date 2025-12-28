# Claude CLI Prompt: QPS Optimization Analyzer v2

## Context

RTBcat needs a **QPS Optimization Analyzer** - the core analytical module that:
1. Ingests daily CSV performance data from Google Authorized Buyers
2. Maps your creative inventory to market sizes (coverage analysis)
3. Calculates what an INCLUDE list would look like and its impact
4. Flags suspicious fraud patterns for human review (not definitive detection)
5. Generates human-readable recommendations for AdOps to implement manually

**Key Corrections from v1:**
- Size filtering is INCLUDE-only. Once you add one size, all others are excluded.
- We generate recommended INCLUDE lists, not exclude lists.
- Most traffic that doesn't convert is "cost of business" not waste.
- Only size mismatch (QPS for sizes you can't serve) is true waste.
- Fraud detection is limited - VPNs are prevalent, smart fraud mixes real/fake.

**Philosophy:** This is a sensitive operation affecting live bidding. Default output is always a "printout" for human review. API implementation is opt-in only.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     QPS FLOW (Constraint Hierarchy)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LEVEL 1: ENDPOINTS (Hard Limit = 90K QPS total)                           │
│  ├── US West:  10,000 QPS  (bidder.novabeyond.com)                         │
│  ├── Asia:     30,000 QPS  (bidder-sg.novabeyond.com)                      │
│  └── US East:  50,000 QPS  (bidder-us.novabeyond.com)                      │
│                                                                             │
│  LEVEL 2: PRETARGETING (10 configs, 375K "virtual" QPS)                    │
│  └── Competes for endpoint capacity above                                  │
│  └── Size filtering: INCLUDE-only (add one = exclude all others)           │
│                                                                             │
│  LEVEL 3: BIDDER LOGIC (what you actually bid on)                          │
│  └── Depends on having matching creatives for the size                     │
│                                                                             │
│  TRUE WASTE = Reached queries for sizes you have no creatives for          │
│  NOT WASTE = Impressions without clicks (normal funnel behavior)           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pretargeting Logic (Critical!)

```
PRETARGETING SETTINGS LOGIC:
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  All settings use AND logic with each other:                               │
│                                                                             │
│  (Geo = India OR Philippines)                                              │
│    AND (Platform = Phone OR Tablet)                                        │
│    AND (Size = 300x250 OR 320x50)   ← Sizes are OR within the list        │
│    AND (Environment = Web OR App)   ← Web/App are OR with each other      │
│                                                                             │
│  SIZE FILTERING:                                                            │
│  ├── Leave blank = Accept ALL sizes (including odd ones you can't serve)  │
│  ├── Add ONE size = ONLY that size (all others excluded)                   │
│  └── Add MULTIPLE sizes = Those sizes accepted (OR within the list)        │
│                                                                             │
│  ⚠️ There is NO "exclude" option - it's INCLUDE-only                       │
│  ⚠️ This is powerful but DANGEROUS - mistakes block good traffic          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The 10 Pretargeting Configs

```python
PRETARGETING_CONFIGS = {
    "72245759413": {
        "name": "Africa/Asia Mix",
        "display_name": "BF, BR, CI, CM, EG, NG, SA, SE, IN, PH, KZ",
        "geos": ["BF", "BR", "CI", "CM", "EG", "NG", "SA", "SE", "IN", "PH", "KZ"],
        "budget": 1200,
        "qps_limit": 50000
    },
    "83435423204": {
        "name": "ID/BR/IN/US Android",
        "display_name": "ID\\BR \\IN\\US\\KR\\ZA\\AR Android",
        "geos": ["ID", "BR", "IN", "US", "KR", "ZA", "AR"],
        "platform": "Android",
        "budget": 2000,
        "qps_limit": 50000
    },
    "104602012074": {
        "name": "SA/UAE/EGY iOS&AND",
        "display_name": "SA,UAE, EGY, PH,IT,ES,BF\\KZ\\FR\\PE\\ZA\\HU\\SK: iOS&AND",
        "geos": ["SA", "AE", "EG", "PH", "IT", "ES", "BF", "KZ", "FR", "PE", "ZA", "HU", "SK"],
        "budget": 1200,
        "qps_limit": 50000
    },
    "137175951277": {
        "name": "BR/ID/MY/TH/VN Whitelist",
        "display_name": "BR\\iD\\MY\\TH\\VN/ - WL",
        "geos": ["BR", "ID", "MY", "TH", "VN"],
        "budget": 1200,
        "qps_limit": 30000
    },
    "151274651962": {
        "name": "USEast CA/MX Blacklist",
        "display_name": "(USEast) CA, MX, blackList",
        "geos": ["CA", "MX"],
        "budget": 1500,
        "qps_limit": 5000
    },
    "153322387893": {
        "name": "Brazil Android WL",
        "display_name": "BRAZ, Android-919WL",
        "geos": ["BR"],
        "platform": "Android",
        "budget": 1500,
        "qps_limit": 30000
    },
    "155546863666": {
        "name": "Asia BL2003",
        "display_name": "(Asia) ID, IN, TH\\CN\\KR\\TR\\VN\\BD\\PH\\MY\\ \\IE-\\ZA- BL2003",
        "geos": ["ID", "IN", "TH", "CN", "KR", "TR", "VN", "BD", "PH", "MY"],
        "budget": 1800,
        "qps_limit": 50000
    },
    "156494841242": {
        "name": "Nova Whitelist",
        "display_name": "Nova WL",
        "geos": [],
        "budget": 2000,
        "qps_limit": 30000
    },
    "157331516553": {
        "name": "US/PH/AU Global",
        "display_name": "US\\PH\\AU\\KR\\EG\\PK\\BD\\UZ\\SA\\JP\\PE\\ZA\\HU\\SK\\AR\\KW And&iOS",
        "geos": ["US", "PH", "AU", "KR", "EG", "PK", "BD", "UZ", "SA", "JP", "PE", "ZA", "HU", "SK", "AR", "KW"],
        "budget": 3000,
        "qps_limit": 50000
    },
    "158323666240": {
        "name": "BR PH Spotify",
        "display_name": "BR PH com.spotify.music",
        "geos": ["BR", "PH"],
        "apps": ["com.spotify.music"],
        "budget": 2000,
        "qps_limit": 30000
    }
}

ENDPOINTS = {
    "us_west": {"url": "bidder.novabeyond.com", "qps": 10000, "location": "US West"},
    "asia": {"url": "bidder-sg.novabeyond.com", "qps": 30000, "location": "Asia"},
    "us_east": {"url": "bidder-us.novabeyond.com", "qps": 50000, "location": "US East"}
}

# Google's available sizes for pretargeting (98 sizes)
GOOGLE_AVAILABLE_SIZES = [
    "468x60", "728x90", "250x250", "200x200", "336x280", "300x250", "120x600",
    "160x600", "320x50", "300x50", "425x600", "300x600", "970x90", "240x400",
    "980x120", "930x180", "250x360", "580x400", "300x1050", "480x320", "320x480",
    "768x1024", "1024x768", "480x32", "1024x90", "970x250", "300x100", "750x300",
    "750x200", "750x100", "950x90", "88x31", "220x90", "300x31", "320x100",
    "980x90", "240x133", "200x446", "292x30", "960x90", "970x66", "300x57",
    "120x60", "375x50", "414x736", "736x414", "320x400", "600x314", "400x400",
    "480x800", "500x500", "500x720", "600x500", "672x560", "1160x800", "600x100",
    "640x100", "640x200", "240x1200", "320x1200", "600x1200", "600x2100", "936x120",
    "1456x180", "1860x360", "1940x180", "1940x500", "1960x240", "850x1200",
    "960x640", "640x960", "1536x2048", "2048x1536", "960x64", "2048x180", "600x200",
    "1500x600", "1500x400", "1500x200", "1900x180", "176x62", "440x180", "600x62",
    "1960x180", "480x266", "400x892", "584x60", "1920x180", "1940x132", "600x114",
    "240x120", "828x1472", "1472x828", "640x800", "800x800", "960x1600", "1000x1000",
    "1000x1440", "1200x1000", "1344x1120", "2320x1600", "1200x200", "1280x200",
    "1280x400", "480x2400", "640x2400", "1200x2400", "1200x4200", "1872x240",
    "2912x360", "3720x720", "3880x360", "3880x1000", "3920x480"
]
```

---

## Your Task: Build the QPS Optimization Analyzer

### Part 1: Database Schema Extension

Add these tables to the existing RTBcat database (`~/.rtbcat/rtbcat.db`):

```sql
-- Pretargeting configurations (sync from API + manual metadata)
CREATE TABLE IF NOT EXISTS pretargeting_configs (
    id INTEGER PRIMARY KEY,
    billing_id TEXT UNIQUE NOT NULL,
    name TEXT,
    display_name TEXT,
    geos TEXT,  -- JSON array
    platforms TEXT,  -- JSON array or NULL for all
    apps TEXT,  -- JSON array for app-specific configs
    budget_daily REAL,
    qps_limit INTEGER,
    current_size_filter TEXT,  -- JSON array of included sizes, NULL = all
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Endpoint configurations
CREATE TABLE IF NOT EXISTS endpoints (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    url TEXT NOT NULL,
    qps_limit INTEGER NOT NULL,
    location TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1
);

-- Daily aggregated metrics by size (from CSV imports)
CREATE TABLE IF NOT EXISTS size_metrics_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,
    billing_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    country TEXT,
    platform TEXT,
    environment TEXT,  -- App or Web
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros INTEGER DEFAULT 0,
    video_starts INTEGER DEFAULT 0,
    video_completions INTEGER DEFAULT 0,
    vast_errors INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_date, billing_id, creative_size, country, platform, environment)
);

-- Creative size coverage (maps your creatives to sizes)
CREATE TABLE IF NOT EXISTS creative_size_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_size TEXT UNIQUE NOT NULL,
    creative_count INTEGER DEFAULT 0,  -- How many of your creatives match this size
    creative_ids TEXT,  -- JSON array of creative IDs
    is_google_standard BOOLEAN DEFAULT 0,  -- Is this in Google's 98-size list?
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Size analysis results
CREATE TABLE IF NOT EXISTS size_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date DATE NOT NULL,
    creative_size TEXT NOT NULL,
    total_reached_7d INTEGER DEFAULT 0,
    total_impressions_7d INTEGER DEFAULT 0,
    you_can_serve BOOLEAN DEFAULT 0,  -- Do you have creatives for this?
    efficiency_pct REAL,
    recommendation TEXT,  -- 'include', 'create_creative', 'ignore'
    priority INTEGER,  -- 1=high, 2=medium, 3=low
    UNIQUE(analysis_date, creative_size)
);

-- Fraud signals (patterns flagged for human review)
CREATE TABLE IF NOT EXISTS fraud_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    app_id TEXT,
    app_name TEXT,
    signal_type TEXT,  -- 'high_ctr', 'clicks_exceed_impressions', 'zero_conversions', etc.
    signal_strength TEXT,  -- 'low', 'medium', 'high'
    evidence TEXT,  -- JSON with supporting data
    days_observed INTEGER,
    status TEXT DEFAULT 'pending',  -- 'pending', 'reviewed', 'blocked', 'cleared'
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    notes TEXT
);

-- Create indices
CREATE INDEX IF NOT EXISTS idx_size_metrics_date ON size_metrics_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_size_metrics_billing ON size_metrics_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_size_metrics_size ON size_metrics_daily(creative_size);
CREATE INDEX IF NOT EXISTS idx_fraud_signals_app ON fraud_signals(app_id);
```

### Part 2: CSV Import Module

**File: `creative-intelligence/importers/bigquery_csv_importer.py`**

```python
#!/usr/bin/env python3
"""
BigQuery CSV Importer for QPS Analysis

Imports daily CSV exports from Google Authorized Buyers BigQuery
and aggregates for QPS optimization analysis.
"""

import csv
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json

DB_PATH = os.path.expanduser("~/.rtbcat/rtbcat.db")

# Column mapping from Google CSV to our schema
COLUMN_MAP = {
    "#Day": "metric_date",
    "Country": "country",
    "Platform": "platform",
    "Creative size": "creative_size",
    "Billing ID": "billing_id",
    "Creative ID": "creative_id",
    "Environment": "environment",
    "Reached queries": "reached_queries",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Spend _buyer currency_": "spend",
    "Video starts": "video_starts",
    "Video completions": "video_completions",
    "VAST error count": "vast_errors",
    "Mobile app name": "app_name",
    "Mobile app ID": "app_id",
}


def parse_date(date_str: str) -> str:
    """Parse date from various formats to YYYY-MM-DD"""
    for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def parse_spend(spend_str: str) -> int:
    """Parse spend to micros (multiply by 1,000,000)"""
    if not spend_str:
        return 0
    cleaned = spend_str.replace("$", "").replace(",", "").strip()
    try:
        return int(float(cleaned) * 1_000_000)
    except ValueError:
        return 0


def import_csv(csv_path: str) -> Dict:
    """
    Import a BigQuery CSV file with aggregation by size/billing_id/country/date.
    
    Returns dict with import statistics.
    """
    stats = {
        "rows_read": 0,
        "rows_imported": 0,
        "sizes_found": set(),
        "billing_ids_found": set(),
        "date_range": {"min": None, "max": None},
        "errors": []
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure tables exist
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS size_metrics_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date DATE NOT NULL,
            billing_id TEXT NOT NULL,
            creative_size TEXT NOT NULL,
            country TEXT,
            platform TEXT,
            environment TEXT,
            reached_queries INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            spend_micros INTEGER DEFAULT 0,
            video_starts INTEGER DEFAULT 0,
            video_completions INTEGER DEFAULT 0,
            vast_errors INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(metric_date, billing_id, creative_size, country, platform, environment)
        );
        CREATE INDEX IF NOT EXISTS idx_size_metrics_date ON size_metrics_daily(metric_date);
        CREATE INDEX IF NOT EXISTS idx_size_metrics_size ON size_metrics_daily(creative_size);
    """)
    
    # Aggregate data before inserting
    aggregated = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats["rows_read"] += 1
            
            metric_date = parse_date(row.get("#Day", ""))
            
            # Track date range
            if stats["date_range"]["min"] is None or metric_date < stats["date_range"]["min"]:
                stats["date_range"]["min"] = metric_date
            if stats["date_range"]["max"] is None or metric_date > stats["date_range"]["max"]:
                stats["date_range"]["max"] = metric_date
            
            key = (
                metric_date,
                row.get("Billing ID", "") or "UNKNOWN",
                row.get("Creative size", "") or "UNKNOWN",
                row.get("Country", "") or "UNKNOWN",
                row.get("Platform", "") or "UNKNOWN",
                row.get("Environment", "") or "UNKNOWN"
            )
            
            if key not in aggregated:
                aggregated[key] = {
                    "reached_queries": 0,
                    "impressions": 0,
                    "clicks": 0,
                    "spend_micros": 0,
                    "video_starts": 0,
                    "video_completions": 0,
                    "vast_errors": 0,
                }
            
            agg = aggregated[key]
            agg["reached_queries"] += int(row.get("Reached queries", 0) or 0)
            agg["impressions"] += int(row.get("Impressions", 0) or 0)
            agg["clicks"] += int(row.get("Clicks", 0) or 0)
            agg["spend_micros"] += parse_spend(row.get("Spend _buyer currency_", "0"))
            agg["video_starts"] += int(row.get("Video starts", 0) or 0)
            agg["video_completions"] += int(row.get("Video completions", 0) or 0)
            agg["vast_errors"] += int(row.get("VAST error count", 0) or 0)
            
            stats["sizes_found"].add(row.get("Creative size", ""))
            stats["billing_ids_found"].add(row.get("Billing ID", ""))
    
    # Insert aggregated data
    for key, metrics in aggregated.items():
        metric_date, billing_id, creative_size, country, platform, environment = key
        
        try:
            cursor.execute("""
                INSERT INTO size_metrics_daily 
                (metric_date, billing_id, creative_size, country, platform, environment,
                 reached_queries, impressions, clicks, spend_micros, 
                 video_starts, video_completions, vast_errors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric_date, billing_id, creative_size, country, platform, environment)
                DO UPDATE SET
                    reached_queries = reached_queries + excluded.reached_queries,
                    impressions = impressions + excluded.impressions,
                    clicks = clicks + excluded.clicks,
                    spend_micros = spend_micros + excluded.spend_micros,
                    video_starts = video_starts + excluded.video_starts,
                    video_completions = video_completions + excluded.video_completions,
                    vast_errors = vast_errors + excluded.vast_errors
            """, (
                metric_date, billing_id, creative_size, country, platform, environment,
                metrics["reached_queries"], metrics["impressions"], metrics["clicks"],
                metrics["spend_micros"], metrics["video_starts"], 
                metrics["video_completions"], metrics["vast_errors"]
            ))
            stats["rows_imported"] += 1
        except Exception as e:
            stats["errors"].append(f"Row {key}: {str(e)}")
    
    conn.commit()
    conn.close()
    
    stats["sizes_found"] = sorted(list(stats["sizes_found"]))
    stats["billing_ids_found"] = sorted(list(stats["billing_ids_found"]))
    
    return stats


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python bigquery_csv_importer.py <csv_file>")
        sys.exit(1)
    
    result = import_csv(sys.argv[1])
    print(f"\n✓ Import complete:")
    print(f"  Rows read:      {result['rows_read']:,}")
    print(f"  Rows imported:  {result['rows_imported']:,}")
    print(f"  Date range:     {result['date_range']['min']} to {result['date_range']['max']}")
    print(f"  Unique sizes:   {len(result['sizes_found'])}")
    print(f"  Billing IDs:    {result['billing_ids_found']}")
    if result['errors']:
        print(f"  Errors:         {len(result['errors'])}")
```

### Part 3: Size Coverage Analyzer

**File: `creative-intelligence/analyzers/size_coverage_analyzer.py`**

```python
#!/usr/bin/env python3
"""
Size Coverage Analyzer

Compares the creative sizes you're receiving (from CSV data) 
against the creatives you have (from API data) to identify:
1. Sizes you CAN serve (have creatives for)
2. Sizes you CANNOT serve (receiving QPS but no creatives)
3. What an INCLUDE list would look like
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
import json

DB_PATH = os.path.expanduser("~/.rtbcat/rtbcat.db")

# Google's available sizes for pretargeting INCLUDE list
GOOGLE_AVAILABLE_SIZES = {
    "468x60", "728x90", "250x250", "200x200", "336x280", "300x250", "120x600",
    "160x600", "320x50", "300x50", "425x600", "300x600", "970x90", "240x400",
    "980x120", "930x180", "250x360", "580x400", "300x1050", "480x320", "320x480",
    "768x1024", "1024x768", "480x32", "1024x90", "970x250", "300x100", "750x300",
    "750x200", "750x100", "950x90", "88x31", "220x90", "300x31", "320x100",
    "980x90", "240x133", "200x446", "292x30", "960x90", "970x66", "300x57",
    "120x60", "375x50", "414x736", "736x414", "320x400", "600x314", "400x400",
    "480x800", "500x500", "500x720", "600x500", "672x560", "1160x800", "600x100",
    "640x100", "640x200", "240x1200", "320x1200", "600x1200", "600x2100", "936x120",
    "1456x180", "1860x360", "1940x180", "1940x500", "1960x240", "850x1200",
    "960x640", "640x960", "1536x2048", "2048x1536", "960x64", "2048x180", "600x200",
    "1500x600", "1500x400", "1500x200", "1900x180", "176x62", "440x180", "600x62",
    "1960x180", "480x266", "400x892", "584x60", "1920x180", "1940x132", "600x114",
    "240x120", "828x1472", "1472x828", "640x800", "800x800", "960x1600", "1000x1000",
    "1000x1440", "1200x1000", "1344x1120", "2320x1600", "1200x200", "1280x200",
    "1280x400", "480x2400", "640x2400", "1200x2400", "1200x4200", "1872x240",
    "2912x360", "3720x720", "3880x360", "3880x1000", "3920x480"
}


@dataclass
class SizeInfo:
    size: str
    reached_queries: int
    impressions: int
    you_can_serve: bool
    creative_count: int
    in_google_list: bool
    efficiency_pct: float
    recommendation: str


def get_your_creative_sizes() -> Dict[str, int]:
    """
    Get sizes from your creative inventory (from creatives table).
    Returns dict of {size: count_of_creatives}
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Try to get sizes from creatives table
    try:
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN width IS NOT NULL AND height IS NOT NULL 
                    THEN width || 'x' || height 
                    ELSE canonical_size 
                END as size,
                COUNT(*) as count
            FROM creatives
            WHERE (width IS NOT NULL AND height IS NOT NULL) OR canonical_size IS NOT NULL
            GROUP BY size
        """)
        
        sizes = {}
        for row in cursor.fetchall():
            if row[0]:
                sizes[row[0]] = row[1]
        
        conn.close()
        return sizes
    except Exception as e:
        conn.close()
        return {}


def get_market_sizes(days: int = 7) -> Dict[str, Dict]:
    """
    Get sizes from CSV data (what you're receiving from the market).
    Returns dict of {size: {reached_queries, impressions}}
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT 
            creative_size,
            SUM(reached_queries) as total_reached,
            SUM(impressions) as total_impressions
        FROM size_metrics_daily
        WHERE metric_date >= ? AND creative_size IS NOT NULL AND creative_size != ''
        GROUP BY creative_size
        ORDER BY SUM(reached_queries) DESC
    """, (cutoff_date,))
    
    sizes = {}
    for row in cursor.fetchall():
        size, reached, impressions = row
        sizes[size] = {
            "reached_queries": reached,
            "impressions": impressions
        }
    
    conn.close()
    return sizes


def analyze_coverage(days: int = 7) -> Tuple[List[SizeInfo], Dict]:
    """
    Analyze size coverage: what you can serve vs. what you're receiving.
    
    Returns:
        - List of SizeInfo objects for each size
        - Summary statistics
    """
    your_sizes = get_your_creative_sizes()
    market_sizes = get_market_sizes(days)
    
    results = []
    
    # Analyze each size in the market
    for size, data in market_sizes.items():
        reached = data["reached_queries"]
        impressions = data["impressions"]
        efficiency = (impressions / reached * 100) if reached > 0 else 0
        
        can_serve = size in your_sizes
        creative_count = your_sizes.get(size, 0)
        in_google_list = size in GOOGLE_AVAILABLE_SIZES
        
        # Determine recommendation
        if can_serve:
            recommendation = "INCLUDE"
        elif in_google_list and reached > 1000:
            recommendation = "CREATE_CREATIVE"  # High volume, worth creating
        elif in_google_list:
            recommendation = "CONSIDER"  # In Google list but low volume
        else:
            recommendation = "IGNORE"  # Not in Google's list, can't filter anyway
        
        results.append(SizeInfo(
            size=size,
            reached_queries=reached,
            impressions=impressions,
            you_can_serve=can_serve,
            creative_count=creative_count,
            in_google_list=in_google_list,
            efficiency_pct=efficiency,
            recommendation=recommendation
        ))
    
    # Sort by reached queries (highest first)
    results.sort(key=lambda x: x.reached_queries, reverse=True)
    
    # Calculate summary
    total_reached = sum(s.reached_queries for s in results)
    servable_reached = sum(s.reached_queries for s in results if s.you_can_serve)
    
    summary = {
        "total_sizes_in_market": len(results),
        "sizes_you_can_serve": len([s for s in results if s.you_can_serve]),
        "sizes_in_google_list": len([s for s in results if s.in_google_list]),
        "total_reached_queries": total_reached,
        "servable_reached_queries": servable_reached,
        "match_rate_pct": (servable_reached / total_reached * 100) if total_reached > 0 else 0,
        "waste_qps": total_reached - servable_reached,
    }
    
    return results, summary


def generate_include_list(days: int = 7) -> List[str]:
    """
    Generate a recommended INCLUDE list for pretargeting.
    Only includes sizes that:
    1. You have creatives for
    2. Are in Google's available list (can actually be filtered)
    """
    your_sizes = get_your_creative_sizes()
    
    include_list = []
    for size in your_sizes.keys():
        if size in GOOGLE_AVAILABLE_SIZES:
            include_list.append(size)
    
    return sorted(include_list)


def generate_report(days: int = 7) -> str:
    """Generate a human-readable size coverage report."""
    results, summary = analyze_coverage(days)
    include_list = generate_include_list(days)
    
    report = []
    report.append("=" * 80)
    report.append("SIZE COVERAGE ANALYSIS REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Analysis Period: Last {days} days")
    report.append("=" * 80)
    
    # Executive Summary
    report.append("")
    report.append("EXECUTIVE SUMMARY")
    report.append("-" * 40)
    report.append(f"Sizes in market (from CSV):        {summary['total_sizes_in_market']}")
    report.append(f"Sizes you can serve (have creatives): {summary['sizes_you_can_serve']}")
    report.append(f"")
    report.append(f"Total Reached Queries:    {summary['total_reached_queries']:>15,}")
    report.append(f"Servable Reached Queries: {summary['servable_reached_queries']:>15,}")
    report.append(f"Waste (can't serve):      {summary['waste_qps']:>15,}")
    report.append(f"Match Rate:               {summary['match_rate_pct']:>14.1f}%")
    report.append("")
    
    if summary['match_rate_pct'] < 80:
        report.append(f"⚠️  {100 - summary['match_rate_pct']:.1f}% of your QPS is for sizes you can't serve!")
    else:
        report.append(f"✓ Good match rate - {summary['match_rate_pct']:.1f}% of QPS is servable")
    
    # Sizes you CAN serve
    report.append("")
    report.append("=" * 80)
    report.append("SIZES YOU CAN SERVE (have creatives)")
    report.append("=" * 80)
    report.append("")
    report.append(f"{'Size':<15} {'Reached':>12} {'Impressions':>12} {'Eff%':>8} {'Creatives':>10}")
    report.append("-" * 60)
    
    for s in results:
        if s.you_can_serve:
            google_marker = "✓" if s.in_google_list else "○"
            report.append(
                f"{google_marker} {s.size:<13} {s.reached_queries:>12,} {s.impressions:>12,} "
                f"{s.efficiency_pct:>7.1f}% {s.creative_count:>10}"
            )
    
    report.append("")
    report.append("✓ = In Google's list (can be filtered)  ○ = Not in Google's list")
    
    # Sizes you CANNOT serve (waste)
    report.append("")
    report.append("=" * 80)
    report.append("SIZES YOU CANNOT SERVE (waste QPS)")
    report.append("=" * 80)
    report.append("")
    report.append(f"{'Size':<15} {'Reached':>12} {'In Google List':>15} {'Recommendation'}")
    report.append("-" * 60)
    
    for s in results:
        if not s.you_can_serve and s.reached_queries > 0:
            google_marker = "Yes" if s.in_google_list else "No"
            report.append(
                f"{s.size:<15} {s.reached_queries:>12,} {google_marker:>15} {s.recommendation}"
            )
    
    # Recommended INCLUDE list
    report.append("")
    report.append("=" * 80)
    report.append("RECOMMENDED INCLUDE LIST FOR PRETARGETING")
    report.append("=" * 80)
    report.append("")
    
    if include_list:
        report.append("If you set pretargeting to INCLUDE only these sizes,")
        report.append("you will eliminate waste from sizes you can't serve.")
        report.append("")
        report.append("⚠️  WARNING: Once you add ANY size, all unlisted sizes are EXCLUDED!")
        report.append("⚠️  Double-check this list carefully before applying!")
        report.append("")
        report.append("SIZES TO INCLUDE:")
        report.append("")
        
        # Format as comma-separated for easy copy-paste
        for i in range(0, len(include_list), 5):
            chunk = include_list[i:i+5]
            report.append("  " + ", ".join(chunk))
        
        report.append("")
        report.append("TO IMPLEMENT:")
        report.append("  1. Go to Authorized Buyers UI")
        report.append("  2. Navigate to Bidder Settings → Pretargeting")
        report.append("  3. Edit the config you want to modify")
        report.append("  4. Under 'Creative dimensions', add the sizes above")
        report.append("  5. Click Save")
        report.append("  6. Monitor traffic for 24-48 hours after applying")
    else:
        report.append("No sizes found to include. Check that creatives are imported.")
    
    # Opportunities
    report.append("")
    report.append("=" * 80)
    report.append("OPPORTUNITIES: High-volume sizes worth creating creatives for")
    report.append("=" * 80)
    report.append("")
    
    opportunities = [s for s in results 
                     if not s.you_can_serve 
                     and s.in_google_list 
                     and s.reached_queries > 1000]
    
    if opportunities:
        report.append(f"{'Size':<15} {'Daily QPS':>12} {'Priority'}")
        report.append("-" * 40)
        for s in opportunities[:10]:
            priority = "HIGH" if s.reached_queries > 10000 else "MEDIUM"
            report.append(f"{s.size:<15} {s.reached_queries:>12,} {priority}")
        report.append("")
        report.append("ACTION: Brief creative team to produce these sizes")
    else:
        report.append("No high-volume opportunities found.")
    
    report.append("")
    report.append("=" * 80)
    report.append("END OF REPORT")
    report.append("=" * 80)
    
    return "\n".join(report)


if __name__ == "__main__":
    import sys
    
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        days = int(sys.argv[idx + 1])
    
    print(generate_report(days))
```

### Part 4: Fraud Signal Detector

**File: `creative-intelligence/analyzers/fraud_signal_detector.py`**

```python
#!/usr/bin/env python3
"""
Fraud Signal Detector

Flags suspicious patterns for human review. Does NOT definitively identify fraud.

Important limitations:
- VPNs make geographic analysis unreliable
- Smart fraudsters mix 70-80% real traffic with 20-30% fake
- Pure fraud gets caught by Google's systems
- We can only detect patterns over time
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List
from dataclasses import dataclass
import json

DB_PATH = os.path.expanduser("~/.rtbcat/rtbcat.db")


@dataclass
class FraudSignal:
    app_id: str
    app_name: str
    signal_type: str
    signal_strength: str  # 'low', 'medium', 'high'
    evidence: Dict
    days_observed: int
    recommendation: str


def detect_high_ctr_apps(days: int = 7, ctr_threshold: float = 3.0) -> List[FraudSignal]:
    """
    Detect apps with abnormally high CTR.
    
    Note: High CTR alone is not proof of fraud. Could be:
    - Very engaging content
    - Well-targeted audience
    - Or yes, click fraud
    
    Flags for human review, not automatic blocking.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # This query would need app data in the CSV - adjust based on actual schema
    cursor.execute("""
        SELECT 
            creative_size as app_proxy,  -- Placeholder, need actual app field
            SUM(impressions) as total_impressions,
            SUM(clicks) as total_clicks,
            COUNT(DISTINCT metric_date) as days_active
        FROM size_metrics_daily
        WHERE metric_date >= ?
        GROUP BY app_proxy
        HAVING SUM(impressions) > 100 AND SUM(clicks) > 0
    """, (cutoff_date,))
    
    signals = []
    for row in cursor.fetchall():
        app_id, impressions, clicks, days_active = row
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        
        if ctr > ctr_threshold:
            strength = "high" if ctr > 5.0 else "medium"
            signals.append(FraudSignal(
                app_id=app_id,
                app_name=app_id,  # Would need lookup
                signal_type="high_ctr",
                signal_strength=strength,
                evidence={
                    "ctr": ctr,
                    "impressions": impressions,
                    "clicks": clicks,
                    "expected_ctr": 0.5  # Typical baseline
                },
                days_observed=days_active,
                recommendation=f"Review - CTR {ctr:.1f}% is {ctr/0.5:.0f}x average"
            ))
    
    conn.close()
    return signals


def detect_clicks_exceed_impressions(days: int = 7) -> List[FraudSignal]:
    """
    Detect cases where clicks > impressions.
    
    Note: This can be legitimate (timing across midnight) or fraud.
    Single occurrences are usually timing. Repeated patterns are suspicious.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT 
            billing_id,
            creative_size,
            COUNT(*) as occurrences,
            SUM(CASE WHEN clicks > impressions THEN 1 ELSE 0 END) as violations
        FROM size_metrics_daily
        WHERE metric_date >= ? AND impressions > 0
        GROUP BY billing_id, creative_size
        HAVING SUM(CASE WHEN clicks > impressions THEN 1 ELSE 0 END) > 1
    """, (cutoff_date,))
    
    signals = []
    for row in cursor.fetchall():
        billing_id, size, occurrences, violations = row
        
        if violations >= 2:  # At least 2 days of violations
            strength = "high" if violations >= 4 else "medium" if violations >= 2 else "low"
            signals.append(FraudSignal(
                app_id=f"{billing_id}_{size}",
                app_name=f"Config {billing_id}, Size {size}",
                signal_type="clicks_exceed_impressions",
                signal_strength=strength,
                evidence={
                    "days_with_issue": violations,
                    "total_days": occurrences
                },
                days_observed=occurrences,
                recommendation=f"Investigate - clicks > impressions on {violations} of {occurrences} days"
            ))
    
    conn.close()
    return signals


def generate_fraud_report(days: int = 7) -> str:
    """Generate human-readable fraud signals report."""
    
    report = []
    report.append("=" * 80)
    report.append("FRAUD SIGNALS REPORT (Patterns for Human Review)")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Analysis Period: Last {days} days")
    report.append("=" * 80)
    report.append("")
    report.append("⚠️  IMPORTANT DISCLAIMER:")
    report.append("These are PATTERNS that may indicate fraud, not proof of fraud.")
    report.append("Smart fraudsters mix 70-80% real traffic with 20-30% fake.")
    report.append("VPNs make geographic analysis unreliable.")
    report.append("All signals require human review before action.")
    report.append("")
    
    # High CTR signals
    high_ctr = detect_high_ctr_apps(days)
    report.append("-" * 80)
    report.append("HIGH CTR PATTERNS")
    report.append("-" * 80)
    
    if high_ctr:
        for signal in high_ctr[:10]:
            report.append(f"\n{signal.app_name}")
            report.append(f"  Signal: {signal.signal_type}")
            report.append(f"  Strength: {signal.signal_strength.upper()}")
            report.append(f"  CTR: {signal.evidence['ctr']:.2f}% (expected ~0.5%)")
            report.append(f"  Impressions: {signal.evidence['impressions']:,}")
            report.append(f"  Clicks: {signal.evidence['clicks']:,}")
            report.append(f"  Recommendation: {signal.recommendation}")
    else:
        report.append("No high CTR patterns detected.")
    
    # Clicks > Impressions
    clicks_exceed = detect_clicks_exceed_impressions(days)
    report.append("")
    report.append("-" * 80)
    report.append("CLICKS EXCEED IMPRESSIONS PATTERNS")
    report.append("-" * 80)
    
    if clicks_exceed:
        for signal in clicks_exceed[:10]:
            report.append(f"\n{signal.app_name}")
            report.append(f"  Signal: {signal.signal_type}")
            report.append(f"  Strength: {signal.signal_strength.upper()}")
            report.append(f"  Days with issue: {signal.evidence['days_with_issue']}")
            report.append(f"  Recommendation: {signal.recommendation}")
    else:
        report.append("No clicks > impressions patterns detected.")
    
    report.append("")
    report.append("=" * 80)
    report.append("NEXT STEPS")
    report.append("=" * 80)
    report.append("")
    report.append("1. Review each signal with domain knowledge")
    report.append("2. Check historical patterns for the flagged apps")
    report.append("3. Compare with conversion data (not available in this report)")
    report.append("4. Consider blocking only after thorough investigation")
    report.append("5. Some 'suspicious' patterns are legitimate - don't over-block")
    report.append("")
    
    return "\n".join(report)


if __name__ == "__main__":
    import sys
    
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        days = int(sys.argv[idx + 1])
    
    print(generate_fraud_report(days))
```

### Part 5: Main CLI

**File: `creative-intelligence/cli/qps_analyzer.py`**

```python
#!/usr/bin/env python3
"""
RTBcat QPS Optimization Analyzer CLI

Usage:
    python qps_analyzer.py import <csv_file>       Import BigQuery CSV
    python qps_analyzer.py coverage [--days N]     Size coverage analysis
    python qps_analyzer.py include-list            Generate recommended INCLUDE list
    python qps_analyzer.py fraud [--days N]        Fraud signal detection
    python qps_analyzer.py full-report [--days N]  Complete analysis report
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_help():
    print(__doc__)
    print("\nExamples:")
    print("  python qps_analyzer.py import ~/downloads/bigquery_export.csv")
    print("  python qps_analyzer.py coverage --days 7")
    print("  python qps_analyzer.py include-list")
    print("  python qps_analyzer.py fraud --days 14")
    print("  python qps_analyzer.py full-report --days 7")


def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Get days parameter
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])
    
    if command == "import":
        if len(sys.argv) < 3:
            print("Usage: python qps_analyzer.py import <csv_file>")
            sys.exit(1)
        
        from importers.bigquery_csv_importer import import_csv
        csv_path = sys.argv[2]
        print(f"Importing {csv_path}...")
        result = import_csv(csv_path)
        print(f"\n✓ Import complete:")
        print(f"  Rows read:      {result['rows_read']:,}")
        print(f"  Rows imported:  {result['rows_imported']:,}")
        print(f"  Date range:     {result['date_range']['min']} to {result['date_range']['max']}")
        print(f"  Unique sizes:   {len(result['sizes_found'])}")
        print(f"  Billing IDs:    {result['billing_ids_found']}")
    
    elif command == "coverage":
        from analyzers.size_coverage_analyzer import generate_report
        print(generate_report(days))
    
    elif command == "include-list":
        from analyzers.size_coverage_analyzer import generate_include_list, get_your_creative_sizes
        
        your_sizes = get_your_creative_sizes()
        include_list = generate_include_list()
        
        print("=" * 60)
        print("RECOMMENDED INCLUDE LIST FOR PRETARGETING")
        print("=" * 60)
        print("")
        print(f"Your creatives span {len(your_sizes)} unique sizes.")
        print(f"Of these, {len(include_list)} can be filtered in pretargeting.")
        print("")
        print("⚠️  WARNING: Adding these will EXCLUDE all other sizes!")
        print("")
        print("SIZES TO INCLUDE:")
        for size in include_list:
            count = your_sizes.get(size, 0)
            print(f"  {size:<15} ({count} creatives)")
        print("")
        print("Copy these to: Bidder Settings → Pretargeting → Creative dimensions")
    
    elif command == "fraud":
        from analyzers.fraud_signal_detector import generate_fraud_report
        print(generate_fraud_report(days))
    
    elif command == "full-report":
        from analyzers.size_coverage_analyzer import generate_report as coverage_report
        from analyzers.fraud_signal_detector import generate_fraud_report
        
        print(coverage_report(days))
        print("\n\n")
        print(generate_fraud_report(days))
    
    elif command in ["help", "-h", "--help"]:
        print_help()
    
    else:
        print(f"Unknown command: {command}")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## Success Criteria

After implementing this prompt:

- [ ] Database schema extended with size coverage and fraud signal tables
- [ ] CSV importer handles BigQuery format correctly
- [ ] Size coverage analyzer maps your creatives to market sizes
- [ ] INCLUDE list generator produces a safe list for pretargeting
- [ ] Fraud detector flags patterns without claiming definitive fraud
- [ ] All reports are human-readable "printouts" for AdOps review
- [ ] No automatic changes to pretargeting - all manual implementation

---

## Example Output

```
================================================================================
SIZE COVERAGE ANALYSIS REPORT
================================================================================

EXECUTIVE SUMMARY
----------------------------------------
Sizes in market (from CSV):           22
Sizes you can serve (have creatives): 8

Total Reached Queries:         127,134
Servable Reached Queries:       94,851
Waste (can't serve):            32,283
Match Rate:                      74.6%

⚠️  25.4% of your QPS is for sizes you can't serve!

================================================================================
SIZES YOU CAN SERVE (have creatives)
================================================================================

✓ 300x250        107,663       80,062    74.4%        127
✓ 320x50          15,234       11,425    75.0%         89
...

================================================================================
RECOMMENDED INCLUDE LIST FOR PRETARGETING
================================================================================

⚠️  WARNING: Once you add ANY size, all unlisted sizes are EXCLUDED!

SIZES TO INCLUDE:
  300x250, 320x50, 728x90, 160x600, 300x600
  320x100, 336x280, ...

TO IMPLEMENT:
  1. Go to Authorized Buyers UI
  2. Navigate to Bidder Settings → Pretargeting
  3. Edit the config you want to modify
  4. Under 'Creative dimensions', add the sizes above
  5. Click Save
  6. Monitor traffic for 24-48 hours after applying
```

---

## DO NOT

- ❌ Automatically apply changes to pretargeting configs
- ❌ Claim definitive fraud detection (only flag patterns)
- ❌ Assume geographic anomalies indicate fraud (VPNs)
- ❌ Delete or modify existing data without confirmation
- ❌ Store sensitive credentials in code

---

## After Completing

Tell Jen:
```
QPS Optimization Analyzer v2 implemented! Here's what was created:

Files:
  creative-intelligence/importers/bigquery_csv_importer.py
  creative-intelligence/analyzers/size_coverage_analyzer.py
  creative-intelligence/analyzers/fraud_signal_detector.py
  creative-intelligence/cli/qps_analyzer.py

Usage:
  1. Import CSV:    python cli/qps_analyzer.py import /path/to/bigquery.csv
  2. Coverage:      python cli/qps_analyzer.py coverage
  3. Include list:  python cli/qps_analyzer.py include-list
  4. Fraud signals: python cli/qps_analyzer.py fraud
  5. Full report:   python cli/qps_analyzer.py full-report

Key corrections in v2:
  - Size filtering is INCLUDE-only (not exclude)
  - Adding one size excludes all others
  - Fraud detection is limited - only flags for review
  - Non-converting traffic is "cost of business" not waste

All outputs are "printouts" for human review. No automatic changes.
```

---

**Priority:** HIGH - Core analytical engine
**Estimated time:** 2-3 hours
**Risk:** Low (read-only analysis, no auto-apply)
