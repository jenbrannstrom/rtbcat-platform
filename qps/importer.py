"""Unified BigQuery CSV Importer with Strict Validation.

Imports Authorized Buyers CSV exports. REQUIRES specific columns
to enable all RTBcat analysis features.

Multi-Account Support:
    The importer tracks which account (bidder_id) each import belongs to.
    If bidder_id is not provided, it will be looked up from the billing_id
    using the pretargeting_configs table.

Usage:
    from qps.importer import import_csv, validate_csv

    # Check before import
    validation = validate_csv("/path/to/file.csv")
    if not validation.is_valid:
        print(validation.error_message)
        return

    # Import with explicit account association
    result = import_csv("/path/to/file.csv", bidder_id="12345678")

    # Or let it auto-detect from billing_id
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

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")


# ============================================================================
# COLUMN CONFIGURATION
# ============================================================================

# Required columns - import FAILS without these
REQUIRED_COLUMNS = {
    "day": ["#Day", "Day", "#Date", "Date"],
    "creative_id": ["Creative ID", "#Creative ID"],
    "billing_id": ["Billing ID", "#Billing ID"],
    "creative_size": ["Creative size", "#Creative size"],
    "country": ["Country", "#Country"],  # Required for geo-level QPS optimization
    "reached_queries": ["Reached queries", "#Reached queries"],
    "impressions": ["Impressions", "#Impressions"],
}

# Optional columns - imported if present
OPTIONAL_COLUMNS = {
    "hour": ["Hour", "#Hour"],  # NEW: Hourly granularity
    "creative_format": ["Creative format", "#Creative format"],
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
            "country": "   • Country",
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

    # Account association (multi-account support)
    bidder_id: Optional[str] = None  # The account this import belongs to
    bidder_id_source: str = ""  # "explicit", "inferred", "unknown"

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
        "metric_date", "hour", "creative_id", "billing_id", "creative_size",
        "country", "platform", "environment", "app_id", "publisher_id",
        "deal_id", "advertiser", "buyer_account_id"
    ]

    hash_input = "|".join(str(row_data.get(k, "")) for k in dimension_keys)
    return hashlib.md5(hash_input.encode()).hexdigest()


# ============================================================================
# IMPORT
# ============================================================================

def import_csv(
    csv_path: str,
    db_path: str = DB_PATH,
    bidder_id: Optional[str] = None,
) -> ImportResult:
    """
    Import a validated CSV file into rtb_daily table.

    IMPORTANT: Call validate_csv() first! This function assumes
    the CSV has already been validated.

    Multi-Account Support:
        If bidder_id is provided, all rows will be associated with that account.
        If not provided, the importer will try to infer it from the billing_id
        by looking up the pretargeting_configs table.

    Args:
        csv_path: Path to CSV file
        db_path: Database path
        bidder_id: Optional account ID to associate with this import.
                   If not provided, will be inferred from billing_id.

    Returns:
        ImportResult with statistics
    """
    result = ImportResult()
    result.batch_id = str(uuid.uuid4())[:8]

    # Track bidder_id source
    if bidder_id:
        result.bidder_id = bidder_id
        result.bidder_id_source = "explicit"
    else:
        result.bidder_id_source = "unknown"  # Will update if inferred

    # Validate first
    validation = validate_csv(csv_path)
    if not validation.is_valid:
        result.error_message = validation.error_message
        result.errors.append(validation.error_message)
        return result

    column_map = validation.columns_mapped
    result.columns_imported = list(column_map.keys())

    # Import account mapper for bidder_id lookup
    try:
        from qps.account_mapper import get_account_mapper
        account_mapper = get_account_mapper(db_path)
    except ImportError:
        account_mapper = None
        logger.warning("AccountMapper not available, bidder_id inference disabled")

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

                    # NEW: Parse hour for hourly granularity
                    hour = get_opt_int("hour")

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
                        "hour": hour,
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

                    # Determine bidder_id for this row
                    row_bidder_id = result.bidder_id  # Use explicit if provided
                    if not row_bidder_id and account_mapper and billing_id:
                        # Try to infer from billing_id
                        row_bidder_id = account_mapper.get_bidder_id(billing_id)
                        if row_bidder_id and result.bidder_id_source == "unknown":
                            result.bidder_id = row_bidder_id
                            result.bidder_id_source = "inferred"

                    # Add to batch (includes bidder_id and hour)
                    batch.append((
                        metric_date, hour, creative_id, billing_id,
                        creative_size, creative_format, country, platform, environment,
                        app_id, app_name, publisher_id, publisher_name, publisher_domain,
                        deal_id, deal_name, transaction_type,
                        advertiser, buyer_account_id, buyer_account_name,
                        reached, impressions, clicks, spend_micros,
                        video_starts, video_first_quartile, video_midpoint,
                        video_third_quartile, video_completions, vast_errors, engaged_views,
                        active_view_measurable, active_view_viewable,
                        gma_sdk, buyer_sdk,
                        row_hash, result.batch_id,
                        row_bidder_id  # bidder_id for multi-account support
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

        # Track first_seen_at for creatives
        _update_creative_first_seen(cursor, creative_ids, result.batch_id)

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
                INSERT INTO rtb_daily (
                    metric_date, hour, creative_id, billing_id,
                    creative_size, creative_format, country, platform, environment,
                    app_id, app_name, publisher_id, publisher_name, publisher_domain,
                    deal_id, deal_name, transaction_type,
                    advertiser, buyer_account_id, buyer_account_name,
                    reached_queries, impressions, clicks, spend_micros,
                    video_starts, video_first_quartile, video_midpoint,
                    video_third_quartile, video_completions, vast_errors, engaged_views,
                    active_view_measurable, active_view_viewable,
                    gma_sdk, buyer_sdk,
                    row_hash, import_batch_id,
                    bidder_id
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, row)
            inserted += 1
        except sqlite3.IntegrityError:
            # Duplicate row_hash
            duplicates += 1

    return inserted, duplicates


def _record_import_history(cursor, result: ImportResult, csv_path: str, validation: ValidationResult):
    """Record import in history table."""
    import json

    try:
        # Get file size
        file_size_bytes = os.path.getsize(csv_path) if os.path.exists(csv_path) else 0

        # Serialize billing_ids as JSON
        billing_ids_json = json.dumps(result.unique_billing_ids) if result.unique_billing_ids else None

        cursor.execute("""
            INSERT INTO import_history (
                batch_id, filename, rows_read, rows_imported, rows_skipped, rows_duplicate,
                date_range_start, date_range_end, columns_found, columns_missing,
                total_reached, total_impressions, total_spend_usd, status, error_message,
                file_size_bytes, bidder_id, billing_ids_found
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            result.error_message if result.error_message else None,
            file_size_bytes,
            result.bidder_id,  # NEW: account association
            billing_ids_json,  # NEW: all billing IDs found in this import
        ))

        # Update daily upload summary
        _update_daily_upload_summary(cursor, result, file_size_bytes)

        # Update per-account daily summary if we have bidder_id
        if result.bidder_id:
            _update_account_daily_upload_summary(cursor, result, file_size_bytes)

    except Exception as e:
        logger.warning(f"Failed to record import history: {e}")


