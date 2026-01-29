#!/usr/bin/env python3
"""Aggregate data from BigQuery and write to Postgres UI tables.

This script runs aggregation queries on BigQuery raw_facts table and
writes the results to Postgres home_* tables for dashboard display.

Usage:
    python scripts/bq_aggregate_to_pg.py --date 2026-01-23
    python scripts/bq_aggregate_to_pg.py --date-range 2026-01-01 2026-01-31

Environment Variables:
    BIGQUERY_PROJECT_ID: GCP project ID
    BIGQUERY_DATASET: BigQuery dataset name
    POSTGRES_DSN: PostgreSQL connection string
    GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from google.cloud import bigquery
except ImportError:
    print("ERROR: google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery")
    sys.exit(1)

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install psycopg[binary]")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Aggregation query templates
# These query BigQuery tables and return aggregated results

AGG_QUERIES = {
    # NOTE: Most queries use raw_facts, but home_size_daily and home_config_daily
    # use rtb_daily which has creative_size and billing_id columns

    "home_publisher_daily": """
        SELECT
            metric_date as metric_date,
            buyer_account_id,
            publisher_id,
            MAX(publisher_name) as publisher_name,
            SUM(COALESCE(reached_queries, 0)) as reached_queries,
            SUM(COALESCE(impressions, 0)) as impressions,
            SUM(COALESCE(bids, 0)) as bids,
            SUM(COALESCE(successful_responses, 0)) as successful_responses,
            SUM(COALESCE(bid_requests, 0)) as bid_requests,
            SUM(COALESCE(auctions_won, 0)) as auctions_won
        FROM `{project}.{dataset}.raw_facts`
        WHERE metric_date = @metric_date
          AND publisher_id IS NOT NULL
        GROUP BY metric_date, buyer_account_id, publisher_id
    """,

    "home_geo_daily": """
        SELECT
            metric_date as metric_date,
            buyer_account_id,
            country,
            SUM(COALESCE(reached_queries, 0)) as reached_queries,
            SUM(COALESCE(impressions, 0)) as impressions,
            SUM(COALESCE(bids, 0)) as bids,
            SUM(COALESCE(successful_responses, 0)) as successful_responses,
            SUM(COALESCE(bid_requests, 0)) as bid_requests,
            SUM(COALESCE(auctions_won, 0)) as auctions_won
        FROM `{project}.{dataset}.raw_facts`
        WHERE metric_date = @metric_date
          AND country IS NOT NULL
        GROUP BY metric_date, buyer_account_id, country
    """,

    "home_size_daily": """
        SELECT
            metric_date as metric_date,
            buyer_account_id,
            creative_size,
            SUM(COALESCE(reached_queries, 0)) as reached_queries,
            SUM(COALESCE(impressions, 0)) as impressions
        FROM `{project}.{dataset}.rtb_daily`
        WHERE metric_date = @metric_date
          AND creative_size IS NOT NULL
        GROUP BY metric_date, buyer_account_id, creative_size
    """,

    "home_seat_daily": """
        SELECT
            metric_date as metric_date,
            buyer_account_id,
            SUM(COALESCE(reached_queries, 0)) as reached_queries,
            SUM(COALESCE(impressions, 0)) as impressions,
            SUM(COALESCE(bids, 0)) as bids,
            SUM(COALESCE(successful_responses, 0)) as successful_responses,
            SUM(COALESCE(bid_requests, 0)) as bid_requests,
            SUM(COALESCE(auctions_won, 0)) as auctions_won
        FROM `{project}.{dataset}.raw_facts`
        WHERE metric_date = @metric_date
        GROUP BY metric_date, buyer_account_id
    """,

    "home_config_daily": """
        SELECT
            metric_date as metric_date,
            buyer_account_id,
            billing_id,
            SUM(COALESCE(reached_queries, 0)) as reached_queries,
            SUM(COALESCE(impressions, 0)) as impressions,
            SUM(COALESCE(bids_in_auction, 0)) as bids_in_auction,
            SUM(COALESCE(auctions_won, 0)) as auctions_won
        FROM `{project}.{dataset}.rtb_daily`
        WHERE metric_date = @metric_date
          AND billing_id IS NOT NULL
        GROUP BY metric_date, buyer_account_id, billing_id
    """,

    "rtb_publisher_daily": """
        SELECT
            metric_date as metric_date,
            buyer_account_id,
            publisher_id,
            MAX(publisher_name) as publisher_name,
            SUM(COALESCE(reached_queries, 0)) as reached_queries,
            SUM(COALESCE(impressions, 0)) as impressions,
            SUM(COALESCE(bids, 0)) as bids,
            SUM(COALESCE(successful_responses, 0)) as successful_responses,
            SUM(COALESCE(bid_requests, 0)) as bid_requests,
            SUM(COALESCE(auctions_won, 0)) as auctions_won
        FROM `{project}.{dataset}.raw_facts`
        WHERE metric_date = @metric_date
          AND publisher_id IS NOT NULL
        GROUP BY metric_date, buyer_account_id, publisher_id
    """,
}

# Postgres upsert templates
# Uses INSERT ... ON CONFLICT for idempotency

PG_UPSERTS = {
    "home_publisher_daily": """
        INSERT INTO home_publisher_daily
            (metric_date, buyer_account_id, publisher_id, publisher_name,
             reached_queries, impressions, bids, successful_responses,
             bid_requests, auctions_won)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (metric_date, buyer_account_id, publisher_id)
        DO UPDATE SET
            publisher_name = EXCLUDED.publisher_name,
            reached_queries = EXCLUDED.reached_queries,
            impressions = EXCLUDED.impressions,
            bids = EXCLUDED.bids,
            successful_responses = EXCLUDED.successful_responses,
            bid_requests = EXCLUDED.bid_requests,
            auctions_won = EXCLUDED.auctions_won
    """,

    "home_geo_daily": """
        INSERT INTO home_geo_daily
            (metric_date, buyer_account_id, country,
             reached_queries, impressions, bids, successful_responses,
             bid_requests, auctions_won)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (metric_date, buyer_account_id, country)
        DO UPDATE SET
            reached_queries = EXCLUDED.reached_queries,
            impressions = EXCLUDED.impressions,
            bids = EXCLUDED.bids,
            successful_responses = EXCLUDED.successful_responses,
            bid_requests = EXCLUDED.bid_requests,
            auctions_won = EXCLUDED.auctions_won
    """,

    "home_size_daily": """
        INSERT INTO home_size_daily
            (metric_date, buyer_account_id, creative_size,
             reached_queries, impressions)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (metric_date, buyer_account_id, creative_size)
        DO UPDATE SET
            reached_queries = EXCLUDED.reached_queries,
            impressions = EXCLUDED.impressions
    """,

    "home_seat_daily": """
        INSERT INTO home_seat_daily
            (metric_date, buyer_account_id,
             reached_queries, impressions, bids, successful_responses,
             bid_requests, auctions_won)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (metric_date, buyer_account_id)
        DO UPDATE SET
            reached_queries = EXCLUDED.reached_queries,
            impressions = EXCLUDED.impressions,
            bids = EXCLUDED.bids,
            successful_responses = EXCLUDED.successful_responses,
            bid_requests = EXCLUDED.bid_requests,
            auctions_won = EXCLUDED.auctions_won
    """,

    "home_config_daily": """
        INSERT INTO home_config_daily
            (metric_date, buyer_account_id, billing_id,
             reached_queries, impressions, bids_in_auction, auctions_won)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (metric_date, buyer_account_id, billing_id)
        DO UPDATE SET
            reached_queries = EXCLUDED.reached_queries,
            impressions = EXCLUDED.impressions,
            bids_in_auction = EXCLUDED.bids_in_auction,
            auctions_won = EXCLUDED.auctions_won
    """,

    "rtb_publisher_daily": """
        INSERT INTO rtb_publisher_daily
            (metric_date, buyer_account_id, publisher_id, publisher_name,
             reached_queries, impressions, bids, successful_responses,
             bid_requests, auctions_won)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (metric_date, buyer_account_id, publisher_id)
        DO UPDATE SET
            publisher_name = EXCLUDED.publisher_name,
            reached_queries = EXCLUDED.reached_queries,
            impressions = EXCLUDED.impressions,
            bids = EXCLUDED.bids,
            successful_responses = EXCLUDED.successful_responses,
            bid_requests = EXCLUDED.bid_requests,
            auctions_won = EXCLUDED.auctions_won
    """,
}

# Row to tuple mapping for each table
ROW_EXTRACTORS = {
    "home_publisher_daily": lambda r: (
        r["metric_date"], r["buyer_account_id"], r["publisher_id"],
        r["publisher_name"], r["reached_queries"], r["impressions"],
        r["bids"], r["successful_responses"], r["bid_requests"],
        r["auctions_won"]
    ),
    "home_geo_daily": lambda r: (
        r["metric_date"], r["buyer_account_id"], r["country"],
        r["reached_queries"], r["impressions"], r["bids"],
        r["successful_responses"], r["bid_requests"], r["auctions_won"]
    ),
    "home_size_daily": lambda r: (
        r["metric_date"], r["buyer_account_id"], r["creative_size"],
        r["reached_queries"], r["impressions"]
    ),
    "home_seat_daily": lambda r: (
        r["metric_date"], r["buyer_account_id"],
        r["reached_queries"], r["impressions"], r["bids"],
        r["successful_responses"], r["bid_requests"], r["auctions_won"]
    ),
    "home_config_daily": lambda r: (
        r["metric_date"], r["buyer_account_id"], r["billing_id"],
        r["reached_queries"], r["impressions"], r["bids_in_auction"],
        r["auctions_won"]
    ),
    "rtb_publisher_daily": lambda r: (
        r["metric_date"], r["buyer_account_id"], r["publisher_id"],
        r["publisher_name"], r["reached_queries"], r["impressions"],
        r["bids"], r["successful_responses"], r["bid_requests"],
        r["auctions_won"]
    ),
}


def get_config() -> Dict[str, str]:
    """Get configuration from environment."""
    project_id = os.getenv("BIGQUERY_PROJECT_ID")
    dataset = os.getenv("BIGQUERY_DATASET")
    postgres_dsn = os.getenv("POSTGRES_DSN")

    if not project_id:
        raise RuntimeError("BIGQUERY_PROJECT_ID must be set")
    if not dataset:
        raise RuntimeError("BIGQUERY_DATASET must be set")
    if not postgres_dsn:
        raise RuntimeError("POSTGRES_DSN must be set")

    return {
        "project_id": project_id,
        "dataset": dataset,
        "postgres_dsn": postgres_dsn,
    }


def run_bq_aggregation(
    bq_client: bigquery.Client,
    table_name: str,
    metric_date: date,
    project_id: str,
    dataset: str,
) -> List[Dict[str, Any]]:
    """Run aggregation query on BigQuery and return results."""
    query_template = AGG_QUERIES.get(table_name)
    if not query_template:
        raise ValueError(f"No aggregation query for table: {table_name}")

    query = query_template.format(project=project_id, dataset=dataset)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("metric_date", "DATE", metric_date)
        ]
    )

    logger.info(f"Running aggregation for {table_name} on {metric_date}")
    query_job = bq_client.query(query, job_config=job_config)
    results = list(query_job.result())

    # Convert to list of dicts
    rows = []
    for row in results:
        rows.append(dict(row))

    logger.info(f"Got {len(rows)} rows for {table_name}")
    return rows


def write_to_postgres(
    pg_conn: psycopg.Connection,
    table_name: str,
    rows: List[Dict[str, Any]],
) -> int:
    """Write aggregated rows to Postgres using upsert."""
    if not rows:
        return 0

    upsert_sql = PG_UPSERTS.get(table_name)
    if not upsert_sql:
        raise ValueError(f"No upsert SQL for table: {table_name}")

    extractor = ROW_EXTRACTORS.get(table_name)
    if not extractor:
        raise ValueError(f"No row extractor for table: {table_name}")

    # Convert rows to tuples
    values = [extractor(row) for row in rows]

    # Execute upsert
    with pg_conn.cursor() as cur:
        cur.executemany(upsert_sql, values)

    pg_conn.commit()
    logger.info(f"Upserted {len(values)} rows into {table_name}")

    return len(values)


def aggregate_date(
    metric_date: date,
    tables: Optional[List[str]] = None,
    config: Optional[Dict[str, str]] = None,
) -> Dict[str, int]:
    """Run aggregation for a single date.

    Args:
        metric_date: Date to aggregate
        tables: List of tables to aggregate (default: all)
        config: Configuration dict (default: from env)

    Returns:
        Dict mapping table name to rows upserted
    """
    config = config or get_config()
    tables = tables or list(AGG_QUERIES.keys())

    bq_client = bigquery.Client(project=config["project_id"])
    pg_conn = psycopg.connect(config["postgres_dsn"])

    results = {}

    try:
        for table_name in tables:
            try:
                # Run BigQuery aggregation
                rows = run_bq_aggregation(
                    bq_client=bq_client,
                    table_name=table_name,
                    metric_date=metric_date,
                    project_id=config["project_id"],
                    dataset=config["dataset"],
                )

                # Write to Postgres
                count = write_to_postgres(pg_conn, table_name, rows)
                results[table_name] = count

            except Exception as e:
                logger.error(f"Error aggregating {table_name}: {e}")
                results[table_name] = -1  # Indicate error

    finally:
        pg_conn.close()

    return results


def aggregate_date_range(
    start_date: date,
    end_date: date,
    tables: Optional[List[str]] = None,
) -> Dict[str, Dict[str, int]]:
    """Run aggregation for a date range.

    Returns:
        Dict mapping date string to table results
    """
    config = get_config()
    all_results = {}

    current = start_date
    while current <= end_date:
        date_str = current.isoformat()
        logger.info(f"Processing {date_str}")

        results = aggregate_date(current, tables, config)
        all_results[date_str] = results

        current += timedelta(days=1)

    return all_results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate BigQuery data to Postgres"
    )
    parser.add_argument(
        "--date", "-d",
        help="Single date to aggregate (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--date-range", "-r",
        nargs=2,
        metavar=("START", "END"),
        help="Date range to aggregate (YYYY-MM-DD YYYY-MM-DD)",
    )
    parser.add_argument(
        "--tables", "-t",
        nargs="+",
        choices=list(AGG_QUERIES.keys()),
        help="Specific tables to aggregate (default: all)",
    )

    args = parser.parse_args()

    if not args.date and not args.date_range:
        parser.error("Either --date or --date-range is required")

    try:
        if args.date:
            metric_date = date.fromisoformat(args.date)
            results = aggregate_date(metric_date, args.tables)

            print(f"\nAggregation complete for {args.date}:")
            for table, count in results.items():
                status = "✓" if count >= 0 else "✗"
                print(f"  {status} {table}: {count if count >= 0 else 'ERROR'} rows")

        else:
            start_date = date.fromisoformat(args.date_range[0])
            end_date = date.fromisoformat(args.date_range[1])
            results = aggregate_date_range(start_date, end_date, args.tables)

            print(f"\nAggregation complete for {start_date} to {end_date}:")
            total_by_table = {}
            for date_str, table_results in results.items():
                for table, count in table_results.items():
                    if count >= 0:
                        total_by_table[table] = total_by_table.get(table, 0) + count

            for table, total in total_by_table.items():
                print(f"  {table}: {total} total rows")

        return 0

    except Exception as e:
        logger.error(f"Aggregation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
