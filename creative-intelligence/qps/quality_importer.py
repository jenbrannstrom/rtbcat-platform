"""Quality Signals CSV Importer.

Imports quality signals (fraud/viewability) reports from Google Authorized Buyers
into the rtb_quality table.

This report answers: "Which publishers have fraud or low viewability?"
Detected by presence of "IVT credited impressions" or "Pre-filtered impressions" columns.

Usage:
    from qps.quality_importer import import_quality_csv

    result = import_quality_csv("/path/to/quality-report.csv")
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
    QUALITY_SIGNALS_REQUIRED, QUALITY_SIGNALS_METRICS, QUALITY_SIGNALS_OPTIONAL
)

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")


@dataclass
class QualityImportResult:
    """Result of Quality Signals CSV import."""
    success: bool = False
    error_message: str = ""
    report_type: str = "quality_signals"

    # Counts
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0

    # Data summary
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    unique_publishers: List[str] = field(default_factory=list)
    unique_countries: List[str] = field(default_factory=list)

    # Totals
    total_impressions: int = 0
    total_ivt_credited: int = 0
    total_viewable: int = 0
    total_measurable: int = 0

    # Quality metrics
    overall_ivt_rate_pct: float = 0.0
    overall_viewability_pct: float = 0.0

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


def compute_quality_row_hash(row_data: Dict) -> str:
    """Compute hash of dimension values for deduplication."""
    keys = ["metric_date", "publisher_id", "country"]
    hash_input = "|".join(str(row_data.get(k, "")) for k in keys)
    return hashlib.md5(hash_input.encode()).hexdigest()


def import_quality_csv(
    csv_path: str,
    db_path: str = DB_PATH,
    bidder_id: Optional[str] = None,
) -> QualityImportResult:
    """
    Import a Quality Signals CSV into the rtb_quality table.

    Args:
        csv_path: Path to CSV file
        db_path: Database path
        bidder_id: Optional account ID to associate with this import

    Returns:
        QualityImportResult with statistics
    """
    result = QualityImportResult()
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

    if detection.report_type != ReportType.QUALITY_SIGNALS:
        result.error_message = (
            f"This CSV is not a Quality Signals report. Detected: {detection.report_type.value}\n"
            f"Quality Signals reports must have 'IVT credited impressions' or 'Pre-filtered impressions' column."
        )
        return result

    if detection.required_missing:
        result.error_message = f"Missing required columns: {', '.join(detection.required_missing)}"
        return result

    column_map = detection.columns_mapped
    result.columns_imported = list(column_map.keys())

    # Tracking sets
    publishers: Set[str] = set()
    countries: Set[str] = set()
    min_date: Optional[str] = None
    max_date: Optional[str] = None

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure table exists
    _ensure_quality_table(cursor)

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
                    publisher_id = row.get(column_map.get("publisher_id", ""), "").strip()

                    if not metric_date or not publisher_id:
                        result.rows_skipped += 1
                        continue

                    # Track date range
                    if min_date is None or metric_date < min_date:
                        min_date = metric_date
                    if max_date is None or metric_date > max_date:
                        max_date = metric_date

                    # Parse optional fields
                    publisher_name = row.get(column_map.get("publisher_name", ""), "").strip() or None
                    country = row.get(column_map.get("country", ""), "").strip() or None

                    # Metrics
                    impressions = parse_int(row.get(column_map.get("impressions", ""), 0))
                    pre_filtered_impressions = parse_int(row.get(column_map.get("pre_filtered_impressions", ""), 0))
                    ivt_credited_impressions = parse_int(row.get(column_map.get("ivt_credited_impressions", ""), 0))
                    billed_impressions = parse_int(row.get(column_map.get("billed_impressions", ""), 0))
                    measurable_impressions = parse_int(row.get(column_map.get("measurable_impressions", ""), 0))
                    viewable_impressions = parse_int(row.get(column_map.get("viewable_impressions", ""), 0))

                    # Calculate rates
                    ivt_rate_pct = (ivt_credited_impressions / impressions * 100) if impressions > 0 else 0.0
                    viewability_pct = (viewable_impressions / measurable_impressions * 100) if measurable_impressions > 0 else 0.0

                    # Track stats
                    publishers.add(publisher_id)
                    if country:
                        countries.add(country)
                    result.total_impressions += impressions
                    result.total_ivt_credited += ivt_credited_impressions
                    result.total_viewable += viewable_impressions
                    result.total_measurable += measurable_impressions

                    # Compute row hash for deduplication
                    row_data = {
                        "metric_date": metric_date,
                        "publisher_id": publisher_id,
                        "country": country,
                    }
                    row_hash = compute_quality_row_hash(row_data)

                    # Add to batch
                    batch.append((
                        metric_date, publisher_id, publisher_name, country,
                        impressions, pre_filtered_impressions, ivt_credited_impressions,
                        billed_impressions, measurable_impressions, viewable_impressions,
                        ivt_rate_pct, viewability_pct,
                        bidder_id, row_hash, result.batch_id
                    ))

                    # Insert batch
                    if len(batch) >= BATCH_SIZE:
                        imported, dupes = _insert_quality_batch(cursor, batch)
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
            imported, dupes = _insert_quality_batch(cursor, batch)
            result.rows_imported += imported
            result.rows_duplicate += dupes

        conn.commit()
        result.success = True

    except Exception as e:
        result.error_message = str(e)
        result.errors.append(f"Fatal: {e}")
        logger.error(f"Quality import failed: {e}")

    finally:
        conn.close()

    # Populate result
    result.date_range_start = min_date
    result.date_range_end = max_date
    result.unique_publishers = sorted(list(publishers))
    result.unique_countries = sorted(list(countries))

    # Calculate overall rates
    if result.total_impressions > 0:
        result.overall_ivt_rate_pct = result.total_ivt_credited / result.total_impressions * 100
    if result.total_measurable > 0:
        result.overall_viewability_pct = result.total_viewable / result.total_measurable * 100

    return result


def _ensure_quality_table(cursor):
    """Ensure rtb_quality table exists."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rtb_quality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date DATE NOT NULL,
            publisher_id TEXT NOT NULL,
            publisher_name TEXT,
            country TEXT,
            impressions INTEGER DEFAULT 0,
            pre_filtered_impressions INTEGER DEFAULT 0,
            ivt_credited_impressions INTEGER DEFAULT 0,
            billed_impressions INTEGER DEFAULT 0,
            measurable_impressions INTEGER DEFAULT 0,
            viewable_impressions INTEGER DEFAULT 0,
            ivt_rate_pct REAL,
            viewability_pct REAL,
            bidder_id TEXT,
            row_hash TEXT UNIQUE,
            import_batch_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_date ON rtb_quality(metric_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_publisher ON rtb_quality(publisher_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_country ON rtb_quality(country)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_ivt_rate ON rtb_quality(ivt_rate_pct)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_viewability ON rtb_quality(viewability_pct)")


def _insert_quality_batch(cursor, batch: List[Tuple]) -> Tuple[int, int]:
    """Insert batch of quality rows. Returns (inserted, duplicates)."""
    inserted = 0
    duplicates = 0

    for row in batch:
        try:
            cursor.execute("""
                INSERT INTO rtb_quality (
                    metric_date, publisher_id, publisher_name, country,
                    impressions, pre_filtered_impressions, ivt_credited_impressions,
                    billed_impressions, measurable_impressions, viewable_impressions,
                    ivt_rate_pct, viewability_pct,
                    bidder_id, row_hash, import_batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        print("Usage: python -m qps.quality_importer <csv_file>")
        print("\nThis importer is for Quality Signals CSVs (with IVT/viewability columns).")
        sys.exit(1)

    csv_path = sys.argv[1]

    print(f"Importing Quality Signals CSV: {csv_path}")
    result = import_quality_csv(csv_path)

    if result.success:
        print(f"\n✅ IMPORT COMPLETE ({result.report_type})")
        print(f"  Rows read:            {result.rows_read:,}")
        print(f"  Rows imported:        {result.rows_imported:,}")
        print(f"  Rows duplicate:       {result.rows_duplicate:,}")
        print(f"  Date range:           {result.date_range_start} to {result.date_range_end}")
        print(f"  Unique publishers:    {len(result.unique_publishers)}")
        print(f"  Unique countries:     {len(result.unique_countries)}")
        print(f"  Total impressions:    {result.total_impressions:,}")
        print(f"  Overall IVT rate:     {result.overall_ivt_rate_pct:.2f}%")
        print(f"  Overall viewability:  {result.overall_viewability_pct:.2f}%")
    else:
        print(f"\n❌ IMPORT FAILED: {result.error_message}")
        sys.exit(1)
