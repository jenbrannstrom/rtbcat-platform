"""RTB Funnel CSV Importer.

Imports the RTB Funnel CSV reports (with bid_requests, bids, auctions_won)
into the rtb_funnel table.

These reports are SEPARATE from the Performance Detail CSVs because Google AB
does not allow bid_requests with creative/app dimensions.

Usage:
    from qps.funnel_importer import import_funnel_csv

    result = import_funnel_csv("/path/to/catscan-funnel-geo.csv")
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
    RTB_FUNNEL_REQUIRED, RTB_FUNNEL_PIPELINE_METRICS, RTB_FUNNEL_OPTIONAL
)

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")


@dataclass
class FunnelImportResult:
    """Result of RTB Funnel CSV import."""
    success: bool = False
    error_message: str = ""
    report_type: str = ""  # "rtb_funnel_geo" or "rtb_funnel_publisher"

    # Counts
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0

    # Data summary
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    unique_countries: List[str] = field(default_factory=list)
    unique_publishers: List[str] = field(default_factory=list)

    # Totals
    total_bid_requests: int = 0
    total_reached: int = 0
    total_impressions: int = 0
    total_auctions_won: int = 0

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


def compute_funnel_row_hash(row_data: Dict) -> str:
    """Compute hash of dimension values for deduplication."""
    keys = ["metric_date", "country", "hour", "buyer_account_id", "publisher_id",
            "platform", "environment", "transaction_type"]
    hash_input = "|".join(str(row_data.get(k, "")) for k in keys)
    return hashlib.md5(hash_input.encode()).hexdigest()


def import_funnel_csv(
    csv_path: str,
    db_path: str = DB_PATH,
    bidder_id: Optional[str] = None,
) -> FunnelImportResult:
    """
    Import an RTB Funnel CSV into the rtb_funnel table.

    Automatically detects whether it's a geo-only or publisher funnel report.

    Args:
        csv_path: Path to CSV file
        db_path: Database path
        bidder_id: Optional account ID to associate with this import

    Returns:
        FunnelImportResult with statistics
    """
    result = FunnelImportResult()
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

    if detection.report_type not in [ReportType.RTB_FUNNEL_GEO, ReportType.RTB_FUNNEL_PUBLISHER]:
        result.error_message = (
            f"This CSV is not an RTB Funnel report. Detected: {detection.report_type.value}\n"
            f"RTB Funnel reports must have 'Bid requests' column.\n"
            f"For Performance Detail CSVs (with Creative ID), use the regular importer."
        )
        return result

    if detection.required_missing:
        result.error_message = f"Missing required columns: {', '.join(detection.required_missing)}"
        return result

    result.report_type = detection.report_type.value
    column_map = detection.columns_mapped
    result.columns_imported = list(column_map.keys())

    # Tracking sets
    countries: Set[str] = set()
    publishers: Set[str] = set()
    min_date: Optional[str] = None
    max_date: Optional[str] = None

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure table exists (run migration if needed)
    _ensure_funnel_table(cursor)

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
                    country = row.get(column_map.get("country", ""), "").strip()
                    bid_requests = parse_int(row.get(column_map.get("bid_requests", ""), 0))
                    reached_queries = parse_int(row.get(column_map.get("reached_queries", ""), 0))

                    if not metric_date or not country:
                        result.rows_skipped += 1
                        continue

                    # Track date range
                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date

                    # Parse optional/pipeline fields
                    hour = parse_int(row.get(column_map.get("hour", ""), "")) if "hour" in column_map else None
                    buyer_account_id = row.get(column_map.get("buyer_account_id", ""), "").strip() or None

                    publisher_id = row.get(column_map.get("publisher_id", ""), "").strip() or None
                    publisher_name = row.get(column_map.get("publisher_name", ""), "").strip() or None

                    # NEW: Platform/Environment/Transaction type
                    platform = row.get(column_map.get("platform", ""), "").strip() or None
                    environment = row.get(column_map.get("environment", ""), "").strip() or None
                    transaction_type = row.get(column_map.get("transaction_type", ""), "").strip() or None

                    # Pipeline metrics
                    inventory_matches = parse_int(row.get(column_map.get("inventory_matches", ""), 0))
                    successful_responses = parse_int(row.get(column_map.get("successful_responses", ""), 0))
                    bids = parse_int(row.get(column_map.get("bids", ""), 0))
                    bids_in_auction = parse_int(row.get(column_map.get("bids_in_auction", ""), 0))
                    auctions_won = parse_int(row.get(column_map.get("auctions_won", ""), 0))
                    impressions = parse_int(row.get(column_map.get("impressions", ""), 0))
                    clicks = parse_int(row.get(column_map.get("clicks", ""), 0))

                    # Track stats
                    countries.add(country)
                    if publisher_id:
                        publishers.add(publisher_id)

                    result.total_bid_requests += bid_requests
                    result.total_reached += reached_queries
                    result.total_impressions += impressions
                    result.total_auctions_won += auctions_won

                    # Compute row hash for deduplication
                    row_data = {
                        "metric_date": metric_date,
                        "country": country,
                        "hour": hour,
                        "buyer_account_id": buyer_account_id,
                        "publisher_id": publisher_id,
                        "platform": platform,
                        "environment": environment,
                        "transaction_type": transaction_type,
                    }
                    row_hash = compute_funnel_row_hash(row_data)

                    # Add to batch (includes new platform/environment/transaction_type)
                    batch.append((
                        metric_date, hour, country, buyer_account_id,
                        publisher_id, publisher_name,
                        platform, environment, transaction_type,
                        inventory_matches, bid_requests, successful_responses,
                        reached_queries, bids, bids_in_auction, auctions_won,
                        impressions, clicks,
                        bidder_id, row_hash, result.batch_id, result.report_type
                    ))

                    # Insert batch
                    if len(batch) >= BATCH_SIZE:
                        imported, dupes = _insert_funnel_batch(cursor, batch)
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
            imported, dupes = _insert_funnel_batch(cursor, batch)
            result.rows_imported += imported
            result.rows_duplicate += dupes

        conn.commit()
        result.success = True

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")
        logger.error(f"Funnel import failed: {e}")

    finally:
        conn.close()

    # Populate result
    result.date_range_start = min_date
    result.date_range_end = max_date
    result.unique_countries = sorted(list(countries))
    result.unique_publishers = sorted(list(publishers))

    return result


def _ensure_funnel_table(cursor):
    """Ensure rtb_funnel table exists with all required columns."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rtb_funnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date DATE NOT NULL,
            hour INTEGER,
            country TEXT NOT NULL,
            buyer_account_id TEXT,
            publisher_id TEXT,
            publisher_name TEXT,
            platform TEXT,
            environment TEXT,
            transaction_type TEXT,
            inventory_matches INTEGER DEFAULT 0,
            bid_requests INTEGER DEFAULT 0,
            successful_responses INTEGER DEFAULT 0,
            reached_queries INTEGER DEFAULT 0,
            bids INTEGER DEFAULT 0,
            bids_in_auction INTEGER DEFAULT 0,
            auctions_won INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            bidder_id TEXT,
            row_hash TEXT UNIQUE,
            import_batch_id TEXT,
            report_type TEXT DEFAULT 'funnel',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_funnel_date ON rtb_funnel(metric_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_funnel_country ON rtb_funnel(country)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_funnel_date_country ON rtb_funnel(metric_date, country)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_funnel_platform ON rtb_funnel(platform)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rtb_funnel_environment ON rtb_funnel(environment)")


def _insert_funnel_batch(cursor, batch: List[Tuple]) -> Tuple[int, int]:
    """Insert batch of funnel rows. Returns (inserted, duplicates)."""
    inserted = 0
    duplicates = 0

    for row in batch:
        try:
            cursor.execute("""
                INSERT INTO rtb_funnel (
                    metric_date, hour, country, buyer_account_id,
                    publisher_id, publisher_name,
                    platform, environment, transaction_type,
                    inventory_matches, bid_requests, successful_responses,
                    reached_queries, bids, bids_in_auction, auctions_won,
                    impressions, clicks,
                    bidder_id, row_hash, import_batch_id, report_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        print("Usage: python -m qps.funnel_importer <csv_file>")
        print("\nThis importer is for RTB Funnel CSVs (with Bid requests column).")
        print("For Performance Detail CSVs (with Creative ID), use: python -m qps.importer")
        sys.exit(1)

    csv_path = sys.argv[1]

    print(f"Importing RTB Funnel CSV: {csv_path}")
    result = import_funnel_csv(csv_path)

    if result.success:
        print(f"\n✅ IMPORT COMPLETE ({result.report_type})")
        print(f"  Rows read:          {result.rows_read:,}")
        print(f"  Rows imported:      {result.rows_imported:,}")
        print(f"  Rows duplicate:     {result.rows_duplicate:,}")
        print(f"  Date range:         {result.date_range_start} to {result.date_range_end}")
        print(f"  Unique countries:   {len(result.unique_countries)}")
        if result.unique_publishers:
            print(f"  Unique publishers:  {len(result.unique_publishers)}")
        print(f"  Total bid requests: {result.total_bid_requests:,}")
        print(f"  Total reached:      {result.total_reached:,}")
        print(f"  Total auctions won: {result.total_auctions_won:,}")
    else:
        print(f"\n❌ IMPORT FAILED: {result.error_message}")
        sys.exit(1)
