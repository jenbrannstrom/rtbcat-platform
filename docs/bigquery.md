# BigQuery Parquet Layout & Table Definitions

This guide defines the Parquet layout and BigQuery table definitions for the `rtb_daily` and `rtb_bidstream` datasets.

## Parquet file layout (by date)

Store daily data in GCS using Hive-style date partitions:

- `gs://rtbcat-raw-parquet/rtb_daily/metric_date=YYYY-MM-DD/*.parquet`
- `gs://rtbcat-raw-parquet/rtb_bidstream/metric_date=YYYY-MM-DD/*.parquet`

## BigQuery native tables (recommended)

Partition on `metric_date` and cluster on high-cardinality identifiers.

### `rtb_daily`

```sql
CREATE TABLE `project_id.dataset_id.rtb_daily`
(
  id INT64,
  metric_date DATE,
  creative_id STRING,
  billing_id STRING,
  creative_size STRING,
  creative_format STRING,
  country STRING,
  platform STRING,
  environment STRING,
  app_id STRING,
  app_name STRING,
  publisher_id STRING,
  publisher_name STRING,
  publisher_domain STRING,
  deal_id STRING,
  deal_name STRING,
  transaction_type STRING,
  advertiser STRING,
  buyer_account_id STRING,
  buyer_account_name STRING,
  bidder_id STRING,
  hour INT64,
  reached_queries INT64,
  impressions INT64,
  clicks INT64,
  spend_micros INT64,
  video_starts INT64,
  video_first_quartile INT64,
  video_midpoint INT64,
  video_third_quartile INT64,
  video_completions INT64,
  vast_errors INT64,
  engaged_views INT64,
  active_view_measurable INT64,
  active_view_viewable INT64,
  gma_sdk INT64,
  buyer_sdk INT64,
  row_hash STRING,
  import_batch_id STRING,
  created_at TIMESTAMP
)
PARTITION BY metric_date
CLUSTER BY buyer_account_id, publisher_id, creative_id;
```

### `rtb_bidstream`

```sql
CREATE TABLE `project_id.dataset_id.rtb_bidstream`
(
  id INT64,
  metric_date DATE,
  hour INT64,
  country STRING,
  buyer_account_id STRING,
  publisher_id STRING,
  publisher_name STRING,
  platform STRING,
  environment STRING,
  transaction_type STRING,
  inventory_matches INT64,
  bid_requests INT64,
  successful_responses INT64,
  reached_queries INT64,
  bids INT64,
  bids_in_auction INT64,
  auctions_won INT64,
  impressions INT64,
  clicks INT64,
  bidder_id STRING,
  row_hash STRING,
  import_batch_id STRING,
  report_type STRING,
  created_at TIMESTAMP
)
PARTITION BY metric_date
CLUSTER BY buyer_account_id, publisher_id, bidder_id;
```

## External tables (optional)

If you prefer querying Parquet files directly, create external tables with Hive partition discovery.

### `rtb_daily_external`

```sql
CREATE EXTERNAL TABLE `project_id.dataset_id.rtb_daily_external`
(
  id INT64,
  creative_id STRING,
  billing_id STRING,
  creative_size STRING,
  creative_format STRING,
  country STRING,
  platform STRING,
  environment STRING,
  app_id STRING,
  app_name STRING,
  publisher_id STRING,
  publisher_name STRING,
  publisher_domain STRING,
  deal_id STRING,
  deal_name STRING,
  transaction_type STRING,
  advertiser STRING,
  buyer_account_id STRING,
  buyer_account_name STRING,
  bidder_id STRING,
  hour INT64,
  reached_queries INT64,
  impressions INT64,
  clicks INT64,
  spend_micros INT64,
  video_starts INT64,
  video_first_quartile INT64,
  video_midpoint INT64,
  video_third_quartile INT64,
  video_completions INT64,
  vast_errors INT64,
  engaged_views INT64,
  active_view_measurable INT64,
  active_view_viewable INT64,
  gma_sdk INT64,
  buyer_sdk INT64,
  row_hash STRING,
  import_batch_id STRING,
  created_at TIMESTAMP
)
WITH PARTITION COLUMNS (metric_date DATE)
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://rtbcat-raw-parquet/rtb_daily/metric_date=*/*.parquet'],
  hive_partition_uri_prefix = 'gs://rtbcat-raw-parquet/rtb_daily/',
  require_hive_partition_filter = TRUE
);
```

### `rtb_bidstream_external`

```sql
CREATE EXTERNAL TABLE `project_id.dataset_id.rtb_bidstream_external`
(
  id INT64,
  hour INT64,
  country STRING,
  buyer_account_id STRING,
  publisher_id STRING,
  publisher_name STRING,
  platform STRING,
  environment STRING,
  transaction_type STRING,
  inventory_matches INT64,
  bid_requests INT64,
  successful_responses INT64,
  reached_queries INT64,
  bids INT64,
  bids_in_auction INT64,
  auctions_won INT64,
  impressions INT64,
  clicks INT64,
  bidder_id STRING,
  row_hash STRING,
  import_batch_id STRING,
  report_type STRING,
  created_at TIMESTAMP
)
WITH PARTITION COLUMNS (metric_date DATE)
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://rtbcat-raw-parquet/rtb_bidstream/metric_date=*/*.parquet'],
  hive_partition_uri_prefix = 'gs://rtbcat-raw-parquet/rtb_bidstream/',
  require_hive_partition_filter = TRUE
);
```

## Load jobs into native tables

To load Parquet into native partitioned tables with Hive partitioning:

```sh
bq load \
  --source_format=PARQUET \
  --hive_partitioning_mode=AUTO \
  --hive_partitioning_source_uri_prefix=gs://rtbcat-raw-parquet/rtb_daily/ \
  project_id:dataset_id.rtb_daily \
  'gs://rtbcat-raw-parquet/rtb_daily/metric_date=*/*.parquet'
```

```sh
bq load \
  --source_format=PARQUET \
  --hive_partitioning_mode=AUTO \
  --hive_partitioning_source_uri_prefix=gs://rtbcat-raw-parquet/rtb_bidstream/ \
  project_id:dataset_id.rtb_bidstream \
  'gs://rtbcat-raw-parquet/rtb_bidstream/metric_date=*/*.parquet'
```
