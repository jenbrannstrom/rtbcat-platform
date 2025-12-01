# Claude CLI Prompt 2/4: CSV Importer with Strict Validation

## Context

RTBcat needs a CSV importer that:
1. **Detects** columns automatically from header
2. **Validates** required columns are present (rejects if not)
3. **Guides** users to fix their export config
4. **Stores** raw data (no aggregation)

**Project:** `/home/jen/Documents/rtbcat-platform/creative-intelligence/`

---

## Required Columns (MUST HAVE)

For RTBcat to function, the CSV MUST contain:

| Column | Why Required |
|--------|--------------|
| Day/Date | Time dimension for all analysis |
| Creative ID | Links to creatives table, creative-level analysis |
| Billing ID | Config performance tracking |
| Creative size | QPS coverage analysis |
| Reached queries | THE critical waste metric |
| Impressions | Basic performance |

If ANY of these are missing → **REJECT** with clear instructions.

---

## Task

### Replace `qps/importer.py` entirely:

```python
"""Unified BigQuery CSV Importer with Strict Validation.

Imports Authorized Buyers CSV exports. REQUIRES specific columns
to enable all RTBcat analysis features.

Usage:
    from qps.importer import import_csv, validate_csv
    
    # Check before import
    validation = validate_csv("/path/to/file.csv")
    if not validation.is_valid:
        print(validation.error_message)
        return
    
    # Import
    result = import_csv("/path/to/file.csv")
"""

import csv
import sqlite3
import os
import hashlib
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.rtbcat/rtbcat.db")


# ============================================================================
# COLUMN CONFIGURATION
# ============================================================================

# Required columns - import FAILS without these
REQUIRED_COLUMNS = {
    "day": ["#Day", "Day", "#Date", "Date"],
    "creative_id": ["Creative ID", "#Creative ID"],
    "billing_id": ["Billing ID", "#Billing ID"],
    "creative_size": ["Creative size", "#Creative size"],
    "reached_queries": ["Reached queries", "#Reached queries"],
    "impressions": ["Impressions", "#Impressions"],
}

# Optional columns - imported if present
OPTIONAL_COLUMNS = {
    "creative_format": ["Creative format", "#Creative format"],
    "country": ["Country", "#Country"],
    "platform": ["Platform", "#Platform"],
    "environment": ["Environment", "#Environment"],
    "app_id": ["Mobile app ID", "#Mobile app ID"],
    "app_name": ["Mobile app name", "#Mobile app name"],
    "publisher_id": ["Publisher ID", "#Publisher ID"],
    "publisher_name": ["Publisher name", "#Publisher name"],
    "publisher_domain": ["Publisher domain", "#Publisher domain"],
    "deal_id": ["Deal ID", "#Deal ID"],
    "deal_name": ["Deal name", "#Deal name"],
    "transaction_type": ["Transaction type", "#Transaction type"],
    "advertiser": ["Advertiser", "#Advertiser"],
    "buyer_account_id": ["Buyer account ID", "#Buyer account ID"],
    "buyer_account_name": ["Buyer account name", "#Buyer account name"],
    "clicks": ["Clicks", "#Clicks"],
    "spend": [
        "Spend (bidder currency)", "Spend _buyer currency_",
        "Spend (buyer currency)", "#Spend"
    ],
    "video_starts": ["Video starts", "#Video starts"],
    "video_first_quartile": ["Video reached first quartile"],
    "video_midpoint": ["Video reached midpoint"],
    "video_third_quartile": ["Video reached third quartile"],
    "video_completions": ["Video completions", "#Video completions"],
    "vast_errors": ["VAST error count", "#VAST error count"],
    "engaged_views": ["Engaged views"],
    "active_view_measurable": ["Active view measurable"],
    "active_view_viewable": ["Active view viewable"],
    "gma_sdk": ["GMA SDK"],
    "buyer_sdk": ["Buyer SDK"],
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ValidationResult:
    """Result of CSV validation."""
    is_valid: bool
    error_message: str = ""
    
    # What we found
    columns_found: List[str] = field(default_factory=list)
    columns_mapped: Dict[str, str] = field(default_factory=dict)
    
    # What's missing
    required_missing: List[str] = field(default_factory=list)
    optional_missing: List[str] = field(default_factory=list)
    
    # File info
    row_count_estimate: int = 0
    
    def get_fix_instructions(self) -> str:
        """Generate instructions for fixing the CSV export."""
        if self.is_valid:
            return ""
        
        lines = [
            "",
            "=" * 60,
            "HOW TO FIX YOUR CSV EXPORT",
            "=" * 60,
            "",
            "In Authorized Buyers, go to Reports → Create Report",
            "",
            "1. Under DIMENSIONS, add:",
        ]
        
        dimension_fixes = {
            "creative_id": "   • Creative ID",
            "billing_id": "   • Billing ID",
            "creative_size": "   • Creative size",
            "day": "   • Day (under Time dimensions)",
        }
        
        for col in self.required_missing:
            if col in dimension_fixes:
                lines.append(dimension_fixes[col])
        
        lines.append("")
        lines.append("2. Under METRICS, add:")
        
        metric_fixes = {
            "reached_queries": "   • Reached queries",
            "impressions": "   • Impressions",
        }
        
        for col in self.required_missing:
            if col in metric_fixes:
                lines.append(metric_fixes[col])
        
        lines.extend([
            "",
            "3. Click 'Run Report' and download as CSV",
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)


@dataclass
class ImportResult:
    """Result of CSV import."""
    success: bool = False
    error_message: str = ""
    
    # Counts
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0
    
    # Data summary
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    unique_creatives: int = 0
    unique_billing_ids: List[str] = field(default_factory=list)
    unique_sizes: List[str] = field(default_factory=list)
    unique_countries: List[str] = field(default_factory=list)
    
    # Totals
    total_reached: int = 0
    total_impressions: int = 0
    total_spend_usd: float = 0.0
    
    # Metadata
    batch_id: str = ""
    columns_imported: List[str] = field(default_factory=list)
    
    # Errors
    errors: List[str] = field(default_factory=list)


# ============================================================================
# VALIDATION
# ============================================================================

def validate_csv(csv_path: str) -> ValidationResult:
    """
    Validate a CSV file before import.
    
    Checks:
    1. File exists and is readable
    2. Has valid CSV header
    3. Contains ALL required columns
    
    Returns ValidationResult with is_valid=False if requirements not met.
    """
    result = ValidationResult(is_valid=False)
    
    # Check file exists
    if not os.path.exists(csv_path):
        result.error_message = f"File not found: {csv_path}"
        return result
    
    # Read header
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            result.columns_found = header
            
            # Count rows (estimate for large files)
            row_count = sum(1 for _ in f)
            result.row_count_estimate = row_count
    except Exception as e:
        result.error_message = f"Failed to read CSV: {e}"
        return result
    
    # Map columns
    header_set = set(header)
    
    # Check required columns
    for our_name, possible_names in REQUIRED_COLUMNS.items():
        found = False
        for csv_name in possible_names:
            if csv_name in header_set:
                result.columns_mapped[our_name] = csv_name
                found = True
                break
        if not found:
            result.required_missing.append(our_name)
    
    # Check optional columns
    for our_name, possible_names in OPTIONAL_COLUMNS.items():
        found = False
        for csv_name in possible_names:
            if csv_name in header_set:
                result.columns_mapped[our_name] = csv_name
                found = True
                break
        if not found:
            result.optional_missing.append(our_name)
    
    # Determine validity
    if result.required_missing:
        missing_str = ", ".join(result.required_missing)
        result.error_message = f"Missing required columns: {missing_str}"
        result.is_valid = False
    else:
        result.is_valid = True
    
    return result


# ============================================================================
# PARSING HELPERS
# ============================================================================

def parse_date(date_str: str) -> str:
    """Parse date from various formats to YYYY-MM-DD."""
    if not date_str:
        return ""
    
    formats = [
        "%m/%d/%Y",   # 11/30/2025
        "%m/%d/%y",   # 11/30/25
        "%Y-%m-%d",   # 2025-11-30
        "%d/%m/%Y",   # 30/11/2025
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return date_str  # Return as-is if no format matches


def parse_int(value) -> Optional[int]:
    """Parse integer, returning None for empty."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def parse_float(value) -> Optional[float]:
    """Parse float, returning None for empty."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace(",", "").replace("$", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def parse_bool(value) -> int:
    """Parse boolean to 0/1."""
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    val_str = str(value).strip().upper()
    return 1 if val_str in ("TRUE", "1", "YES") else 0


def compute_row_hash(row_data: Dict) -> str:
    """Compute hash of dimension values for deduplication."""
    # Include all dimension values (not metrics) in hash
    dimension_keys = [
        "metric_date", "creative_id", "billing_id", "creative_size",
        "country", "platform", "environment", "app_id", "publisher_id",
        "deal_id", "advertiser", "buyer_account_id"
    ]
    
    hash_input = "|".join(str(row_data.get(k, "")) for k in dimension_keys)
    return hashlib.md5(hash_input.encode()).hexdigest()


# ============================================================================
# IMPORT
# ============================================================================

def import_csv(csv_path: str, db_path: str = DB_PATH) -> ImportResult:
    """
    Import a validated CSV file into performance_data table.
    
    IMPORTANT: Call validate_csv() first! This function assumes
    the CSV has already been validated.
    
    Args:
        csv_path: Path to CSV file
        db_path: Database path
    
    Returns:
        ImportResult with statistics
    """
    result = ImportResult()
    result.batch_id = str(uuid.uuid4())[:8]
    
    # Validate first
    validation = validate_csv(csv_path)
    if not validation.is_valid:
        result.error_message = validation.error_message
        result.errors.append(validation.error_message)
        return result
    
    column_map = validation.columns_mapped
    result.columns_imported = list(column_map.keys())
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Tracking
    creative_ids: Set[str] = set()
    billing_ids: Set[str] = set()
    sizes: Set[str] = set()
    countries: Set[str] = set()
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    
    # Batch insert
    BATCH_SIZE = 1000
    batch: List[Tuple] = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):
                result.rows_read += 1
                
                try:
                    # Parse required fields
                    metric_date = parse_date(row.get(column_map["day"], ""))
                    creative_id = str(row.get(column_map["creative_id"], "")).strip()
                    billing_id = str(row.get(column_map["billing_id"], "")).strip()
                    creative_size = row.get(column_map["creative_size"], "").strip() or None
                    reached = parse_int(row.get(column_map["reached_queries"], 0)) or 0
                    impressions = parse_int(row.get(column_map["impressions"], 0)) or 0
                    
                    if not metric_date or not creative_id or not billing_id:
                        result.rows_skipped += 1
                        continue
                    
                    # Track date range
                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date
                    
                    # Parse optional fields
                    def get_opt(key: str) -> Optional[str]:
                        if key not in column_map:
                            return None
                        val = row.get(column_map[key], "").strip()
                        return val if val else None
                    
                    def get_opt_int(key: str) -> Optional[int]:
                        if key not in column_map:
                            return None
                        return parse_int(row.get(column_map[key], ""))
                    
                    creative_format = get_opt("creative_format")
                    country = get_opt("country")
                    platform = get_opt("platform")
                    environment = get_opt("environment")
                    app_id = get_opt("app_id")
                    app_name = get_opt("app_name")
                    publisher_id = get_opt("publisher_id")
                    publisher_name = get_opt("publisher_name")
                    publisher_domain = get_opt("publisher_domain")
                    deal_id = get_opt("deal_id")
                    if deal_id == "0":
                        deal_id = None
                    deal_name = get_opt("deal_name")
                    if deal_name == "(none)":
                        deal_name = None
                    transaction_type = get_opt("transaction_type")
                    advertiser = get_opt("advertiser")
                    buyer_account_id = get_opt("buyer_account_id")
                    buyer_account_name = get_opt("buyer_account_name")
                    
                    clicks = get_opt_int("clicks") or 0
                    spend_raw = parse_float(row.get(column_map.get("spend", ""), 0)) or 0
                    spend_micros = int(spend_raw * 1_000_000)
                    
                    video_starts = get_opt_int("video_starts")
                    video_first_quartile = get_opt_int("video_first_quartile")
                    video_midpoint = get_opt_int("video_midpoint")
                    video_third_quartile = get_opt_int("video_third_quartile")
                    video_completions = get_opt_int("video_completions")
                    vast_errors = get_opt_int("vast_errors")
                    engaged_views = get_opt_int("engaged_views")
                    
                    active_view_measurable = get_opt_int("active_view_measurable")
                    active_view_viewable = get_opt_int("active_view_viewable")
                    
                    gma_sdk = parse_bool(row.get(column_map.get("gma_sdk", ""), ""))
                    buyer_sdk = parse_bool(row.get(column_map.get("buyer_sdk", ""), ""))
                    
                    # Build row data for hash
                    row_data = {
                        "metric_date": metric_date,
                        "creative_id": creative_id,
                        "billing_id": billing_id,
                        "creative_size": creative_size,
                        "country": country,
                        "platform": platform,
                        "environment": environment,
                        "app_id": app_id,
                        "publisher_id": publisher_id,
                        "deal_id": deal_id,
                        "advertiser": advertiser,
                        "buyer_account_id": buyer_account_id,
                    }
                    row_hash = compute_row_hash(row_data)
                    
                    # Track stats
                    creative_ids.add(creative_id)
                    billing_ids.add(billing_id)
                    if creative_size:
                        sizes.add(creative_size)
                    if country:
                        countries.add(country)
                    result.total_reached += reached
                    result.total_impressions += impressions
                    result.total_spend_usd += spend_raw
                    
                    # Add to batch
                    batch.append((
                        metric_date, creative_id, billing_id,
                        creative_size, creative_format, country, platform, environment,
                        app_id, app_name, publisher_id, publisher_name, publisher_domain,
                        deal_id, deal_name, transaction_type,
                        advertiser, buyer_account_id, buyer_account_name,
                        reached, impressions, clicks, spend_micros,
                        video_starts, video_first_quartile, video_midpoint,
                        video_third_quartile, video_completions, vast_errors, engaged_views,
                        active_view_measurable, active_view_viewable,
                        gma_sdk, buyer_sdk,
                        row_hash, result.batch_id
                    ))
                    
                    # Insert batch
                    if len(batch) >= BATCH_SIZE:
                        imported, dupes = _insert_batch(cursor, batch)
                        result.rows_imported += imported
                        result.rows_duplicate += dupes
                        batch = []
                        
                        if result.rows_read % 50000 == 0:
                            logger.info(f"Progress: {result.rows_read:,} read, {result.rows_imported:,} imported")
                
                except Exception as e:
                    result.rows_skipped += 1
                    if len(result.errors) < 20:
                        result.errors.append(f"Row {row_num}: {str(e)}")
        
        # Final batch
        if batch:
            imported, dupes = _insert_batch(cursor, batch)
            result.rows_imported += imported
            result.rows_duplicate += dupes
        
        conn.commit()
        
        # Record import history
        _record_import_history(cursor, result, csv_path, validation)
        conn.commit()
        
        result.success = True
        
    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")
        logger.error(f"Import failed: {e}")
    
    finally:
        conn.close()
    
    # Populate result
    result.date_range_start = min_date
    result.date_range_end = max_date
    result.unique_creatives = len(creative_ids)
    result.unique_billing_ids = sorted(list(billing_ids))
    result.unique_sizes = sorted(list(sizes))
    result.unique_countries = sorted(list(countries))
    
    return result


def _insert_batch(cursor: sqlite3.Cursor, batch: List[Tuple]) -> Tuple[int, int]:
    """Insert batch of rows. Returns (inserted, duplicates)."""
    inserted = 0
    duplicates = 0
    
    for row in batch:
        try:
            cursor.execute("""
                INSERT INTO performance_data (
                    metric_date, creative_id, billing_id,
                    creative_size, creative_format, country, platform, environment,
                    app_id, app_name, publisher_id, publisher_name, publisher_domain,
                    deal_id, deal_name, transaction_type,
                    advertiser, buyer_account_id, buyer_account_name,
                    reached_queries, impressions, clicks, spend_micros,
                    video_starts, video_first_quartile, video_midpoint,
                    video_third_quartile, video_completions, vast_errors, engaged_views,
                    active_view_measurable, active_view_viewable,
                    gma_sdk, buyer_sdk,
                    row_hash, import_batch_id
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, row)
            inserted += 1
        except sqlite3.IntegrityError:
            # Duplicate row_hash
            duplicates += 1
    
    return inserted, duplicates


def _record_import_history(cursor, result: ImportResult, csv_path: str, validation: ValidationResult):
    """Record import in history table."""
    try:
        cursor.execute("""
            INSERT INTO import_history (
                batch_id, filename, rows_read, rows_imported, rows_skipped, rows_duplicate,
                date_range_start, date_range_end, columns_found, columns_missing,
                total_reached, total_impressions, total_spend_usd, status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.batch_id,
            os.path.basename(csv_path),
            result.rows_read,
            result.rows_imported,
            result.rows_skipped,
            result.rows_duplicate,
            result.date_range_start,
            result.date_range_end,
            ",".join(result.columns_imported),
            ",".join(validation.optional_missing) if validation.optional_missing else None,
            result.total_reached,
            result.total_impressions,
            result.total_spend_usd,
            "complete" if result.success else "failed",
            result.error_message if result.error_message else None
        ))
    except Exception as e:
        logger.warning(f"Failed to record import history: {e}")


# ============================================================================
# UTILITIES
# ============================================================================

def get_data_summary(db_path: str = DB_PATH) -> Dict:
    """Get summary of imported data."""
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
            "date_range": {"start": row[6], "end": row[7]},
            "total_reached_queries": row[8] or 0,
            "total_impressions": row[9] or 0,
            "total_clicks": row[10] or 0,
            "total_spend_usd": (row[11] or 0) / 1_000_000,
        }
    finally:
        conn.close()


# Backward compatibility
def get_import_summary(db_path: str = DB_PATH) -> Dict:
    return get_data_summary(db_path)


def import_bigquery_csv(csv_path: str, db_path: str = DB_PATH) -> ImportResult:
    """Backward compatible alias for import_csv."""
    return import_csv(csv_path, db_path)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m qps.importer <csv_file>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    
    print(f"Validating {csv_path}...")
    validation = validate_csv(csv_path)
    
    if not validation.is_valid:
        print(f"\n❌ VALIDATION FAILED")
        print(f"\nError: {validation.error_message}")
        print(validation.get_fix_instructions())
        sys.exit(1)
    
    print(f"✓ Validation passed ({validation.row_count_estimate:,} rows)")
    print(f"  Columns mapped: {len(validation.columns_mapped)}")
    if validation.optional_missing:
        print(f"  Optional missing: {', '.join(validation.optional_missing[:5])}")
    
    print(f"\nImporting...")
    result = import_csv(csv_path)
    
    if result.success:
        print(f"\n✅ IMPORT COMPLETE")
        print(f"  Rows read:        {result.rows_read:,}")
        print(f"  Rows imported:    {result.rows_imported:,}")
        print(f"  Rows duplicate:   {result.rows_duplicate:,}")
        print(f"  Rows skipped:     {result.rows_skipped:,}")
        print(f"  Date range:       {result.date_range_start} to {result.date_range_end}")
        print(f"  Unique creatives: {result.unique_creatives:,}")
        print(f"  Unique sizes:     {len(result.unique_sizes)}")
        print(f"  Total reached:    {result.total_reached:,}")
        print(f"  Total spend:      ${result.total_spend_usd:,.2f}")
    else:
        print(f"\n❌ IMPORT FAILED: {result.error_message}")
        sys.exit(1)
```

---

## Success Criteria

- [ ] validate_csv() detects columns and identifies missing required ones
- [ ] Clear error message when required columns missing
- [ ] get_fix_instructions() tells user exactly what to add in Authorized Buyers
- [ ] import_csv() stores raw data with row hash for deduplication
- [ ] Import history recorded for tracking
- [ ] Backward compatible functions (import_bigquery_csv, get_import_summary)

---

## After Completing

Tell Jen: "CSV Importer complete. Ready for Prompt 3 (Update Analyzers)."
