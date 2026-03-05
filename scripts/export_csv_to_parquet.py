#!/usr/bin/env python3
"""Export CSV file to Parquet format and upload to GCS.

This script converts RTB report CSVs to Parquet files and uploads them
to Google Cloud Storage for BigQuery ingestion.

Usage:
    python scripts/export_csv_to_parquet.py \
        --input /path/to/report.csv \
        --buyer-id 3333333333 \
        --date 2026-01-23 \
        --report-type funnel_publishers

Environment Variables:
    RAW_PARQUET_BUCKET: GCS bucket name for Parquet files
    GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    print("ERROR: pyarrow not installed. Run: pip install pyarrow")
    sys.exit(1)

try:
    from google.cloud import storage
except ImportError:
    print("ERROR: google-cloud-storage not installed. Run: pip install google-cloud-storage")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Schema definitions for different report types
SCHEMAS = {
    "funnel_publishers": pa.schema([
        ("metric_date", pa.date32()),
        ("hour", pa.int64()),
        ("country", pa.string()),
        ("publisher_id", pa.string()),
        ("publisher_name", pa.string()),
        ("buyer_account_id", pa.string()),
        ("bid_requests", pa.int64()),
        ("inventory_matches", pa.int64()),
        ("successful_responses", pa.int64()),
        ("reached_queries", pa.int64()),
        ("bids", pa.int64()),
        ("bids_in_auction", pa.int64()),
        ("auctions_won", pa.int64()),
        ("impressions", pa.int64()),
        ("clicks", pa.int64()),
        ("report_type", pa.string()),
    ]),
    "funnel_geo": pa.schema([
        ("metric_date", pa.date32()),
        ("hour", pa.int64()),
        ("country", pa.string()),
        ("buyer_account_id", pa.string()),
        ("bid_requests", pa.int64()),
        ("inventory_matches", pa.int64()),
        ("successful_responses", pa.int64()),
        ("bids", pa.int64()),
        ("bids_in_auction", pa.int64()),
        ("auctions_won", pa.int64()),
        ("impressions", pa.int64()),
        ("clicks", pa.int64()),
        ("report_type", pa.string()),
    ]),
    "bid_filtering": pa.schema([
        ("metric_date", pa.date32()),
        ("country", pa.string()),
        ("creative_id", pa.string()),
        ("buyer_account_id", pa.string()),
        ("bid_filtering_reason", pa.string()),
        ("bids", pa.int64()),
        ("report_type", pa.string()),
    ]),
    "quality": pa.schema([
        ("metric_date", pa.date32()),
        ("billing_id", pa.string()),
        ("creative_id", pa.string()),
        ("creative_size", pa.string()),
        ("creative_format", pa.string()),
        ("buyer_account_id", pa.string()),
        ("reached_queries", pa.int64()),
        ("impressions", pa.int64()),
        ("spend_buyer_currency", pa.float64()),
        ("active_view_viewable", pa.int64()),
        ("active_view_measurable", pa.int64()),
        ("report_type", pa.string()),
    ]),
    "bidsinauction": pa.schema([
        ("metric_date", pa.date32()),
        ("country", pa.string()),
        ("creative_id", pa.string()),
        ("buyer_account_id", pa.string()),
        ("bids_in_auction", pa.int64()),
        ("auctions_won", pa.int64()),
        ("bids", pa.int64()),
        ("reached_queries", pa.int64()),
        ("impressions", pa.int64()),
        ("spend_buyer_currency", pa.float64()),
        ("spend_bidder_currency", pa.float64()),
        ("report_type", pa.string()),
    ]),
}

# Column name mappings from CSV headers to schema fields
def normalize_header(header: str) -> str:
    """Normalize header names for mapping/detection."""
    return header.strip().lstrip("#").strip()


COLUMN_MAPPINGS = {
    "#Day": "metric_date",
    "#Buyer account ID": "buyer_account_id",
    "Day": "metric_date",
    "Hour": "hour",
    "Country": "country",
    "Publisher ID": "publisher_id",
    "Publisher id": "publisher_id",
    "Publisher name": "publisher_name",
    "Publisher Name": "publisher_name",
    "Buyer account ID": "buyer_account_id",
    "Buyer Account ID": "buyer_account_id",
    "Bid requests": "bid_requests",
    "Inventory matches": "inventory_matches",
    "Successful responses": "successful_responses",
    "Reached queries": "reached_queries",
    "Bids": "bids",
    "Bids in auction": "bids_in_auction",
    "Auctions won": "auctions_won",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Creative ID": "creative_id",
    "Creative id": "creative_id",
    "Bid filtering reason": "bid_filtering_reason",
    "Billing ID": "billing_id",
    "Billing id": "billing_id",
    "Creative size": "creative_size",
    "Creative format": "creative_format",
    "Spend (buyer currency)": "spend_buyer_currency",
    "Spend (bidder currency)": "spend_bidder_currency",
    "Active view viewable": "active_view_viewable",
    "Active view measurable": "active_view_measurable",
}


def detect_report_type(headers: List[str]) -> str:
    """Detect report type from CSV headers."""
    header_set = {normalize_header(h) for h in headers}

    if "Publisher ID" in header_set or "Publisher id" in header_set:
        return "funnel_publishers"
    if "Bid filtering reason" in header_set:
        return "bid_filtering"
    if "Creative format" in header_set and "Billing ID" in header_set:
        return "quality"
    if "Spend (buyer currency)" in header_set and "Creative ID" in header_set:
        return "bidsinauction"
    if "Country" in header_set and "Bid requests" in header_set:
        return "funnel_geo"

    raise ValueError(f"Unable to detect report type from headers: {headers}")


def normalize_value(value: str, field_type: pa.DataType, buyer_id: Optional[str] = None) -> Any:
    """Normalize a CSV value to the appropriate PyArrow type."""
    if value is None or value.strip() == "":
        return None

    value = value.strip()

    if pa.types.is_date32(field_type):
        # Handle various date formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unable to parse date: {value}")

    if pa.types.is_int64(field_type):
        # Remove commas, currency symbols, and whitespace
        cleaned = value.replace(",", "").replace(" ", "").replace("$", "").replace("€", "").replace("£", "")
        return int(float(cleaned)) if "." in cleaned else int(cleaned)

    if pa.types.is_float64(field_type):
        # Remove commas, currency symbols, and whitespace
        cleaned = value.replace(",", "").replace(" ", "").replace("$", "").replace("€", "").replace("£", "")
        return float(cleaned)

    if pa.types.is_string(field_type):
        return value

    return value


def parse_csv_to_records(
    csv_path: str,
    buyer_id: str,
    report_type: Optional[str] = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """Parse CSV file and return records with normalized values."""
    records = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        # Read header
        reader = csv.reader(f)
        headers = next(reader)

        # Detect report type if not specified
        if report_type is None:
            report_type = detect_report_type(headers)
            logger.info(f"Detected report type: {report_type}")

        schema = SCHEMAS.get(report_type)
        if schema is None:
            raise ValueError(f"Unknown report type: {report_type}")

        # Build column index mapping
        col_mapping = {}
        for i, header in enumerate(headers):
            normalized = normalize_header(header)
            field_name = COLUMN_MAPPINGS.get(normalized) or COLUMN_MAPPINGS.get(header.strip())
            if field_name and field_name in schema.names:
                col_mapping[i] = field_name

        # Parse rows
        for row_num, row in enumerate(reader, start=2):
            if not row or all(cell.strip() == "" for cell in row):
                continue

            try:
                record = {"buyer_account_id": buyer_id}

                for i, cell in enumerate(row):
                    if i in col_mapping:
                        field_name = col_mapping[i]
                        field_idx = schema.get_field_index(field_name)
                        field_type = schema.field(field_idx).type
                        record[field_name] = normalize_value(cell, field_type, buyer_id)

                # Fill missing fields with None
                for field in schema:
                    if field.name not in record:
                        record[field.name] = None

                # Set report_type from detected type
                record["report_type"] = report_type

                records.append(record)

            except Exception as e:
                logger.warning(f"Error parsing row {row_num}: {e}")
                continue

    return report_type, records


def write_parquet(
    records: List[Dict[str, Any]],
    schema: pa.Schema,
    output_path: str,
) -> None:
    """Write records to a Parquet file."""
    if not records:
        raise ValueError("No records to write")

    table = pa.Table.from_pylist(records, schema=schema)
    pq.write_table(table, output_path, compression="snappy")
    logger.info(f"Wrote {len(records)} records to {output_path}")


def upload_to_gcs(
    local_path: str,
    bucket_name: str,
    gcs_path: str,
) -> str:
    """Upload a file to GCS and return the gs:// URI."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)

    blob.upload_from_filename(local_path)
    gcs_uri = f"gs://{bucket_name}/{gcs_path}"
    logger.info(f"Uploaded to {gcs_uri}")

    return gcs_uri


