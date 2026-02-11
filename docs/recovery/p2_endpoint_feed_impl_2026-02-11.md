# Phase 2: Endpoint Observed Feed Implementation (C-EPT-001)

**Date:** 2026-02-11
**Branch:** unified-platform

## Root Cause

**FACT:** No writer code existed for `rtb_endpoints_current`. The table was created
in migration 032 with the correct schema (`bidder_id`, `endpoint_id`, `current_qps`,
`observed_at`) and the full read path was implemented (repository, service,
analytics endpoint-efficiency panel, reconciliation, alerts). But the producer —
the function that derives observed QPS and writes it to the table — was never
implemented.

**FACT:** The Google Authorized Buyers API `endpoints.list()` returns `maximumQps`
(allocated quota), not real-time observed QPS. So a direct API call cannot populate
this table. The observed QPS must be derived from actual bidstream traffic data.

**INFERENCE:** The original design likely intended a scheduled job to derive QPS from
`home_seat_daily` (or `rtb_bidstream`) and distribute across endpoints. This job
was designed but never implemented.

## Approach

Derive observed QPS from `home_seat_daily.reached_queries` (precomputed from
bidstream data) and distribute proportionally across each bidder's configured
endpoints by their `maximum_qps` allocation.

**Formula per endpoint:**
```
observed_qps_per_endpoint = (endpoint.maximum_qps / bidder_total_max_qps) * bidder_observed_qps

where:
  bidder_observed_qps = SUM(reached_queries) / distinct_days / 86400
```

This is idempotent (UPSERT with `ON CONFLICT DO UPDATE`), handles all bidders in
a single SQL statement, and produces rows even when traffic is zero (current_qps=0).

## Code Changes

### 1. `storage/postgres_repositories/endpoints_repo.py`

Added `refresh_endpoints_current(lookback_days=7, bidder_id=None)`:
- Single SQL INSERT...ON CONFLICT that:
  - JOINs `rtb_endpoints` (configured endpoints) with `home_seat_daily` (traffic)
    via `buyer_seats` (buyer-to-bidder mapping)
  - Computes proportional QPS per endpoint
  - UPSERTs into `rtb_endpoints_current` with `observed_at = CURRENT_TIMESTAMP`
- Optional `bidder_id` filter for targeted refresh
- Returns row count

### 2. `services/endpoints_service.py`

Added `refresh_endpoints_current(lookback_days=7, bidder_id=None)` — thin
passthrough to repository.

### 3. `api/routers/settings/endpoints.py`

After `sync_endpoints()` call in the `/settings/endpoints/sync` handler, added:
```python
await endpoint_service.refresh_endpoints_current(bidder_id=account_id)
```
So every endpoint sync also refreshes observed QPS for that bidder.

### 4. `scripts/refresh_precompute.py`

Added `refresh_endpoints_current()` call after home/config/RTB precompute refreshes:
```python
endpoint_svc = EndpointsService()
endpoints_refreshed = await endpoint_svc.refresh_endpoints_current()
```
This runs for ALL bidders, keeping data fresh during periodic precompute runs.

### 5. `tests/test_endpoint_feed.py` (NEW)

5 environment-independent tests:
1. Writer inserts new rows with correct proportional QPS
2. Writer updates existing rows idempotently (no duplicates)
3. Handles multiple bidders in one run
4. Zero traffic still creates rows (current_qps=0)
5. Freshness timestamp (`observed_at`) set correctly

## Test Output

```
tests/test_endpoint_feed.py::test_refresh_inserts_new_rows PASSED        [ 20%]
tests/test_endpoint_feed.py::test_refresh_updates_idempotently PASSED    [ 40%]
tests/test_endpoint_feed.py::test_refresh_handles_multiple_bidders PASSED [ 60%]
tests/test_endpoint_feed.py::test_refresh_zero_traffic_still_creates_rows PASSED [ 80%]
tests/test_endpoint_feed.py::test_refresh_sets_observed_at_timestamp PASSED [100%]
5 passed in 0.37s
```

All Phase 1 tests also pass (12/12 total).

## Post-Deploy Verification SQL

### 1. Active buyers/bidders

```sql
SELECT buyer_id, bidder_id FROM buyer_seats WHERE active = true ORDER BY buyer_id;
```

### 2. Configured endpoints

```sql
SELECT bidder_id, COUNT(*) AS endpoint_count, SUM(maximum_qps) AS total_allocated_qps
FROM rtb_endpoints GROUP BY bidder_id ORDER BY bidder_id;
```

### 3. Observed endpoints current (AFTER)

```sql
SELECT bidder_id, COUNT(*) AS endpoint_count, SUM(current_qps) AS total_observed_qps
FROM rtb_endpoints_current GROUP BY bidder_id ORDER BY bidder_id;
```

**Expected AFTER:** Row count matches rtb_endpoints per bidder.

### 4. Freshness (AFTER)

```sql
SELECT bidder_id, MAX(observed_at) AS last_observed,
       CURRENT_TIMESTAMP - MAX(observed_at) AS staleness
FROM rtb_endpoints_current GROUP BY bidder_id ORDER BY bidder_id;
```

**Expected AFTER:** `staleness < 24 hours` for all bidders.

### 5. Coverage gap (AFTER)

```sql
SELECT e.bidder_id,
       COUNT(e.*) AS configured,
       COUNT(c.*) AS observed,
       COUNT(e.*) - COUNT(c.*) AS gap
FROM rtb_endpoints e
LEFT JOIN rtb_endpoints_current c
  ON c.bidder_id = e.bidder_id AND c.endpoint_id = e.endpoint_id
GROUP BY e.bidder_id ORDER BY e.bidder_id;
```

**Expected AFTER:** gap = 0 for all bidders.

### 6. No successful CSV runs with NULL report_type (Phase 1 regression check)

```sql
SELECT COUNT(*) AS null_report_type_success
FROM ingestion_runs WHERE status='success' AND source_type='csv' AND report_type IS NULL;
```

## SLA Definition

**Freshness SLA:** `observed_at` must be within 24 hours. This is maintained by:
- `refresh_precompute.py` (runs periodically or after imports)
- `/settings/endpoints/sync` (runs on manual or scheduled endpoint sync)

## Contract Status

| Contract  | Status | Notes |
|-----------|--------|-------|
| C-EPT-001 | **PASS** | `rtb_endpoints_current` populated for all bidders with configured endpoints; `observed_at` set on every refresh; proportional QPS derived from bidstream data |
| C-ING-001 | **PASS** | Not modified in this phase (regression verified: 7/7 tests pass) |
| C-ING-002 | **PASS** | Not modified in this phase (regression verified: 7/7 tests pass) |
