#!/usr/bin/env python3
"""Orchestrate the full data pipeline: CSV → Parquet → BigQuery → Postgres.

This script coordinates the complete data pipeline flow:
1. Export CSV to Parquet and upload to GCS
2. Load Parquet into BigQuery raw_facts table
3. Aggregate BigQuery data into Postgres UI tables

Usage:
    python scripts/run_pipeline.py --csv-path /path/to/report.csv --buyer-id 6634662463
    python scripts/run_pipeline.py --csv-path /path/to/report.csv --buyer-id 6634662463 --skip-aggregate

Environment Variables:
    RAW_PARQUET_BUCKET: GCS bucket for Parquet files
    BIGQUERY_PROJECT_ID: GCP project ID
    BIGQUERY_DATASET: BigQuery dataset name
    BIGQUERY_RAW_FACTS_TABLE: Raw facts table name (default: raw_facts)
    POSTGRES_DSN: PostgreSQL connection string
    GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline(
    csv_path: str,
    buyer_id: str,
    metric_date: Optional[str] = None,
    skip_parquet: bool = False,
    skip_bigquery: bool = False,
    skip_aggregate: bool = False,
) -> Dict[str, Any]:
    """Run the full pipeline for a CSV file.

    Args:
        csv_path: Path to the CSV file
        buyer_id: Buyer account ID
        metric_date: Date for the metrics (default: extracted from CSV)
        skip_parquet: Skip Parquet export step
        skip_bigquery: Skip BigQuery load step
        skip_aggregate: Skip Postgres aggregation step

    Returns:
        Dict with results from each pipeline step
    """
    result = {
        "csv_path": csv_path,
        "buyer_id": buyer_id,
        "steps": {},
        "success": True,
        "errors": [],
    }

    # Default metric_date to today if not specified
    if metric_date is None:
        metric_date = date.today().isoformat()

    result["metric_date"] = metric_date

    # Step 1: Export CSV to Parquet and upload to GCS
    gcs_uri = None
    if not skip_parquet:
        try:
            from scripts.export_csv_to_parquet import export_csv_to_parquet

            logger.info("Step 1: Exporting CSV to Parquet...")
            parquet_result = export_csv_to_parquet(
                input_path=csv_path,
                buyer_id=buyer_id,
                metric_date=metric_date,
            )
            result["steps"]["parquet"] = parquet_result
            gcs_uri = parquet_result.get("gcs_uri")

            if not gcs_uri:
                logger.warning("No GCS URI returned - Parquet export may have failed or bucket not configured")

        except Exception as e:
            error_msg = f"Parquet export failed: {e}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            result["success"] = False
            # Continue to try other steps
    else:
        logger.info("Step 1: Skipped (--skip-parquet)")
        result["steps"]["parquet"] = {"skipped": True}

    # Step 2: Load Parquet into BigQuery
    if not skip_bigquery and gcs_uri:
        try:
            from scripts.load_parquet_to_bigquery import load_parquet_to_bigquery

            logger.info("Step 2: Loading Parquet into BigQuery...")
            bq_result = load_parquet_to_bigquery(gcs_uri=gcs_uri)
            result["steps"]["bigquery"] = bq_result

        except Exception as e:
            error_msg = f"BigQuery load failed: {e}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            result["success"] = False
    elif skip_bigquery:
        logger.info("Step 2: Skipped (--skip-bigquery)")
        result["steps"]["bigquery"] = {"skipped": True}
    else:
        logger.info("Step 2: Skipped (no GCS URI from step 1)")
        result["steps"]["bigquery"] = {"skipped": True, "reason": "no_gcs_uri"}

    # Step 3: Aggregate to Postgres
    if not skip_aggregate:
        try:
            from scripts.bq_aggregate_to_pg import aggregate_date

            logger.info("Step 3: Aggregating BigQuery to Postgres...")
            agg_date = date.fromisoformat(metric_date)
            agg_result = aggregate_date(agg_date)
            result["steps"]["aggregate"] = agg_result

        except Exception as e:
            error_msg = f"Aggregation failed: {e}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            result["success"] = False
    else:
        logger.info("Step 3: Skipped (--skip-aggregate)")
        result["steps"]["aggregate"] = {"skipped": True}

    return result


def run_pipeline_batch(
    csv_paths: List[str],
    buyer_id: str,
    metric_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Run pipeline for multiple CSV files.

    This batches the aggregation step to run once after all CSVs are loaded.
    """
    results = {
        "files_processed": 0,
        "files_failed": 0,
        "file_results": [],
        "aggregation": None,
    }

    # Process each CSV (skip aggregation until all are done)
    for csv_path in csv_paths:
        logger.info(f"Processing: {csv_path}")
        result = run_pipeline(
            csv_path=csv_path,
            buyer_id=buyer_id,
            metric_date=metric_date,
            skip_aggregate=True,  # Batch aggregation at the end
        )
        results["file_results"].append(result)

        if result["success"]:
            results["files_processed"] += 1
        else:
            results["files_failed"] += 1

    # Run aggregation once for all dates
    if csv_paths:
        try:
            from scripts.bq_aggregate_to_pg import aggregate_date

            agg_date = date.fromisoformat(metric_date or date.today().isoformat())
            logger.info(f"Running aggregation for {agg_date}")
            results["aggregation"] = aggregate_date(agg_date)

        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            results["aggregation"] = {"error": str(e)}

    return results