def build_gcs_path(
    metric_date: date,
    buyer_id: str,
    report_type: str,
) -> str:
    """Build the GCS path for a Parquet file."""
    return f"raw/{metric_date.year:04d}/{metric_date.month:02d}/{metric_date.day:02d}/{buyer_id}/{report_type}.parquet"


def export_csv_to_parquet(
    input_path: str,
    buyer_id: str,
    metric_date: str,
    bucket: Optional[str] = None,
    report_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Export a CSV file to Parquet and optionally upload to GCS.

    Returns:
        Dict with keys: local_path, gcs_uri (if uploaded), report_type, record_count
    """
    bucket = bucket or os.getenv("RAW_PARQUET_BUCKET")

    # Parse metric_date
    if isinstance(metric_date, str):
        metric_date = date.fromisoformat(metric_date)

    # Parse CSV
    detected_type, records = parse_csv_to_records(input_path, buyer_id, report_type)
    report_type = detected_type

    if not records:
        raise ValueError("No valid records found in CSV")

    # Get schema
    schema = SCHEMAS[report_type]

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        local_path = tmp.name

    write_parquet(records, schema, local_path)

    result = {
        "local_path": local_path,
        "report_type": report_type,
        "record_count": len(records),
        "gcs_uri": None,
    }

    # Upload to GCS if bucket specified
    if bucket:
        gcs_path = build_gcs_path(metric_date, buyer_id, report_type)
        result["gcs_uri"] = upload_to_gcs(local_path, bucket, gcs_path)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export CSV to Parquet and upload to GCS"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input CSV file",
    )
    parser.add_argument(
        "--buyer-id", "-b",
        required=True,
        help="Buyer account ID",
    )
    parser.add_argument(
        "--date", "-d",
        required=True,
        help="Metric date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--bucket",
        help="GCS bucket name (default: RAW_PARQUET_BUCKET env var)",
    )
    parser.add_argument(
        "--report-type", "-t",
        choices=list(SCHEMAS.keys()),
        help="Report type (auto-detected if not specified)",
    )

    args = parser.parse_args()

    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    try:
        result = export_csv_to_parquet(
            input_path=args.input,
            buyer_id=args.buyer_id,
            metric_date=args.date,
            bucket=args.bucket,
            report_type=args.report_type,
        )

        print(f"\nExport complete:")
        print(f"  Report type:   {result['report_type']}")
        print(f"  Record count:  {result['record_count']}")
        print(f"  Local path:    {result['local_path']}")
        if result["gcs_uri"]:
            print(f"  GCS URI:       {result['gcs_uri']}")

        return 0

    except Exception as e:
        logger.error(f"Export failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
