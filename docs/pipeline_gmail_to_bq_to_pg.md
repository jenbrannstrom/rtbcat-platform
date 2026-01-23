# Data Pipeline: Gmail CSV → BigQuery → Postgres

## Overview

This document describes the data pipeline that processes RTB reports from Gmail,
stores them in BigQuery for analytics, and aggregates results into Postgres for
the dashboard UI.

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA PIPELINE FLOW                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   Gmail      │     │    GCS       │     │   BigQuery   │     │   Postgres   │
  │   (CSV)      │────▶│  (Parquet)   │────▶│  (raw_facts) │────▶│  (home_*)    │
  └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
        │                    │                    │                    │
        │                    │                    │                    │
   ┌────▼────┐          ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
   │ Gmail   │          │ Parquet │          │ Load    │          │ Agg     │
   │ Import  │          │ Export  │          │ Job     │          │ Queries │
   └─────────┘          └─────────┘          └─────────┘          └─────────┘

  Step 1: Gmail importer downloads CSV attachments from Google Ads reports
  Step 2: CSV converted to Parquet and uploaded to GCS
  Step 3: BigQuery loads Parquet files into raw_facts table
  Step 4: Aggregation queries populate Postgres UI tables
```

## GCS Path Structure

Parquet files are stored with the following path convention:

```
gs://<RAW_PARQUET_BUCKET>/raw/YYYY/MM/DD/<buyer_id>/<report_type>.parquet

Examples:
gs://rtbcat-raw-parquet-sg-202601/raw/2026/01/23/6634662463/funnel_publishers.parquet
gs://rtbcat-raw-parquet-sg-202601/raw/2026/01/23/6634662463/bid_filtering.parquet
gs://rtbcat-raw-parquet-sg-202601/raw/2026/01/23/6634662463/quality.parquet
```

**Path Components:**
- `raw/` - Prefix for raw ingested data
- `YYYY/MM/DD` - Metric date (not import date)
- `<buyer_id>` - Buyer account ID from the report
- `<report_type>.parquet` - Type of report (funnel, bid_filtering, quality)

## BigQuery Schema

### Dataset: `rtbcat_analytics`

### Table: `raw_facts` (Partitioned)

| Column | Type | Description |
|--------|------|-------------|
| event_timestamp | TIMESTAMP | Partition field (metric date) |
| buyer_account_id | STRING | Buyer/account identifier |
| report_type | STRING | funnel_publishers, bid_filtering, quality |
| metric_date | DATE | Date of the metrics |
| country | STRING | Country code |
| publisher_id | STRING | Publisher identifier |
| publisher_name | STRING | Publisher display name |
| creative_id | STRING | Creative identifier |
| creative_size | STRING | Creative dimensions (e.g., "300x250") |
| billing_id | STRING | Billing configuration ID |
| bid_requests | INT64 | Number of bid requests |
| inventory_matches | INT64 | Inventory match count |
| successful_responses | INT64 | Successful bid responses |
| reached_queries | INT64 | Reached query count |
| bids | INT64 | Number of bids |
| bids_in_auction | INT64 | Bids that entered auction |
| auctions_won | INT64 | Auctions won |
| impressions | INT64 | Impression count |
| clicks | INT64 | Click count |
| spend_buyer_currency | FLOAT64 | Spend in buyer currency |
| spend_bidder_currency | FLOAT64 | Spend in bidder currency |
| bid_filtering_reason | STRING | Reason for bid filtering |
| gcs_source_uri | STRING | Source Parquet file URI |
| loaded_at | TIMESTAMP | When the row was loaded |

**Partitioning:** `event_timestamp` (DAY)
**Clustering:** `buyer_account_id`, `report_type`

### Aggregation Tables (Views or Materialized)

These are computed from `raw_facts` and written to Postgres:

- `agg_publisher_daily` - Publisher-level daily aggregates
- `agg_geo_daily` - Geography-level daily aggregates
- `agg_size_daily` - Creative size daily aggregates
- `agg_config_daily` - Billing config daily aggregates

## Postgres UI Tables

### home_publisher_daily

| Column | Type | Description |
|--------|------|-------------|
| metric_date | DATE | Metric date |
| buyer_account_id | TEXT | Buyer account ID |
| publisher_id | TEXT | Publisher ID |
| publisher_name | TEXT | Publisher name |
| reached_queries | BIGINT | Reached queries |
| impressions | BIGINT | Impressions |
| bids | BIGINT | Bids |
| successful_responses | BIGINT | Successful responses |
| bid_requests | BIGINT | Bid requests |
| auctions_won | BIGINT | Auctions won |

**Primary Key:** `(metric_date, buyer_account_id, publisher_id)`

### home_geo_daily

| Column | Type | Description |
|--------|------|-------------|
| metric_date | DATE | Metric date |
| buyer_account_id | TEXT | Buyer account ID |
| country | TEXT | Country code |
| reached_queries | BIGINT | Reached queries |
| impressions | BIGINT | Impressions |
| bids | BIGINT | Bids |
| successful_responses | BIGINT | Successful responses |
| bid_requests | BIGINT | Bid requests |
| auctions_won | BIGINT | Auctions won |

**Primary Key:** `(metric_date, buyer_account_id, country)`

### home_size_daily

| Column | Type | Description |
|--------|------|-------------|
| metric_date | DATE | Metric date |
| buyer_account_id | TEXT | Buyer account ID |
| creative_size | TEXT | Creative dimensions |
| reached_queries | BIGINT | Reached queries |
| impressions | BIGINT | Impressions |

**Primary Key:** `(metric_date, buyer_account_id, creative_size)`

### home_seat_daily

| Column | Type | Description |
|--------|------|-------------|
| metric_date | DATE | Metric date |
| buyer_account_id | TEXT | Buyer account ID |
| reached_queries | BIGINT | Reached queries |
| impressions | BIGINT | Impressions |
| bids | BIGINT | Bids |
| successful_responses | BIGINT | Successful responses |
| bid_requests | BIGINT | Bid requests |
| auctions_won | BIGINT | Auctions won |

**Primary Key:** `(metric_date, buyer_account_id)`

### home_config_daily

| Column | Type | Description |
|--------|------|-------------|
| metric_date | DATE | Metric date |
| buyer_account_id | TEXT | Buyer account ID |
| billing_id | TEXT | Billing configuration ID |
| reached_queries | BIGINT | Reached queries |
| impressions | BIGINT | Impressions |
| bids_in_auction | BIGINT | Bids in auction |
| auctions_won | BIGINT | Auctions won |

**Primary Key:** `(metric_date, buyer_account_id, billing_id)`

## Batch Cadence

### Primary Trigger: Gmail Import
- Pipeline runs automatically after each successful Gmail CSV import
- Gmail import runs every 15 minutes (via cron or Cloud Scheduler)

### Daily Scheduled Run
- Full pipeline runs daily at 06:00 UTC
- Reprocesses previous day to catch late-arriving reports
- Cloud Scheduler: `0 6 * * *`

### Manual Trigger
```bash
# Run pipeline for specific CSV
python scripts/run_pipeline.py --csv-path /path/to/report.csv

