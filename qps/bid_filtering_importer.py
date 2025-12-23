"""Bid Filtering CSV Importer.

Imports bid filtering reason reports from Google Authorized Buyers
into the rtb_bid_filtering table.

This report answers: "WHY are bids being filtered?"
Detected by presence of "Bid filtering reason" column.

Usage:
    from qps.bid_filtering_importer import import_bid_filtering_csv

    result = import_bid_filtering_csv("/path/to/bid-filtering-report.csv")
"""

import csv
import sqlite3
import os
import hashlib
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from qps.csv_report_types import (
    ReportType, detect_report_type,
    BID_FILTERING_REQUIRED, BID_FILTERING_METRICS, BID_FILTERING_OPTIONAL
)

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")


@dataclass
class BidFilteringImportResult:
    """Result of Bid Filtering CSV import."""
    success: bool = False
    error_message: str = ""
    report_type: str = "bid_filtering"

    # Counts
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0

    # Data summary
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    unique_reasons: List[str] = field(default_factory=list)
    unique_countries: List[str] = field(default_factory=list)

    # Totals
    total_bids_filtered: int = 0
    total_bids_in_auction: int = 0

    # Metadata
    batch_id: str = ""
    columns_imported: List[str] = field(default_factory=list)
    bidder_id: Optional[str] = None

    # Errors
    errors: List[str] = field(default_factory=list)


def parse_date(date_str: str) -> str:
    """Parse date from various formats to YYYY-MM-DD."""
    if not date_str:
        return ""
    formats = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def parse_int(value) -> int:
    """Parse integer, returning 0 for empty/invalid."""
    if value is None or value == "":
        return 0
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def compute_bid_filtering_row_hash(row_data: Dict) -> str:
    """Compute hash of dimension values for deduplication."""
    keys = ["metric_date", "country", "buyer_account_id", "filtering_reason", "creative_id"]
    hash_input = "|".join(str(row_data.get(k, "")) for k in keys)
    return hashlib.md5(hash_input.encode()).hexdigest()


def import_bid_filtering_csv(
    csv_path: str,
    db_path: str = DB_PATH,
    bidder_id: Optional[str] = None,
) -> BidFilteringImportResult:
    """
    Import a Bid Filtering CSV into the rtb_bid_filtering table.

    Args:
        csv_path: Path to CSV file
        db_path: Database path
        bidder_id: Optional account ID to associate with this import

    Returns:
        BidFilteringImportResult with statistics
    """
    result = BidFilteringImportResult()
    result.batch_id = str(uuid.uuid4())[:8]
    result.bidder_id = bidder_id

    # Read and detect report type
    if not os.path.exists(csv_path):
        result.error_message = f"File not found: {csv_path}"
        return result

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
    except Exception as e:
        result.error_message = f"Failed to read CSV: {e}"
        return result

    # Detect report type
    detection = detect_report_type(header)

    if detection.report_type != ReportType.BID_FILTERING:
        result.error_message = (
            f"This CSV is not a Bid Filtering report. Detected: {detection.report_type.value}\n"
            f"Bid Filtering reports must have 'Bid filtering reason' column."
        )
        return result

    if detection.required_missing:
        result.error_message = f"Missing required columns: {', '.join(detection.required_missing)}"
        return result

    column_map = detection.columns_mapped
    result.columns_imported = list(column_map.keys())

    # Tracking sets
    reasons: Set[str] = set()
    countries: Set[str] = set()
    min_date: Optional[str] = None
    max_date: Optional[str] = None

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure table exists
    _ensure_bid_filtering_table(cursor)

    BATCH_SIZE = 1000
    batch: List[Tuple] = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                result.rows_read += 1

                try:
                    # Parse required fields
                    metric_date = parse_date(row.get(column_map.get("day", ""), ""))
                    filtering_reason = row.get(column_map.get("filtering_reason", ""), "").strip()

                    if not metric_date or not filtering_reason:
                        result.rows_skipped += 1
                        continue

                    # Track date range
                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date

                    # Parse optional fields
                    country = row.get(column_map.get("country", ""), "").strip() or None
                    buyer_account_id = row.get(column_map.get("buyer_account_id", ""), "").strip() or None
                    creative_id = row.get(column_map.get("creative_id", ""), "").strip() or None

                    # Metrics
                    bids = parse_int(row.get(column_map.get("bids", ""), 0))
                    bids_in_auction = parse_int(row.get(column_map.get("bids_in_auction", ""), 0))

                    # Opportunity cost (if available)
                    opportunity_cost_raw = row.get(column_map.get("opportunity_cost", ""), "0")
                    try:
                        opportunity_cost_micros = int(float(str(opportunity_cost_raw).replace(",", "").replace("$", "")) * 1_000_000)
                    except (ValueError, TypeError):
                        opportunity_cost_micros = 0

                    # Track stats
                    reasons.add(filtering_reason)
                    if country:
                        countries.add(country)
                    result.total_bids_filtered += bids
                    result.total_bids_in_auction += bids_in_auction

                    # Compute row hash for deduplication
                    row_data = {
                        "metric_date": metric_date,
                        "country": country,
                        "buyer_account_id": buyer_account_id,
                        "filtering_reason": filtering_reason,
                        "creative_id": creative_id,
                    }
                    row_hash = compute_bid_filtering_row_hash(row_data)

                    # Add to batch
                    batch.append((
                        metric_date, country, buyer_account_id, filtering_reason, creative_id,
                        bids, bids_in_auction, opportunity_cost_micros,
                        bidder_id, row_hash, result.batch_id
                    ))

                    # Insert batch
                    if len(batch) >= BATCH_SIZE:
                        imported, dupes = _insert_bid_filtering_batch(cursor, batch)
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
            imported, dupes = _insert_bid_filtering_batch(cursor, batch)
            result.rows_imported += imported
            result.rows_duplicate += dupes

        conn.commit()
        result.success = True

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")
        logger.error(f"Bid filtering import failed: {e}")

    finally:
        conn.close()

    # Populate result
    result.date_range_start = min_date
    result.date_range_end = max_date
    result.unique_reasons = sorted(list(reasons))
    result.unique_countries = sorted(list(countries))

    return result


