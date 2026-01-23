#!/usr/bin/env python3
"""Load Parquet files from GCS into BigQuery.

This script loads Parquet files from Google Cloud Storage into the
BigQuery raw_facts table, creating the table if it doesn't exist.

Usage:
    python scripts/load_parquet_to_bigquery.py \
        --gcs-uri gs://bucket/raw/2026/01/23/6634662463/funnel_publishers.parquet

Environment Variables:
    BIGQUERY_PROJECT_ID: GCP project ID
    BIGQUERY_DATASET: BigQuery dataset name
    BIGQUERY_RAW_FACTS_TABLE: Table name (default: raw_facts)
    GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound
except ImportError:
    print("ERROR: google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# BigQuery schema for raw_facts table
RAW_FACTS_SCHEMA = [
    bigquery.SchemaField("event_timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("buyer_account_id", "STRING"),
    bigquery.SchemaField("report_type", "STRING"),
    bigquery.SchemaField("metric_date", "DATE"),
    bigquery.SchemaField("hour", "INT64"),
    bigquery.SchemaField("country", "STRING"),
    bigquery.SchemaField("publisher_id", "STRING"),
    bigquery.SchemaField("publisher_name", "STRING"),
    bigquery.SchemaField("creative_id", "STRING"),
    bigquery.SchemaField("creative_size", "STRING"),
    bigquery.SchemaField("creative_format", "STRING"),
    bigquery.SchemaField("billing_id", "STRING"),
    bigquery.SchemaField("bid_filtering_reason", "STRING"),
    bigquery.SchemaField("bid_requests", "INT64"),
    bigquery.SchemaField("inventory_matches", "INT64"),
    bigquery.SchemaField("successful_responses", "INT64"),
    bigquery.SchemaField("reached_queries", "INT64"),
    bigquery.SchemaField("bids", "INT64"),
    bigquery.SchemaField("bids_in_auction", "INT64"),
    bigquery.SchemaField("auctions_won", "INT64"),
    bigquery.SchemaField("impressions", "INT64"),
    bigquery.SchemaField("clicks", "INT64"),
    bigquery.SchemaField("spend_buyer_currency", "FLOAT64"),
    bigquery.SchemaField("spend_bidder_currency", "FLOAT64"),
    bigquery.SchemaField("active_view_viewable", "INT64"),
    bigquery.SchemaField("active_view_measurable", "INT64"),
    bigquery.SchemaField("gcs_source_uri", "STRING"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP"),
]


def get_bigquery_config() -> dict:
    """Get BigQuery configuration from environment."""
    project_id = os.getenv("BIGQUERY_PROJECT_ID")
    dataset = os.getenv("BIGQUERY_DATASET")
    table = os.getenv("BIGQUERY_RAW_FACTS_TABLE", "raw_facts")

    if not project_id:
        raise RuntimeError("BIGQUERY_PROJECT_ID environment variable must be set")
    if not dataset:
        raise RuntimeError("BIGQUERY_DATASET environment variable must be set")

    return {
        "project_id": project_id,
        "dataset": dataset,
        "table": table,
    }


def parse_gcs_uri(gcs_uri: str) -> dict:
    """Parse GCS URI to extract metadata.

    Expected format: gs://bucket/raw/YYYY/MM/DD/buyer_id/report_type.parquet
    """
    match = re.match(
        r"gs://([^/]+)/raw/(\d{4})/(\d{2})/(\d{2})/([^/]+)/([^.]+)\.parquet",
        gcs_uri
    )

    if not match:
        # Try alternative parsing for simpler paths
        simple_match = re.match(r"gs://([^/]+)/(.+)", gcs_uri)
        if simple_match:
            return {
                "bucket": simple_match.group(1),
                "path": simple_match.group(2),
                "metric_date": None,
                "buyer_id": None,
                "report_type": None,
            }
        raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

    bucket, year, month, day, buyer_id, report_type = match.groups()

    return {
        "bucket": bucket,
        "path": f"raw/{year}/{month}/{day}/{buyer_id}/{report_type}.parquet",
        "metric_date": f"{year}-{month}-{day}",
        "buyer_id": buyer_id,
        "report_type": report_type,
    }


def ensure_table_exists(
    client: bigquery.Client,
    table_ref: str,
) -> bigquery.Table:
    """Create the raw_facts table if it doesn't exist."""
    try:
        table = client.get_table(table_ref)
        logger.info(f"Table {table_ref} exists")
        return table
    except NotFound:
        logger.info(f"Creating table {table_ref}")

        table = bigquery.Table(table_ref)

        # Configure partitioning and clustering
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="metric_date",
        )
        # table.time_partitioning_old = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="event_timestamp",
        )
        table.clustering_fields = ["buyer_account_id", "report_type"]

        table = client.create_table(table)
        logger.info(f"Created table {table_ref}")
        return table


