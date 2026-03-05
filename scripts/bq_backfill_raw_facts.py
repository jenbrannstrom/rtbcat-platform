#!/usr/bin/env python3
"""Backfill Postgres raw fact tables from BigQuery.

This script copies data from BigQuery rtb_daily, rtb_bidstream, rtb_bid_filtering
tables to the corresponding Postgres tables.

Usage:
    python scripts/bq_backfill_raw_facts.py --table rtb_daily --date-range 2026-01-07 2026-01-25
    python scripts/bq_backfill_raw_facts.py --all --date-range 2026-01-07 2026-01-25

Environment Variables:
    BIGQUERY_PROJECT_ID: GCP project ID (required)
    BIGQUERY_DATASET: BigQuery dataset name (default: rtbcat_analytics)
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

# BigQuery SELECT queries for each table
BQ_QUERIES = {
    "rtb_daily": """
        SELECT
            metric_date,
            creative_id,
            billing_id,
            creative_size,
            creative_format,
            country,
            platform,
            environment,
            app_id,
            app_name,
            publisher_id,
            publisher_name,
            publisher_domain,
            deal_id,
            deal_name,
            transaction_type,
            advertiser,
            buyer_account_id,
            buyer_account_name,
            bidder_id,
            NULL as report_type,
            hour,
            COALESCE(reached_queries, 0) as reached_queries,
            COALESCE(impressions, 0) as impressions,
            COALESCE(clicks, 0) as clicks,
            COALESCE(spend_micros, 0) as spend_micros,
            COALESCE(video_starts, 0) as video_starts,
            COALESCE(video_first_quartile, 0) as video_first_quartile,
            COALESCE(video_midpoint, 0) as video_midpoint,
            COALESCE(video_third_quartile, 0) as video_third_quartile,
            COALESCE(video_completions, 0) as video_completions,
            COALESCE(vast_errors, 0) as vast_errors,
            COALESCE(engaged_views, 0) as engaged_views,
            COALESCE(active_view_measurable, 0) as active_view_measurable,
            COALESCE(active_view_viewable, 0) as active_view_viewable,
            COALESCE(bids, 0) as bids,
            COALESCE(bids_in_auction, 0) as bids_in_auction,
            COALESCE(auctions_won, 0) as auctions_won,
            gma_sdk,
            buyer_sdk,
            row_hash,
            import_batch_id
        FROM `{project}.{dataset}.rtb_daily`
        WHERE metric_date = @metric_date
    """,

    "rtb_bidstream": """
        SELECT
            metric_date,
            hour,
            country,
            buyer_account_id,
            publisher_id,
            publisher_name,
            platform,
            environment,
            transaction_type,
            COALESCE(inventory_matches, 0) as inventory_matches,
            COALESCE(bid_requests, 0) as bid_requests,
            COALESCE(successful_responses, 0) as successful_responses,
            COALESCE(reached_queries, 0) as reached_queries,
            COALESCE(bids, 0) as bids,
            COALESCE(bids_in_auction, 0) as bids_in_auction,
            COALESCE(auctions_won, 0) as auctions_won,
            COALESCE(impressions, 0) as impressions,
            COALESCE(clicks, 0) as clicks,
            bidder_id,
            report_type,
            row_hash,
            import_batch_id
        FROM `{project}.{dataset}.rtb_bidstream`
        WHERE metric_date = @metric_date
    """,

    "rtb_bid_filtering": """
        SELECT
            metric_date,
            country,
            buyer_account_id,
            filtering_reason,
            creative_id,
            COALESCE(bids, 0) as bids,
            COALESCE(bids_in_auction, 0) as bids_in_auction,
            COALESCE(opportunity_cost_micros, 0) as opportunity_cost_micros,
            bidder_id,
            row_hash,
            import_batch_id
        FROM `{project}.{dataset}.rtb_bid_filtering`
        WHERE metric_date = @metric_date
    """,
}

# Postgres INSERT statements (ON CONFLICT with row_hash)
PG_INSERTS = {
    "rtb_daily": """
        INSERT INTO rtb_daily (
            metric_date, creative_id, billing_id, creative_size, creative_format,
            country, platform, environment, app_id, app_name,
            publisher_id, publisher_name, publisher_domain, deal_id, deal_name,
            transaction_type, advertiser, buyer_account_id, buyer_account_name,
            bidder_id, report_type, hour, reached_queries, impressions, clicks,
            spend_micros, video_starts, video_first_quartile, video_midpoint,
            video_third_quartile, video_completions, vast_errors, engaged_views,
            active_view_measurable, active_view_viewable, bids, bids_in_auction,
            auctions_won, gma_sdk, buyer_sdk, row_hash, import_batch_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (row_hash) DO NOTHING
    """,

    "rtb_bidstream": """
        INSERT INTO rtb_bidstream (
            metric_date, hour, country, buyer_account_id, publisher_id,
            publisher_name, platform, environment, transaction_type,
            inventory_matches, bid_requests, successful_responses, reached_queries,
            bids, bids_in_auction, auctions_won, impressions, clicks,
            bidder_id, report_type, row_hash, import_batch_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (row_hash) DO NOTHING
    """,

    "rtb_bid_filtering": """
        INSERT INTO rtb_bid_filtering (
            metric_date, country, buyer_account_id, filtering_reason, creative_id,
            bids, bids_in_auction, opportunity_cost_micros, bidder_id,
            row_hash, import_batch_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (row_hash) DO NOTHING
    """,
}

# Column extractors for each table
ROW_EXTRACTORS = {
    "rtb_daily": lambda r: (
        r["metric_date"], r["creative_id"], r["billing_id"], r["creative_size"], r["creative_format"],
        r["country"], r["platform"], r["environment"], r["app_id"], r["app_name"],
        r["publisher_id"], r["publisher_name"], r["publisher_domain"], r["deal_id"], r["deal_name"],
        r["transaction_type"], r["advertiser"], r["buyer_account_id"], r["buyer_account_name"],
        r["bidder_id"], r["report_type"], r["hour"], r["reached_queries"], r["impressions"], r["clicks"],
        r["spend_micros"], r["video_starts"], r["video_first_quartile"], r["video_midpoint"],
        r["video_third_quartile"], r["video_completions"], r["vast_errors"], r["engaged_views"],
        r["active_view_measurable"], r["active_view_viewable"], r["bids"], r["bids_in_auction"],
        r["auctions_won"], r["gma_sdk"], r["buyer_sdk"], r["row_hash"], r["import_batch_id"]
    ),

    "rtb_bidstream": lambda r: (
        r["metric_date"], r["hour"], r["country"], r["buyer_account_id"], r["publisher_id"],
        r["publisher_name"], r["platform"], r["environment"], r["transaction_type"],
        r["inventory_matches"], r["bid_requests"], r["successful_responses"], r["reached_queries"],
        r["bids"], r["bids_in_auction"], r["auctions_won"], r["impressions"], r["clicks"],
        r["bidder_id"], r["report_type"], r["row_hash"], r["import_batch_id"]
    ),

    "rtb_bid_filtering": lambda r: (
        r["metric_date"], r["country"], r["buyer_account_id"], r["filtering_reason"], r["creative_id"],
        r["bids"], r["bids_in_auction"], r["opportunity_cost_micros"], r["bidder_id"],
        r["row_hash"], r["import_batch_id"]
    ),
}


def get_config() -> Dict[str, str]:
    """Get configuration from environment."""
    project_id = (os.getenv("BIGQUERY_PROJECT_ID") or "").strip()
    dataset = os.getenv("BIGQUERY_DATASET", "rtbcat_analytics")
    postgres_dsn = os.getenv("POSTGRES_DSN")

    if not project_id:
        raise RuntimeError("BIGQUERY_PROJECT_ID must be set")

    if not postgres_dsn:
        raise RuntimeError("POSTGRES_DSN must be set")

    return {
        "project_id": project_id,
        "dataset": dataset,
        "postgres_dsn": postgres_dsn,
    }


def fetch_from_bq(
    bq_client: bigquery.Client,
    table_name: str,
    metric_date: date,
    project_id: str,
    dataset: str,
) -> List[Dict[str, Any]]:
    """Fetch data from BigQuery for a given table and date."""
    query_template = BQ_QUERIES.get(table_name)
    if not query_template:
        raise ValueError(f"No BQ query for table: {table_name}")

    query = query_template.format(project=project_id, dataset=dataset)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("metric_date", "DATE", metric_date)
        ]
    )

    logger.info(f"Querying BQ {table_name} for {metric_date}...")
    job = bq_client.query(query, job_config=job_config)
    results = list(job.result())
    logger.info(f"  Got {len(results)} rows from BQ")

    return [dict(row) for row in results]


def insert_to_postgres(
    pg_conn: psycopg.Connection,
    table_name: str,
    rows: List[Dict[str, Any]],
    batch_size: int = 5000,
) -> int:
    """Insert rows into Postgres table."""
    if not rows:
        return 0

    insert_sql = PG_INSERTS.get(table_name)
    extractor = ROW_EXTRACTORS.get(table_name)

    if not insert_sql or not extractor:
        raise ValueError(f"No insert config for table: {table_name}")

    cursor = pg_conn.cursor()
    total_inserted = 0

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        values = [extractor(row) for row in batch]

        try:
            cursor.executemany(insert_sql, values)
            total_inserted += len(batch)
            logger.info(f"  Inserted batch {i // batch_size + 1}: {len(batch)} rows")
        except Exception as e:
            logger.error(f"  Error inserting batch: {e}")
            pg_conn.rollback()
            raise

    pg_conn.commit()
    return total_inserted


def backfill_table(
    bq_client: bigquery.Client,
    pg_conn: psycopg.Connection,
    table_name: str,
    start_date: date,
    end_date: date,
    project_id: str,
    dataset: str,
) -> Dict[str, int]:
    """Backfill a single table for a date range."""
    logger.info(f"=== Backfilling {table_name} from {start_date} to {end_date} ===")

    stats = {"total_fetched": 0, "total_inserted": 0, "dates_processed": 0}
    current = start_date

    while current <= end_date:
        rows = fetch_from_bq(bq_client, table_name, current, project_id, dataset)
        stats["total_fetched"] += len(rows)

        if rows:
            inserted = insert_to_postgres(pg_conn, table_name, rows)
            stats["total_inserted"] += inserted

        stats["dates_processed"] += 1
        current += timedelta(days=1)

    logger.info(f"=== {table_name} complete: {stats['total_fetched']} fetched, {stats['total_inserted']} inserted ===")
    return stats


def parse_date(s: str) -> date:
    """Parse date from YYYY-MM-DD string."""
    from datetime import datetime
    return datetime.strptime(s, "%Y-%m-%d").date()


def main():
    parser = argparse.ArgumentParser(description="Backfill Postgres raw fact tables from BigQuery")
    parser.add_argument("--table", type=str, help="Table to backfill (rtb_daily, rtb_bidstream, rtb_bid_filtering)")
    parser.add_argument("--all", action="store_true", help="Backfill all raw fact tables")
    parser.add_argument("--date-range", nargs=2, type=str, required=True,
                        help="Start and end dates (YYYY-MM-DD YYYY-MM-DD)")
    parser.add_argument("--batch-size", type=int, default=5000, help="Postgres insert batch size")

    args = parser.parse_args()

    if not args.table and not args.all:
        parser.error("Must specify --table or --all")

    tables = list(BQ_QUERIES.keys()) if args.all else [args.table]
    start_date = parse_date(args.date_range[0])
    end_date = parse_date(args.date_range[1])

    config = get_config()
    logger.info(f"Config: project={config['project_id']}, dataset={config['dataset']}")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Tables: {tables}")

    bq_client = bigquery.Client(project=config["project_id"])
    pg_conn = psycopg.connect(config["postgres_dsn"])

    all_stats = {}
    for table in tables:
        if table not in BQ_QUERIES:
            logger.error(f"Unknown table: {table}")
            continue

        stats = backfill_table(
            bq_client, pg_conn, table,
            start_date, end_date,
            config["project_id"], config["dataset"]
        )
        all_stats[table] = stats

    pg_conn.close()

    # Print summary
    print("\n" + "=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)
    for table, stats in all_stats.items():
        print(f"{table}:")
        print(f"  Dates processed: {stats['dates_processed']}")
        print(f"  Rows fetched: {stats['total_fetched']}")
        print(f"  Rows inserted: {stats['total_inserted']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