def _ensure_bid_filtering_table(cursor):
    """Ensure rtb_bid_filtering table exists."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rtb_bid_filtering (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date DATE NOT NULL,
            country TEXT,
            buyer_account_id TEXT,
            filtering_reason TEXT NOT NULL,
            creative_id TEXT,
            bids INTEGER DEFAULT 0,
            bids_in_auction INTEGER DEFAULT 0,
            opportunity_cost_micros INTEGER DEFAULT 0,
            bidder_id TEXT,
            row_hash TEXT UNIQUE,
            import_batch_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bid_filtering_date ON rtb_bid_filtering(metric_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bid_filtering_reason ON rtb_bid_filtering(filtering_reason)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bid_filtering_country ON rtb_bid_filtering(country)")


def _insert_bid_filtering_batch(cursor, batch: List[Tuple]) -> Tuple[int, int]:
    """Insert batch of bid filtering rows. Returns (inserted, duplicates)."""
    inserted = 0
    duplicates = 0

    for row in batch:
        try:
            cursor.execute("""
                INSERT INTO rtb_bid_filtering (
                    metric_date, country, buyer_account_id, filtering_reason, creative_id,
                    bids, bids_in_auction, opportunity_cost_micros,
                    bidder_id, row_hash, import_batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)
            inserted += 1
        except sqlite3.IntegrityError:
            duplicates += 1

    return inserted, duplicates


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m qps.bid_filtering_importer <csv_file>")
        print("\nThis importer is for Bid Filtering CSVs (with Bid filtering reason column).")
        sys.exit(1)

    csv_path = sys.argv[1]

    print(f"Importing Bid Filtering CSV: {csv_path}")
    result = import_bid_filtering_csv(csv_path)

    if result.success:
        print(f"\n✅ IMPORT COMPLETE ({result.report_type})")
        print(f"  Rows read:          {result.rows_read:,}")
        print(f"  Rows imported:      {result.rows_imported:,}")
        print(f"  Rows duplicate:     {result.rows_duplicate:,}")
        print(f"  Date range:         {result.date_range_start} to {result.date_range_end}")
        print(f"  Unique reasons:     {len(result.unique_reasons)}")
        print(f"  Unique countries:   {len(result.unique_countries)}")
        print(f"  Total bids filtered: {result.total_bids_filtered:,}")
    else:
        print(f"\n❌ IMPORT FAILED: {result.error_message}")
        sys.exit(1)