def _update_daily_upload_summary(cursor, result: ImportResult, file_size_bytes: int):
    """Update the daily upload summary table with aggregated stats."""
    try:
        import_date = datetime.now().strftime("%Y-%m-%d")
        is_success = 1 if result.success else 0
        is_failure = 0 if result.success else 1

        # Check if entry exists for today
        cursor.execute(
            "SELECT id, total_uploads, successful_uploads, failed_uploads, "
            "total_rows_written, total_file_size_bytes, min_rows, max_rows "
            "FROM daily_upload_summary WHERE upload_date = ?",
            (import_date,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing entry
            new_total = existing[1] + 1
            new_success = existing[2] + is_success
            new_failed = existing[3] + is_failure
            new_rows = existing[4] + result.rows_imported
            new_size = existing[5] + file_size_bytes
            new_avg = new_rows / new_total if new_total > 0 else 0

            # Update min/max rows
            min_rows = min(existing[6], result.rows_imported) if existing[6] is not None else result.rows_imported
            max_rows = max(existing[7], result.rows_imported) if existing[7] is not None else result.rows_imported

            cursor.execute("""
                UPDATE daily_upload_summary SET
                    total_uploads = ?,
                    successful_uploads = ?,
                    failed_uploads = ?,
                    total_rows_written = ?,
                    total_file_size_bytes = ?,
                    avg_rows_per_upload = ?,
                    min_rows = ?,
                    max_rows = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE upload_date = ?
            """, (new_total, new_success, new_failed, new_rows, new_size,
                  new_avg, min_rows, max_rows, import_date))
        else:
            # Insert new entry
            cursor.execute("""
                INSERT INTO daily_upload_summary (
                    upload_date, total_uploads, successful_uploads, failed_uploads,
                    total_rows_written, total_file_size_bytes, avg_rows_per_upload,
                    min_rows, max_rows
                ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
            """, (import_date, is_success, is_failure, result.rows_imported,
                  file_size_bytes, result.rows_imported, result.rows_imported, result.rows_imported))

        # Check for anomalies (row count spikes/drops compared to recent days)
        _check_upload_anomalies(cursor, import_date)

    except Exception as e:
        logger.warning(f"Failed to update daily upload summary: {e}")


def _update_creative_first_seen(cursor, creative_ids: Set[str], batch_id: str):
    """Update first_seen_at for creatives that don't have it set yet."""
    try:
        now = datetime.now().isoformat()

        for creative_id in creative_ids:
            # Update only if first_seen_at is NULL
            cursor.execute("""
                UPDATE creatives
                SET first_seen_at = ?,
                    first_import_batch_id = ?
                WHERE id = ?
                AND first_seen_at IS NULL
            """, (now, batch_id, creative_id))

    except Exception as e:
        logger.warning(f"Failed to update creative first_seen_at: {e}")


def _check_upload_anomalies(cursor, current_date: str):
    """Check for anomalies in row counts compared to recent days (Mon-Sun pattern)."""
    try:
        # Get last 7 days of data
        cursor.execute("""
            SELECT upload_date, total_rows_written
            FROM daily_upload_summary
            WHERE upload_date < ?
            ORDER BY upload_date DESC
            LIMIT 7
        """, (current_date,))
        recent_days = cursor.fetchall()

        if len(recent_days) < 3:
            # Not enough data to detect anomalies
            return

        # Calculate average and std deviation of recent days
        row_counts = [day[1] for day in recent_days if day[1] is not None and day[1] > 0]
        if not row_counts:
            return

        avg_rows = sum(row_counts) / len(row_counts)

        # Get current day's row count
        cursor.execute(
            "SELECT total_rows_written FROM daily_upload_summary WHERE upload_date = ?",
            (current_date,)
        )
        current = cursor.fetchone()
        if not current or current[0] is None:
            return

        current_rows = current[0]

        # Detect anomaly: >50% drop or >200% spike from average
        anomaly_reason = None
        if avg_rows > 0:
            ratio = current_rows / avg_rows
            if ratio < 0.5:
                anomaly_reason = f"Row count dropped {((1-ratio)*100):.0f}% below 7-day average ({current_rows:,} vs avg {avg_rows:,.0f})"
            elif ratio > 2.0:
                anomaly_reason = f"Row count spiked {((ratio-1)*100):.0f}% above 7-day average ({current_rows:,} vs avg {avg_rows:,.0f})"

        # Update anomaly flag
        has_anomaly = 1 if anomaly_reason else 0
        cursor.execute("""
            UPDATE daily_upload_summary
            SET has_anomaly = ?, anomaly_reason = ?
            WHERE upload_date = ?
        """, (has_anomaly, anomaly_reason, current_date))

    except Exception as e:
        logger.warning(f"Failed to check upload anomalies: {e}")


def _update_account_daily_upload_summary(cursor, result: ImportResult, file_size_bytes: int):
    """Update the per-account daily upload summary table.

    This tracks upload statistics per account (bidder_id) per day,
    enabling multi-account upload monitoring.
    """
    if not result.bidder_id:
        return

    try:
        import_date = datetime.now().strftime("%Y-%m-%d")
        is_success = 1 if result.success else 0
        is_failure = 0 if result.success else 1

        # Check if entry exists for today + this account
        cursor.execute(
            """SELECT id, total_uploads, successful_uploads, failed_uploads,
               total_rows_written, total_file_size_bytes, min_rows, max_rows
               FROM account_daily_upload_summary
               WHERE upload_date = ? AND bidder_id = ?""",
            (import_date, result.bidder_id)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing entry
            new_total = existing[1] + 1
            new_success = existing[2] + is_success
            new_failed = existing[3] + is_failure
            new_rows = existing[4] + result.rows_imported
            new_size = existing[5] + file_size_bytes
            new_avg = new_rows / new_total if new_total > 0 else 0

            # Update min/max rows
            min_rows = min(existing[6], result.rows_imported) if existing[6] is not None else result.rows_imported
            max_rows = max(existing[7], result.rows_imported) if existing[7] is not None else result.rows_imported

            cursor.execute("""
                UPDATE account_daily_upload_summary SET
                    total_uploads = ?,
                    successful_uploads = ?,
                    failed_uploads = ?,
                    total_rows_written = ?,
                    total_file_size_bytes = ?,
                    avg_rows_per_upload = ?,
                    min_rows = ?,
                    max_rows = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE upload_date = ? AND bidder_id = ?
            """, (new_total, new_success, new_failed, new_rows, new_size,
                  new_avg, min_rows, max_rows, import_date, result.bidder_id))
        else:
            # Insert new entry for this account + date
            cursor.execute("""
                INSERT INTO account_daily_upload_summary (
                    upload_date, bidder_id, total_uploads, successful_uploads, failed_uploads,
                    total_rows_written, total_file_size_bytes, avg_rows_per_upload,
                    min_rows, max_rows
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """, (import_date, result.bidder_id, is_success, is_failure, result.rows_imported,
                  file_size_bytes, result.rows_imported, result.rows_imported, result.rows_imported))

    except Exception as e:
        logger.warning(f"Failed to update account daily upload summary: {e}")


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
            FROM rtb_daily
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