def load_parquet_to_bigquery(
    gcs_uri: str,
    project_id: Optional[str] = None,
    dataset: Optional[str] = None,
    table_name: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Load a Parquet file from GCS into BigQuery.

    Args:
        gcs_uri: GCS URI of the Parquet file
        project_id: GCP project ID (default: from env)
        dataset: BigQuery dataset name (default: from env)
        table_name: BigQuery table name (default: from env)
        dry_run: If True, validate but don't load

    Returns:
        Dict with load job details
    """
    # Get config
    config = get_bigquery_config()
    project_id = project_id or config["project_id"]
    dataset = dataset or config["dataset"]
    table_name = table_name or config["table"]

    # Parse GCS URI for metadata
    uri_info = parse_gcs_uri(gcs_uri)

    # Initialize client
    client = bigquery.Client(project=project_id)
    table_ref = f"{project_id}.{dataset}.{table_name}"

    # Ensure table exists
    ensure_table_exists(client, table_ref)

    if dry_run:
        return {
            "status": "dry_run",
            "gcs_uri": gcs_uri,
            "table": table_ref,
            "metadata": uri_info,
        }

    # Configure load job
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        # Schema mapping for Parquet files that may have different column names
        schema_update_options=[
            bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION,
        ],
    )

    # Load the file
    logger.info(f"Loading {gcs_uri} into {table_ref}")
    load_job = client.load_table_from_uri(
        gcs_uri,
        table_ref,
        job_config=job_config,
    )

    # Wait for job to complete
    load_job.result()

    # Get job stats
    result = {
        "status": "success",
        "job_id": load_job.job_id,
        "gcs_uri": gcs_uri,
        "table": table_ref,
        "rows_loaded": load_job.output_rows,
        "bytes_loaded": load_job.output_bytes,
        "metadata": uri_info,
    }

    logger.info(f"Loaded {result['rows_loaded']} rows from {gcs_uri}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load Parquet from GCS into BigQuery"
    )
    parser.add_argument(
        "--gcs-uri", "-u",
        required=True,
        help="GCS URI of the Parquet file (gs://bucket/path/file.parquet)",
    )
    parser.add_argument(
        "--project-id",
        help="GCP project ID (default: BIGQUERY_PROJECT_ID env var)",
    )
    parser.add_argument(
        "--dataset",
        help="BigQuery dataset (default: BIGQUERY_DATASET env var)",
    )
    parser.add_argument(
        "--table",
        help="BigQuery table (default: BIGQUERY_RAW_FACTS_TABLE env var or 'raw_facts')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without loading",
    )

    args = parser.parse_args()

    try:
        result = load_parquet_to_bigquery(
            gcs_uri=args.gcs_uri,
            project_id=args.project_id,
            dataset=args.dataset,
            table_name=args.table,
            dry_run=args.dry_run,
        )

        print(f"\nLoad {'would complete' if args.dry_run else 'complete'}:")
        print(f"  Status:       {result['status']}")
        print(f"  GCS URI:      {result['gcs_uri']}")
        print(f"  Table:        {result['table']}")
        if not args.dry_run:
            print(f"  Rows loaded:  {result.get('rows_loaded', 'N/A')}")
            print(f"  Job ID:       {result.get('job_id', 'N/A')}")

        return 0

    except Exception as e:
        logger.error(f"Load failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
