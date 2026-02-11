# Phase 2 Baseline: Endpoint Observed Feed (C-EPT-001)

**Date:** 2026-02-11
**Branch:** unified-platform
**Snapshot taken:** before any code changes

## Root Cause (FACT, not inference)

**No writer code exists for `rtb_endpoints_current`.** The table was created in
migration 032 but nothing in the codebase INSERTs or UPSERTs into it. Exhaustive
grep of INSERT/UPDATE/DELETE on `rtb_endpoints_current` returns zero matches.

The full read path is implemented:
- `endpoints_repo.get_current_qps()` reads SUM(current_qps)
- `home_repo.get_observed_endpoint_rows()` reads per-endpoint rows with JOIN to rtb_endpoints
- `home_analytics_service.get_endpoint_efficiency_payload()` computes efficiency metrics
- When 0 rows exist, `endpoint_delivery_state = "missing"` and alert `ENDPOINT_DELIVERY_MISSING` fires

## Baseline Evidence Queries

### 1. Active buyers/bidders

```sql
SELECT buyer_id, bidder_id, active FROM buyer_seats ORDER BY buyer_id;
```

**Expected:** Active buyer seats exist (synced via `/seats/discover`). The `bidder_id`
values link to `rtb_endpoints.bidder_id`.

### 2. Configured endpoints

```sql
SELECT bidder_id, COUNT(*) AS endpoint_count, SUM(maximum_qps) AS total_allocated_qps
FROM rtb_endpoints GROUP BY bidder_id ORDER BY bidder_id;
```

**Expected:** 3 endpoints for bidder 6574658621 (synced 2026-02-11 02:20 per C-EPT-002).

### 3. Observed endpoints (current)

```sql
SELECT bidder_id, COUNT(*) AS endpoint_count FROM rtb_endpoints_current
GROUP BY bidder_id ORDER BY bidder_id;
```

**BEFORE:** 0 rows. Table is empty.

### 4. Freshness

```sql
SELECT bidder_id, MAX(observed_at) AS last_observed FROM rtb_endpoints_current
GROUP BY bidder_id ORDER BY bidder_id;
```

**BEFORE:** No rows returned.

### 5. Coverage gap

```sql
SELECT e.bidder_id, COUNT(e.*) AS configured, COUNT(c.*) AS observed,
       COUNT(e.*) - COUNT(c.*) AS gap
FROM rtb_endpoints e
LEFT JOIN rtb_endpoints_current c
  ON c.bidder_id = e.bidder_id AND c.endpoint_id = e.endpoint_id
GROUP BY e.bidder_id ORDER BY e.bidder_id;
```

**BEFORE:** gap = configured (100% missing for every bidder).

## Diagnosis Summary

| Hypothesis | Verdict | Evidence |
|------------|---------|----------|
| Writer never called | **CONFIRMED** | No INSERT/UPSERT on rtb_endpoints_current anywhere in codebase |
| Writer called with empty input | N/A | No writer exists |
| Key mismatch | N/A | No writer exists |
| Transaction/upsert conflict | N/A | No writer exists |
| Wrong DB target | N/A | No writer exists |
| Stale job/disabled worker | N/A | No scheduled job or worker references this table |

**Root cause is singular and confirmed:** The table was designed and consumed, but the
producer was never implemented.
