# Claude CLI Prompt: QPS Waste Analyzer - Core Engine

## Context

RTBcat needs a **QPS Waste Analyzer** - the core analytical module that:
1. Ingests daily CSV performance data from Google Authorized Buyers
2. Analyzes where QPS is being wasted (sizes, geos, apps that can't be served)
3. Generates human-readable recommendations for AdOps to implement manually
4. Optionally allows API-based implementation after human review

**Philosophy:** This is a sensitive operation affecting live bidding. Default output is always a "printout" for human review. API implementation is opt-in only.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     QPS FLOW (Constraint Hierarchy)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  LEVEL 1: ENDPOINTS (Hard Limit = 90K QPS total)                       │
│  ├── US West:  10,000 QPS  (bidder.novabeyond.com)                     │
│  ├── Asia:     30,000 QPS  (bidder-sg.novabeyond.com)                  │
│  └── US East:  50,000 QPS  (bidder-us.novabeyond.com)                  │
│                                                                         │
│  LEVEL 2: PRETARGETING (10 configs, 375K "virtual" QPS)                │
│  └── Competes for endpoint capacity above                              │
│                                                                         │
│  LEVEL 3: BIDDER LOGIC (what you actually bid on)                      │
│  └── Depends on having matching creatives                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
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
        "qps_limit": 50000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "83435423204": {
        "name": "ID/BR/IN/US Android",
        "display_name": "ID\\BR \\IN\\US\\KR\\ZA\\AR Android",
        "geos": ["ID", "BR", "IN", "US", "KR", "ZA", "AR"],
        "platform": "Android",
        "budget": 2000,
        "qps_limit": 50000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "104602012074": {
        "name": "SA/UAE/EGY iOS&AND",
        "display_name": "SA,UAE, EGY, PH,IT,ES,BF\\KZ\\FR\\PE\\ZA\\HU\\SK: iOS&AND",
        "geos": ["SA", "AE", "EG", "PH", "IT", "ES", "BF", "KZ", "FR", "PE", "ZA", "HU", "SK"],
        "budget": 1200,
        "qps_limit": 50000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "137175951277": {
        "name": "BR/ID/MY/TH/VN Whitelist",
        "display_name": "BR\\iD\\MY\\TH\\VN/ - WL",
        "geos": ["BR", "ID", "MY", "TH", "VN"],
        "budget": 1200,
        "qps_limit": 30000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "151274651962": {
        "name": "USEast CA/MX Blacklist",
        "display_name": "(USEast) CA, MX, blackList",
        "geos": ["CA", "MX"],
        "budget": 1500,
        "qps_limit": 5000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "153322387893": {
        "name": "Brazil Android WL",
        "display_name": "BRAZ, Android-919WL",
        "geos": ["BR"],
        "platform": "Android",
        "budget": 1500,
        "qps_limit": 30000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "155546863666": {
        "name": "Asia BL2003",
        "display_name": "(Asia) ID, IN, TH\\CN\\KR\\TR\\VN\\BD\\PH\\MY\\ \\IE-\\ZA- BL2003",
        "geos": ["ID", "IN", "TH", "CN", "KR", "TR", "VN", "BD", "PH", "MY"],
        "budget": 1800,
        "qps_limit": 50000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "156494841242": {
        "name": "Nova Whitelist",
        "display_name": "Nova WL",
        "geos": [],  # Unknown - needs investigation
        "budget": 2000,
        "qps_limit": 30000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "157331516553": {
        "name": "US/PH/AU Global",
        "display_name": "US\\PH\\AU\\KR\\EG\\PK\\BD\\UZ\\SA\\JP\\PE\\ZA\\HU\\SK\\AR\\KW And&iOS",
        "geos": ["US", "PH", "AU", "KR", "EG", "PK", "BD", "UZ", "SA", "JP", "PE", "ZA", "HU", "SK", "AR", "KW"],
        "budget": 3000,
        "qps_limit": 50000,
        "formats": ["Banner", "Audio and video", "Native"]
    },
    "158323666240": {
        "name": "BR PH Spotify",
        "display_name": "BR PH com.spotify.music",
        "geos": ["BR", "PH"],
        "apps": ["com.spotify.music"],
        "budget": 2000,
        "qps_limit": 30000,
        "formats": ["Banner", "Audio and video", "Native"]
    }
}

ENDPOINTS = {
    "us_west": {
        "url": "https://bidder.novabeyond.com/dsp/doubleclick/bidding.do",
        "qps": 10000,
        "location": "US West"
    },
    "asia": {
        "url": "https://bidder-sg.novabeyond.com/dsp/doubleclick/bidding.do",
        "qps": 30000,
        "location": "Asia"
    },
    "us_east": {
        "url": "https://bidder-us.novabeyond.com/dsp/doubleclick/bidding.do",
        "qps": 50000,
        "location": "US East"
    }
}
```

---

## Your Task: Build the QPS Waste Analyzer

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
    formats TEXT,  -- JSON array
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

-- Size coverage analysis (your creatives vs. market sizes)
CREATE TABLE IF NOT EXISTS size_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_size TEXT UNIQUE NOT NULL,
    your_creative_count INTEGER DEFAULT 0,  -- How many of your 653 creatives match
    total_reached_7d INTEGER DEFAULT 0,
    total_impressions_7d INTEGER DEFAULT 0,
    efficiency_pct REAL,  -- impressions / reached * 100
    waste_category TEXT,  -- 'none', 'low', 'medium', 'high', 'critical'
    recommendation TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- QPS waste recommendations (generated by analyzer)
CREATE TABLE IF NOT EXISTS qps_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recommendation_type TEXT NOT NULL,  -- 'exclude_size', 'exclude_app', 'adjust_geo', etc.
    billing_id TEXT,  -- Which pretargeting config to modify
    target TEXT,  -- What to exclude/include (e.g., "336x280")
    current_value TEXT,  -- Current setting
    recommended_value TEXT,  -- Recommended change
    waste_qps_daily INTEGER,  -- How much QPS this wastes per day
    waste_spend_daily REAL,  -- Estimated wasted spend
    confidence TEXT,  -- 'high', 'medium', 'low'
    rationale TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'implemented'
    implemented_at TIMESTAMP,
    implemented_by TEXT
);

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_size_metrics_date ON size_metrics_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_size_metrics_billing ON size_metrics_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_size_metrics_size ON size_metrics_daily(creative_size);
```

### Part 2: CSV Import Enhanced

Create/update the CSV importer to handle the BigQuery format with all 46 fields:

**File: `creative-intelligence/importers/bigquery_csv_importer.py`**

```python
#!/usr/bin/env python3
"""
BigQuery CSV Importer for QPS Analysis

Imports daily CSV exports from Google Authorized Buyers BigQuery
and aggregates for QPS waste analysis.
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
    "Publisher name": "publisher_name",
    "Creative format": "creative_format",
}


def parse_date(date_str: str) -> str:
    """Parse date from MM/DD/YYYY to YYYY-MM-DD"""
    try:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        # Try other formats
        for fmt in ["%Y-%m-%d", "%m/%d/%y", "%d/%m/%Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
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


def import_csv(csv_path: str, aggregate: bool = True) -> Dict:
    """
    Import a BigQuery CSV file.
    
    Args:
        csv_path: Path to CSV file
        aggregate: If True, aggregate by size/billing_id/country/date
                   If False, import raw rows
    
    Returns:
        Dict with import statistics
    """
    stats = {
        "rows_read": 0,
        "rows_imported": 0,
        "rows_skipped": 0,
        "errors": [],
        "sizes_found": set(),
        "billing_ids_found": set(),
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Read and process CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        if aggregate:
            # Aggregate data before inserting
            aggregated = {}
            
            for row in reader:
                stats["rows_read"] += 1
                
                # Extract key fields
                key = (
                    parse_date(row.get("#Day", "")),
                    row.get("Billing ID", ""),
                    row.get("Creative size", ""),
                    row.get("Country", ""),
                    row.get("Platform", ""),
                    row.get("Environment", "")
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
                
                # Aggregate metrics
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
                    stats["errors"].append(str(e))
                    stats["rows_skipped"] += 1
    
    conn.commit()
    conn.close()
    
    stats["sizes_found"] = list(stats["sizes_found"])
    stats["billing_ids_found"] = list(stats["billing_ids_found"])
    
    return stats


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python bigquery_csv_importer.py <csv_file>")
        sys.exit(1)
    
    result = import_csv(sys.argv[1])
    print(f"Import complete:")
    print(f"  Rows read: {result['rows_read']}")
    print(f"  Rows imported: {result['rows_imported']}")
    print(f"  Unique sizes: {len(result['sizes_found'])}")
    print(f"  Billing IDs: {result['billing_ids_found']}")
```

### Part 3: QPS Waste Analyzer

**File: `creative-intelligence/analyzers/qps_waste_analyzer.py`**

```python
#!/usr/bin/env python3
"""
QPS Waste Analyzer

Analyzes imported CSV data to identify where QPS is being wasted
and generates recommendations for pretargeting optimization.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass
import json

DB_PATH = os.path.expanduser("~/.rtbcat/rtbcat.db")

# Standard IAB sizes that are common and worth supporting
STANDARD_SIZES = {
    "300x250", "320x50", "728x90", "160x600", "300x600",
    "336x280", "320x100", "468x60", "970x250", "970x90",
    "300x50", "320x480", "480x320", "768x1024", "1024x768"
}


@dataclass
class SizeAnalysis:
    """Analysis result for a single size"""
    size: str
    reached_queries: int
    impressions: int
    efficiency_pct: float
    waste_qps: int
    is_standard: bool
    recommendation: str
    confidence: str


@dataclass
class ConfigAnalysis:
    """Analysis result for a pretargeting config"""
    billing_id: str
    name: str
    total_reached: int
    total_impressions: int
    efficiency_pct: float
    top_waste_sizes: List[SizeAnalysis]
    recommendations: List[str]


def get_db_connection():
    return sqlite3.connect(DB_PATH)


def analyze_sizes(days: int = 7) -> List[SizeAnalysis]:
    """
    Analyze creative size efficiency over the past N days.
    
    Returns list of SizeAnalysis sorted by waste (highest first).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT 
            creative_size,
            SUM(reached_queries) as total_reached,
            SUM(impressions) as total_impressions
        FROM size_metrics_daily
        WHERE metric_date >= ?
        GROUP BY creative_size
        ORDER BY SUM(reached_queries) DESC
    """, (cutoff_date,))
    
    results = []
    for row in cursor.fetchall():
        size, reached, impressions = row
        efficiency = (impressions / reached * 100) if reached > 0 else 0
        waste = reached - impressions
        is_standard = size in STANDARD_SIZES
        
        # Determine recommendation
        if efficiency >= 70:
            recommendation = "KEEP - Good efficiency"
            confidence = "high"
        elif efficiency >= 50:
            recommendation = "MONITOR - Mediocre efficiency"
            confidence = "medium"
        elif efficiency >= 30:
            recommendation = "CONSIDER EXCLUDING - Low efficiency"
            confidence = "medium"
        else:
            recommendation = "EXCLUDE - Very low efficiency, high waste"
            confidence = "high"
        
        # Adjust for standard sizes (more valuable to keep)
        if is_standard and efficiency < 50:
            recommendation = f"INVESTIGATE - Standard size with low efficiency ({efficiency:.1f}%)"
            confidence = "medium"
        
        results.append(SizeAnalysis(
            size=size,
            reached_queries=reached,
            impressions=impressions,
            efficiency_pct=efficiency,
            waste_qps=waste,
            is_standard=is_standard,
            recommendation=recommendation,
            confidence=confidence
        ))
    
    conn.close()
    
    # Sort by waste QPS (highest first)
    return sorted(results, key=lambda x: x.waste_qps, reverse=True)


def analyze_by_config(days: int = 7) -> Dict[str, ConfigAnalysis]:
    """
    Analyze efficiency per pretargeting config.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Get overall stats per billing ID
    cursor.execute("""
        SELECT 
            billing_id,
            SUM(reached_queries) as total_reached,
            SUM(impressions) as total_impressions
        FROM size_metrics_daily
        WHERE metric_date >= ?
        GROUP BY billing_id
    """, (cutoff_date,))
    
    config_stats = {}
    for row in cursor.fetchall():
        billing_id, reached, impressions = row
        efficiency = (impressions / reached * 100) if reached > 0 else 0
        config_stats[billing_id] = {
            "reached": reached,
            "impressions": impressions,
            "efficiency": efficiency
        }
    
    # Get top waste sizes per config
    cursor.execute("""
        SELECT 
            billing_id,
            creative_size,
            SUM(reached_queries) as reached,
            SUM(impressions) as impressions
        FROM size_metrics_daily
        WHERE metric_date >= ?
        GROUP BY billing_id, creative_size
        HAVING SUM(reached_queries) > 100  -- Only sizes with meaningful volume
        ORDER BY billing_id, (SUM(reached_queries) - SUM(impressions)) DESC
    """, (cutoff_date,))
    
    waste_by_config = {}
    for row in cursor.fetchall():
        billing_id, size, reached, impressions = row
        if billing_id not in waste_by_config:
            waste_by_config[billing_id] = []
        
        efficiency = (impressions / reached * 100) if reached > 0 else 0
        if efficiency < 50:  # Only include waste sizes
            waste_by_config[billing_id].append({
                "size": size,
                "reached": reached,
                "impressions": impressions,
                "efficiency": efficiency,
                "waste": reached - impressions
            })
    
    conn.close()
    
    # Build results
    results = {}
    for billing_id, stats in config_stats.items():
        waste_sizes = waste_by_config.get(billing_id, [])[:5]  # Top 5 waste sizes
        
        recommendations = []
        for ws in waste_sizes:
            if ws["efficiency"] < 30:
                recommendations.append(
                    f"EXCLUDE size {ws['size']} - Only {ws['efficiency']:.1f}% efficient, "
                    f"wastes {ws['waste']:,} QPS/day"
                )
        
        results[billing_id] = ConfigAnalysis(
            billing_id=billing_id,
            name=billing_id,  # Will be enriched from config table
            total_reached=stats["reached"],
            total_impressions=stats["impressions"],
            efficiency_pct=stats["efficiency"],
            top_waste_sizes=[
                SizeAnalysis(
                    size=ws["size"],
                    reached_queries=ws["reached"],
                    impressions=ws["impressions"],
                    efficiency_pct=ws["efficiency"],
                    waste_qps=ws["waste"],
                    is_standard=ws["size"] in STANDARD_SIZES,
                    recommendation="EXCLUDE" if ws["efficiency"] < 30 else "MONITOR",
                    confidence="high" if ws["efficiency"] < 30 else "medium"
                ) for ws in waste_sizes
            ],
            recommendations=recommendations
        )
    
    return results


def generate_report(days: int = 7) -> str:
    """
    Generate a human-readable QPS Waste Report.
    
    This is the "printout" for AdOps to review before making changes.
    """
    sizes = analyze_sizes(days)
    configs = analyze_by_config(days)
    
    report = []
    report.append("=" * 80)
    report.append("QPS WASTE ANALYSIS REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Analysis Period: Last {days} days")
    report.append("=" * 80)
    
    # Overall summary
    total_reached = sum(s.reached_queries for s in sizes)
    total_impressions = sum(s.impressions for s in sizes)
    total_waste = total_reached - total_impressions
    overall_efficiency = (total_impressions / total_reached * 100) if total_reached > 0 else 0
    
    report.append("")
    report.append("EXECUTIVE SUMMARY")
    report.append("-" * 40)
    report.append(f"Total Reached Queries:  {total_reached:>15,}")
    report.append(f"Total Impressions:      {total_impressions:>15,}")
    report.append(f"Total Wasted QPS:       {total_waste:>15,}")
    report.append(f"Overall Efficiency:     {overall_efficiency:>14.1f}%")
    report.append("")
    report.append(f"⚠️  {total_waste:,} QPS are being wasted daily!")
    report.append(f"    This represents {100 - overall_efficiency:.1f}% of your endpoint capacity.")
    
    # Top waste sizes
    report.append("")
    report.append("=" * 80)
    report.append("TOP 20 WASTE SIZES (by wasted QPS)")
    report.append("=" * 80)
    report.append("")
    report.append(f"{'Size':<15} {'Reached':>12} {'Impress':>12} {'Waste':>12} {'Eff%':>8} {'Action'}")
    report.append("-" * 80)
    
    for size in sizes[:20]:
        std_marker = "★" if size.is_standard else " "
        report.append(
            f"{std_marker}{size.size:<14} {size.reached_queries:>12,} {size.impressions:>12,} "
            f"{size.waste_qps:>12,} {size.efficiency_pct:>7.1f}% {size.recommendation}"
        )
    
    report.append("")
    report.append("★ = Standard IAB size (valuable, investigate before excluding)")
    
    # Per-config analysis
    report.append("")
    report.append("=" * 80)
    report.append("ANALYSIS BY PRETARGETING CONFIG")
    report.append("=" * 80)
    
    for billing_id, config in sorted(configs.items(), key=lambda x: -x[1].total_reached):
        report.append("")
        report.append(f"CONFIG: {billing_id}")
        report.append(f"  Reached: {config.total_reached:,} | Impressions: {config.total_impressions:,} | Efficiency: {config.efficiency_pct:.1f}%")
        
        if config.recommendations:
            report.append("  RECOMMENDATIONS:")
            for rec in config.recommendations:
                report.append(f"    → {rec}")
        else:
            report.append("  ✓ No immediate action needed")
    
    # Actionable recommendations
    report.append("")
    report.append("=" * 80)
    report.append("ACTIONABLE RECOMMENDATIONS")
    report.append("=" * 80)
    report.append("")
    report.append("The following sizes should be EXCLUDED from pretargeting configs:")
    report.append("(Copy these to the Authorized Buyers UI → Pretargeting → Creative dimensions)")
    report.append("")
    
    exclude_sizes = [s for s in sizes if s.efficiency_pct < 30 and s.waste_qps > 1000]
    for size in exclude_sizes[:10]:
        report.append(f"  ❌ {size.size} - Efficiency: {size.efficiency_pct:.1f}%, Waste: {size.waste_qps:,} QPS/day")
    
    report.append("")
    report.append("-" * 80)
    report.append("⚠️  IMPORTANT: Review these recommendations before implementing!")
    report.append("    Some sizes may have strategic value despite low efficiency.")
    report.append("    To implement via API, run: python qps_waste_analyzer.py --apply")
    report.append("-" * 80)
    
    return "\n".join(report)


def save_recommendations(days: int = 7):
    """
    Save recommendations to the database for tracking and optional API implementation.
    """
    sizes = analyze_sizes(days)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for size in sizes:
        if size.efficiency_pct < 50:  # Only save problematic sizes
            cursor.execute("""
                INSERT INTO qps_recommendations 
                (recommendation_type, target, waste_qps_daily, confidence, rationale, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
            """, (
                "exclude_size",
                size.size,
                size.waste_qps,
                size.confidence,
                f"Efficiency {size.efficiency_pct:.1f}%, {size.reached_queries:,} reached, {size.impressions:,} impressions",
                "pending"
            ))
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import sys
    
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        days = int(sys.argv[idx + 1])
    
    if "--apply" in sys.argv:
        print("API implementation not yet available.")
        print("Please implement recommendations manually in the Authorized Buyers UI.")
        sys.exit(1)
    
    # Generate and print the report
    report = generate_report(days)
    print(report)
    
    # Save recommendations to database
    save_recommendations(days)
    print("\n✓ Recommendations saved to database for tracking.")
```

### Part 4: CLI Interface

**File: `creative-intelligence/cli/analyze_qps.py`**

```python
#!/usr/bin/env python3
"""
RTBcat QPS Analysis CLI

Usage:
    python analyze_qps.py import <csv_file>    Import a BigQuery CSV
    python analyze_qps.py report [--days N]    Generate waste report
    python analyze_qps.py sizes                List all sizes with efficiency
    python analyze_qps.py configs              List all pretargeting configs
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from importers.bigquery_csv_importer import import_csv
from analyzers.qps_waste_analyzer import generate_report, analyze_sizes, analyze_by_config


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "import":
        if len(sys.argv) < 3:
            print("Usage: python analyze_qps.py import <csv_file>")
            sys.exit(1)
        
        csv_path = sys.argv[2]
        print(f"Importing {csv_path}...")
        result = import_csv(csv_path)
        print(f"✓ Import complete:")
        print(f"  Rows read: {result['rows_read']}")
        print(f"  Rows imported: {result['rows_imported']}")
        print(f"  Unique sizes: {len(result['sizes_found'])}")
        print(f"  Billing IDs: {result['billing_ids_found']}")
    
    elif command == "report":
        days = 7
        if "--days" in sys.argv:
            idx = sys.argv.index("--days")
            days = int(sys.argv[idx + 1])
        
        print(generate_report(days))
    
    elif command == "sizes":
        sizes = analyze_sizes()
        print(f"{'Size':<15} {'Reached':>12} {'Impressions':>12} {'Efficiency':>10} {'Waste':>12}")
        print("-" * 65)
        for s in sizes:
            print(f"{s.size:<15} {s.reached_queries:>12,} {s.impressions:>12,} {s.efficiency_pct:>9.1f}% {s.waste_qps:>12,}")
    
    elif command == "configs":
        configs = analyze_by_config()
        for billing_id, config in configs.items():
            print(f"\n{billing_id}: {config.efficiency_pct:.1f}% efficient")
            print(f"  Reached: {config.total_reached:,} | Impressions: {config.total_impressions:,}")
            for rec in config.recommendations[:3]:
                print(f"  → {rec}")
    
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## Part 5: Integration with RTBcat Dashboard

Add a new page to the Next.js dashboard to display QPS analysis:

**File: `dashboard/src/app/qps-analysis/page.tsx`**

Create a page that:
1. Shows overall efficiency metrics
2. Lists top waste sizes with recommendations
3. Shows per-config analysis
4. Allows downloading the printout report

This should call new API endpoints:
- `GET /api/qps/sizes` - List sizes with efficiency
- `GET /api/qps/configs` - List config analysis
- `GET /api/qps/report` - Get text report
- `POST /api/qps/import` - Upload CSV for import

---

## Success Criteria

After implementing this prompt:

- [ ] Database schema extended with new tables
- [ ] CSV importer handles BigQuery format with all 46 fields
- [ ] QPS Waste Analyzer generates accurate reports
- [ ] CLI tools work for import and analysis
- [ ] Reports are human-readable "printouts" for AdOps review
- [ ] Recommendations are saved to database for tracking

---

## Example Report Output

```
================================================================================
QPS WASTE ANALYSIS REPORT
Generated: 2025-12-01 14:30:00
Analysis Period: Last 7 days
================================================================================

EXECUTIVE SUMMARY
----------------------------------------
Total Reached Queries:        890,234,567
Total Impressions:            623,164,197
Total Wasted QPS:             267,070,370
Overall Efficiency:                 70.0%

⚠️  267,070,370 QPS are being wasted daily!
    This represents 30.0% of your endpoint capacity.

================================================================================
TOP 20 WASTE SIZES (by wasted QPS)
================================================================================

Size            Reached     Impress        Waste     Eff%  Action
--------------------------------------------------------------------------------
 336x280       14,570,000   4,173,000  10,397,000   28.6%  EXCLUDE - Very low efficiency
 392x327        6,900,000   3,890,000   3,010,000   56.4%  MONITOR - Mediocre efficiency
★300x250      107,663,000  80,062,000  27,601,000   74.4%  KEEP - Good efficiency
...
```

---

## DO NOT

- ❌ Automatically apply changes to pretargeting configs
- ❌ Delete or modify existing performance data
- ❌ Make API calls that affect live bidding without explicit user approval
- ❌ Store sensitive credentials in code

---

## After Completing

Tell Jen:
```
QPS Waste Analyzer implemented! Here's what was created:

Files:
- creative-intelligence/importers/bigquery_csv_importer.py
- creative-intelligence/analyzers/qps_waste_analyzer.py
- creative-intelligence/cli/analyze_qps.py

Usage:
1. Import CSV:  python cli/analyze_qps.py import /path/to/bigquery.csv
2. View report: python cli/analyze_qps.py report
3. List sizes:  python cli/analyze_qps.py sizes

The report shows which sizes to exclude from pretargeting.
All recommendations are "printouts" - manual implementation required.
```

---

**Priority:** HIGH - Core analytical engine
**Estimated time:** 2-3 hours
**Risk:** Low (read-only analysis, no auto-apply)
