# SQLite → GCS/BigQuery → Postgres migration runbook

This runbook tracks the four migration tasks:

1. Export existing SQLite raw tables to CSV/Parquet.
2. Load into GCS and BigQuery partitions.
3. Run precompute jobs for the last 90 days to fill Postgres summary tables.
4. Switch the UI to Postgres once validated.

## Prerequisites

- Access to the SQLite database file (typically `~/.catscan/catscan.db`).
- A GCS bucket for raw exports.
- A BigQuery dataset for staging/partitioned tables.
- A Postgres instance with the target schema and summary tables.

## 1) Export SQLite raw tables to CSV/Parquet

### Identify raw tables

The raw RTB tables that drive analytics include:

- `rtb_daily`
- `rtb_bidstream`
- `rtb_bid_filtering`
- `rtb_quality`
- `rtb_traffic`

If you need additional raw tables (for example, `performance_metrics`), export those as well.

### CSV export (recommended for large tables)

For full-table exports:

```bash
sqlite3 ~/.catscan/catscan.db \
  -header -csv "SELECT * FROM rtb_bidstream;" \
  > rtb_bidstream.csv
```

For date-bounded exports (preferred for partitions and resumable loads):

```bash
sqlite3 ~/.catscan/catscan.db \
  -header -csv "SELECT * FROM rtb_bidstream WHERE metric_date BETWEEN '2024-01-01' AND '2024-03-31';" \
  > rtb_bidstream_2024Q1.csv
```

Repeat per table and per partitionable date range.

### Parquet export (optional)

If you need Parquet, convert the CSVs with a tool like DuckDB or pandas + pyarrow:

```bash
duckdb -c "COPY (SELECT * FROM read_csv_auto('rtb_bidstream.csv')) TO 'rtb_bidstream.parquet' (FORMAT PARQUET);"
```

## 2) Load exports into GCS and BigQuery partitions

### Upload to GCS

```bash
gsutil -m cp rtb_bidstream_*.csv gs://YOUR_BUCKET/rtb/raw/rtb_bidstream/
```

### BigQuery load (CSV)

If `metric_date` is a `DATE` column, load with ingestion-time partitioning:

```bash
bq load \
  --source_format=CSV \
  --skip_leading_rows=1 \
  --autodetect \
  --time_partitioning_field=metric_date \
  YOUR_DATASET.rtb_bidstream \
  gs://YOUR_BUCKET/rtb/raw/rtb_bidstream/rtb_bidstream_*.csv
```

If `metric_date` arrives as text, load into a staging table and cast into a partitioned table:

```sql
CREATE OR REPLACE TABLE YOUR_DATASET.rtb_bidstream
PARTITION BY metric_date AS
SELECT
  *,
  DATE(metric_date) AS metric_date
FROM YOUR_DATASET.rtb_bidstream_staging;
```

Repeat the same pattern for `rtb_daily`, `rtb_bid_filtering`, `rtb_quality`, and `rtb_traffic`.

## 3) Run precompute jobs for the last 90 days

Once the Postgres data is in place (and the API is configured to point at Postgres), refresh the precompute tables for the last 90 days:

```bash
python scripts/refresh_precompute.py --days 90 --validate
```

Optional scope to a seat:

```bash
python scripts/refresh_precompute.py --days 90 --buyer-id BUYER_ACCOUNT_ID --validate
```

The precompute refresh covers:

- Home summaries (`home_*_daily`)
- Config breakdowns (`config_*_daily`)
- RTB summaries (`rtb_*_daily`)

## 4) Switch the UI to Postgres once validated

1. Validate the precompute outputs (use the `--validate` flag above and spot-check in BigQuery/Postgres).
2. Update API configuration to point to the Postgres-backed storage.
3. Redeploy API + dashboard services.
4. Confirm the UI reads from Postgres-backed endpoints.

## Validation checklist

- Row counts match between SQLite exports and BigQuery staging tables.
- Partitioned tables in BigQuery include the expected date ranges.
- Precompute validation passes for the last 90 days.
- UI analytics pages render with data in the expected date ranges.