# Run aggregation only (no new data)
python scripts/bq_aggregate_to_pg.py --date 2026-01-23
```

## Failure Handling

### CSV Parsing Errors
- Log error with filename and line number
- Skip corrupt rows, continue with valid data
- Record skipped count in import log

### GCS Upload Failures
- Retry up to 3 times with exponential backoff
- On persistent failure, log error and continue to next file
- Keep local Parquet file for manual retry

### BigQuery Load Failures
- Retry up to 3 times
- On schema mismatch, log error and skip file
- Use WRITE_APPEND mode for idempotent loads

### Postgres Write Failures
- Use upsert (INSERT ON CONFLICT UPDATE) for idempotency
- Transaction rollback on error
- Log failed date ranges for manual retry

### Error Logging
All errors logged to:
- Console (stdout/stderr)
- `/var/log/catscan/pipeline.log`
- Import history table in database

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| RAW_PARQUET_BUCKET | Yes | GCS bucket for Parquet files |
| BIGQUERY_PROJECT_ID | Yes | GCP project for BigQuery |
| BIGQUERY_DATASET | Yes | BigQuery dataset name |
| BIGQUERY_RAW_FACTS_TABLE | No | Raw facts table (default: raw_facts) |
| POSTGRES_DSN | Yes | PostgreSQL connection string |
| GOOGLE_APPLICATION_CREDENTIALS | Yes | Path to service account JSON |

## Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `scripts/export_csv_to_parquet.py` | Convert CSV to Parquet, upload to GCS |
| `scripts/load_parquet_to_bigquery.py` | Load Parquet from GCS into BigQuery |
| `scripts/bq_aggregate_to_pg.py` | Aggregate BigQuery data to Postgres |
| `scripts/run_pipeline.py` | Orchestrate full pipeline |
| `scripts/gmail_import.py` | Gmail import (calls run_pipeline.py) |

## Monitoring

### Health Checks
- `/api/precompute/health` - Returns last refresh status
- BigQuery job status via Cloud Console
- GCS file count and size metrics

### Alerts
- Pipeline failure: Slack/email notification
- Data freshness: Alert if no new data in 24 hours
- Error rate: Alert if >10% rows fail validation
