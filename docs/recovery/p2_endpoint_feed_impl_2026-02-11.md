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

## Runtime Evidence (2026-02-11 16:19 UTC)

Backfill executed via `refresh_endpoints_current()` SQL on `catscan-production-sg`.
**11 rows upserted** (was 0).

### Q1: Active buyers/bidders

| buyer_id | bidder_id | active |
|----------|-----------|--------|
| 1487810529 | 1487810529 | true |
| 299038253 | 299038253 | true |
| 6574658621 | 6574658621 | true |
| 6634662463 | 6634662463 | true |

### Q2: Configured endpoints

| bidder_id | endpoints | total_allocated_qps |
|-----------|-----------|---------------------|
| 1487810529 | 2 | 46,000 |
| 299038253 | 3 | 46,999 |
| 6574658621 | 3 | 460,000 |
| 6634662463 | 3 | 304,428 |

### Q3: Observed endpoints current (AFTER)

| bidder_id | endpoints | total_observed_qps |
|-----------|-----------|-------------------|
| 1487810529 | 2 | 44.6 |
| 299038253 | 3 | 77.4 |
| 6574658621 | 3 | 6,299.5 |
| 6634662463 | 3 | 2,064.5 |

### Q4: Freshness

| bidder_id | last_observed |
|-----------|---------------|
| 1487810529 | 2026-02-11 16:19:26 |
| 299038253 | 2026-02-11 16:19:26 |
| 6574658621 | 2026-02-11 16:19:26 |
| 6634662463 | 2026-02-11 16:19:26 |

All within 24h SLA.

### Q5: Coverage gap

| bidder_id | configured | observed | gap |
|-----------|-----------|----------|-----|
| 1487810529 | 2 | 2 | **0** |
| 299038253 | 3 | 3 | **0** |
| 6574658621 | 3 | 3 | **0** |
| 6634662463 | 3 | 3 | **0** |

### Q6: Per-endpoint detail

| bidder_id | endpoint_id | current_qps | observed_at |
|-----------|-------------|-------------|-------------|
| 1487810529 | 16213 | 34.9 | 2026-02-11 16:19:26 |
| 1487810529 | 19587 | 9.7 | 2026-02-11 16:19:26 |
| 299038253 | 13761 | 8.6 | 2026-02-11 16:19:26 |
| 299038253 | 14379 | 25.8 | 2026-02-11 16:19:26 |
| 299038253 | 14478 | 43.0 | 2026-02-11 16:19:26 |
| 6574658621 | 15386 | 136.9 | 2026-02-11 16:19:26 |
| 6574658621 | 15784 | 2,054.2 | 2026-02-11 16:19:26 |
| 6574658621 | 15831 | 4,108.4 | 2026-02-11 16:19:26 |
| 6634662463 | 17620 | 678.2 | 2026-02-11 16:19:26 |
| 6634662463 | 17656 | 1,356.3 | 2026-02-11 16:19:26 |
| 6634662463 | 18435 | 30.0 | 2026-02-11 16:19:26 |

### Before/After comparison

| Metric | BEFORE | AFTER |
|--------|--------|-------|
| rtb_endpoints_current rows | 0 | 11 |
| Bidders with observed data | 0/4 | 4/4 |
| Coverage gap (any bidder) | 11 | 0 |
| endpoint_delivery_state | "missing" | "available" |
| ENDPOINT_DELIVERY_MISSING alert | fires | cleared |

## SG2 Parity Evidence (2026-02-11)

Verification queries run on `catscan-production-sg2` to confirm identical state
to `catscan-production-sg` (SG). Both instances share the same Cloud SQL database,
so data parity is expected and confirmed.

### SG2 Q1: Active buyers/bidders

| buyer_id | bidder_id | active |
|----------|-----------|--------|
| 1487810529 | 1487810529 | true |
| 299038253 | 299038253 | true |
| 6574658621 | 6574658621 | true |
| 6634662463 | 6634662463 | true |

### SG2 Q2: Configured endpoints

| bidder_id | endpoints | total_allocated_qps |
|-----------|-----------|---------------------|
| 1487810529 | 2 | 46,000 |
| 299038253 | 3 | 46,999 |
| 6574658621 | 3 | 460,000 |
| 6634662463 | 3 | 304,428 |

### SG2 Q3: Observed endpoints current

| bidder_id | endpoints | total_observed_qps |
|-----------|-----------|-------------------|
| 1487810529 | 2 | 44.6 |
| 299038253 | 3 | 77.4 |
| 6574658621 | 3 | 6,299.5 |
| 6634662463 | 3 | 2,064.5 |

### SG2 Q4: Freshness

| bidder_id | last_observed |
|-----------|---------------|
| 1487810529 | 2026-02-11 16:19:26 |
| 299038253 | 2026-02-11 16:19:26 |
| 6574658621 | 2026-02-11 16:19:26 |
| 6634662463 | 2026-02-11 16:19:26 |

### SG2 Q5: Coverage gap

| bidder_id | configured | observed | gap |
|-----------|-----------|----------|-----|
| 1487810529 | 2 | 2 | **0** |
| 299038253 | 3 | 3 | **0** |
| 6574658621 | 3 | 3 | **0** |
| 6634662463 | 3 | 3 | **0** |

### SG2 Q6: Per-endpoint detail

| bidder_id | endpoint_id | current_qps | observed_at |
|-----------|-------------|-------------|-------------|
| 1487810529 | 16213 | 34.9 | 2026-02-11 16:19:26 |
| 1487810529 | 19587 | 9.7 | 2026-02-11 16:19:26 |
| 299038253 | 13761 | 8.6 | 2026-02-11 16:19:26 |
| 299038253 | 14379 | 25.8 | 2026-02-11 16:19:26 |
| 299038253 | 14478 | 43.0 | 2026-02-11 16:19:26 |
| 6574658621 | 15386 | 136.9 | 2026-02-11 16:19:26 |
| 6574658621 | 15784 | 2,054.2 | 2026-02-11 16:19:26 |
| 6574658621 | 15831 | 4,108.4 | 2026-02-11 16:19:26 |
| 6634662463 | 17620 | 678.2 | 2026-02-11 16:19:26 |
| 6634662463 | 17656 | 1,356.3 | 2026-02-11 16:19:26 |
| 6634662463 | 18435 | 30.0 | 2026-02-11 16:19:26 |

### SG vs SG2 Parity Comparison

| Metric | SG | SG2 | Match |
|--------|-----|------|-------|
| Active bidders | 4 | 4 | YES |
| Configured endpoints | 11 | 11 | YES |
| rtb_endpoints_current rows | 11 | 11 | YES |
| Bidders with observed data | 4/4 | 4/4 | YES |
| Coverage gap (any bidder) | 0 | 0 | YES |
| Total observed QPS | 8,486.0 | 8,486.0 | YES |
| Max staleness | 2026-02-11 16:19:26 | 2026-02-11 16:19:26 | YES |
| Per-endpoint QPS values | (see Q6) | (see SG2 Q6) | YES (exact) |

**Verdict: PARITY PASS** — All values are identical across SG and SG2. Both
instances connect to the same Cloud SQL database, so row-level identity is expected.
Confirmed: no instance-local caching or divergent state.

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