def detect_metric_date_from_csv(csv_path: str) -> Optional[str]:
    """Try to extract metric date from CSV content."""
    import csv as csv_module

    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv_module.reader(f)
            headers = next(reader)

            # Find date column
            date_col_idx = None
            for i, header in enumerate(headers):
                if header.strip() in ("#Day", "Day", "Date"):
                    date_col_idx = i
                    break

            if date_col_idx is None:
                return None

            # Get first data row's date
            first_row = next(reader)
            date_value = first_row[date_col_idx].strip()

            # Try to parse date
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    parsed = datetime.strptime(date_value, fmt)
                    return parsed.date().isoformat()
                except ValueError:
                    continue

    except Exception as e:
        logger.warning(f"Could not detect date from CSV: {e}")

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the data pipeline: CSV → Parquet → BigQuery → Postgres"
    )
    parser.add_argument(
        "--csv-path", "-c",
        required=True,
        nargs="+",
        help="Path to CSV file(s)",
    )
    parser.add_argument(
        "--buyer-id", "-b",
        required=True,
        help="Buyer account ID",
    )
    parser.add_argument(
        "--date", "-d",
        help="Metric date (YYYY-MM-DD). Default: detected from CSV or today",
    )
    parser.add_argument(
        "--skip-parquet",
        action="store_true",
        help="Skip Parquet export step",
    )
    parser.add_argument(
        "--skip-bigquery",
        action="store_true",
        help="Skip BigQuery load step",
    )
    parser.add_argument(
        "--skip-aggregate",
        action="store_true",
        help="Skip Postgres aggregation step",
    )

    args = parser.parse_args()

    # Validate CSV paths
    for csv_path in args.csv_path:
        if not Path(csv_path).exists():
            logger.error(f"CSV file not found: {csv_path}")
            return 1

    # Detect or use provided date
    metric_date = args.date
    if not metric_date and len(args.csv_path) == 1:
        metric_date = detect_metric_date_from_csv(args.csv_path[0])
        if metric_date:
            logger.info(f"Detected metric date from CSV: {metric_date}")

    if not metric_date:
        metric_date = date.today().isoformat()
        logger.info(f"Using today's date: {metric_date}")

    try:
        if len(args.csv_path) == 1:
            # Single file
            result = run_pipeline(
                csv_path=args.csv_path[0],
                buyer_id=args.buyer_id,
                metric_date=metric_date,
                skip_parquet=args.skip_parquet,
                skip_bigquery=args.skip_bigquery,
                skip_aggregate=args.skip_aggregate,
            )

            print("\n" + "=" * 60)
            print("PIPELINE RESULTS")
            print("=" * 60)
            print(f"CSV:        {result['csv_path']}")
            print(f"Buyer ID:   {result['buyer_id']}")
            print(f"Date:       {result['metric_date']}")
            print(f"Success:    {'✓' if result['success'] else '✗'}")

            if result.get("steps", {}).get("parquet"):
                p = result["steps"]["parquet"]
                if not p.get("skipped"):
                    print(f"\nParquet Export:")
                    print(f"  Records:  {p.get('record_count', 'N/A')}")
                    print(f"  GCS URI:  {p.get('gcs_uri', 'N/A')}")

            if result.get("steps", {}).get("bigquery"):
                b = result["steps"]["bigquery"]
                if not b.get("skipped"):
                    print(f"\nBigQuery Load:")
                    print(f"  Rows:     {b.get('rows_loaded', 'N/A')}")
                    print(f"  Job ID:   {b.get('job_id', 'N/A')}")

            if result.get("steps", {}).get("aggregate"):
                a = result["steps"]["aggregate"]
                if not a.get("skipped"):
                    print(f"\nPostgres Aggregation:")
                    for table, count in a.items():
                        if count >= 0:
                            print(f"  {table}: {count} rows")

            if result.get("errors"):
                print(f"\nErrors:")
                for err in result["errors"]:
                    print(f"  - {err}")

            print("=" * 60)

            return 0 if result["success"] else 1

        else:
            # Multiple files
            result = run_pipeline_batch(
                csv_paths=args.csv_path,
                buyer_id=args.buyer_id,
                metric_date=metric_date,
            )

            print("\n" + "=" * 60)
            print("BATCH PIPELINE RESULTS")
            print("=" * 60)
            print(f"Files processed: {result['files_processed']}")
            print(f"Files failed:    {result['files_failed']}")

            if result.get("aggregation"):
                print(f"\nAggregation:")
                for table, count in result["aggregation"].items():
                    if isinstance(count, int) and count >= 0:
                        print(f"  {table}: {count} rows")

            print("=" * 60)

            return 0 if result["files_failed"] == 0 else 1

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
