# Chapter 14: Database Operations

*Audience: DevOps, platform engineers*

## Postgres production

Cat-Scan uses Cloud SQL (Postgres 15) as its sole operational database. The
API connects via a Cloud SQL Auth Proxy sidecar container on `localhost:5432`.

### Key tables and scale

| Table | Approximate rows | What it stores |
|-------|------------------|----------------|
| `rtb_daily` | ~84 million | Daily RTB performance per buyer, creative, geo, etc. |
| `rtb_bidstream` | ~21 million | Bidstream breakdown by publisher, geo |
| `rtb_quality` | varies | Quality metrics (viewability, brand safety) |
| `rtb_bid_filtering` | ~188 thousand | Bid filtering reasons and volumes |
| `pretargeting_configs` | small | Pretargeting configuration snapshots |
| `creatives` | small | Creative metadata and thumbnails |
| `import_history` | small | CSV import records |
| `users`, `permissions`, `audit_log` | small | Auth and admin data |

### Critical indexes

The most performance-sensitive index pattern is:

```sql
CREATE INDEX idx_<table>_buyer_metric_date_desc
    ON <table> (buyer_account_id, metric_date DESC);
```

This exists on `rtb_daily`, `rtb_bidstream`, `rtb_quality`, and
`rtb_bid_filtering`. It supports the data-freshness query and buyer-scoped
analytics.

Other important indexes:
- `(metric_date, buyer_account_id)`: for date-range + buyer filters
- `(metric_date, billing_id)`: for billing-scoped queries
- `(row_hash)` UNIQUE: deduplication on import

### Deduplication

Each imported row is hashed (`row_hash` column). The unique constraint on
`row_hash` prevents duplicate inserts, making re-import safe.

## Connection model

The API uses **per-request connections** (no connection pool). Each query
creates a fresh `psycopg.connect()` call, wrapped in `run_in_executor` for
async compatibility.

```python
async def pg_query(sql, params=()):
    loop = asyncio.get_event_loop()
    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    return await loop.run_in_executor(None, _execute)
```

For production workloads, consider adding `psycopg_pool` if connection
overhead becomes a bottleneck.

## Statement timeouts

For expensive queries (e.g., data-freshness across large tables), the API
uses `pg_query_with_timeout`:

```python
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
cursor = conn.execute(sql, params)
```

Key details:
- `SET LOCAL` scopes the timeout to the current transaction and auto-resets
  when the transaction ends (commit or rollback).
- Default data-freshness timeout: 30 seconds.
- Configurable via `UPLOADS_DATA_FRESHNESS_QUERY_TIMEOUT_MS` environment
  variable (minimum 1000ms).
- `SET LOCAL` avoids the aborted-transaction problem that occurs when using
  `SET` + `RESET` in a `try/finally` block (if the query is cancelled by the
  timeout, the transaction enters an aborted state, and `RESET` fails).

## Data freshness query pattern

The data-freshness endpoint needs to know which dates have data for each
report type. The performant pattern uses `generate_series` + `EXISTS`:

```sql
SELECT d::date AS metric_date, 'bidsinauction' AS csv_type, 1 AS row_count
FROM generate_series(%s::date, CURRENT_DATE - 1, '1 day'::interval) AS d
WHERE EXISTS (
    SELECT 1 FROM rtb_daily
    WHERE metric_date = d::date AND buyer_account_id = %s
    LIMIT 1
)
```

This does N index lookups (one per day in the window) instead of scanning
millions of rows. For a 14-day window: 14 lookups at ~0.1ms each vs. a full
parallel seq scan that takes 160+ seconds.

**Why GROUP BY doesn't work here:** Even with `1 AS row_count` (no COUNT),
the planner chooses a sequential scan when the GROUP BY result set is large
relative to the table. The `(buyer_account_id, metric_date DESC)` index
exists but the planner estimates it's cheaper to scan 84M rows than to do
4.4M index reads.

## BigQuery's role

BigQuery stores raw, granular data and runs batch analytics jobs. It is not
used for real-time API queries. The pattern:

1. Raw CSV data is loaded into BigQuery tables.
2. Batch jobs aggregate the data.
3. Pre-aggregated results are written to Postgres.
4. The API serves from Postgres.

## Data retention

Configurable at `/settings/retention`. Controls how long historical data is
kept in Postgres before aging out.

## Related

- [Architecture Overview](11-architecture.md): where the database fits
- [Troubleshooting](15-troubleshooting.md): database failure patterns
- For media buyers: [Data Import](09-data-import.md) covers the user-facing
  data freshness grid.
