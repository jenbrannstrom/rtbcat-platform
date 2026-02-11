# Phase 3: Precompute Completeness Implementation (C-PRE-002 + C-PRE-003)

**Date:** 2026-02-11
**Branch:** unified-platform

## Root Cause

### C-PRE-002: home_config_daily missing ACTIVE configs

**FACT:** `home_config_daily` is populated exclusively from BigQuery `rtb_daily`,
grouped by `(metric_date, buyer_account_id, billing_id)`, filtering
`billing_id IS NOT NULL AND billing_id != ''` (`home_precompute.py:229-256`).

**FACT:** If an ACTIVE config's billing_id has zero traffic in the BQ window, no
row is produced. The precompute is traffic-driven only.

**FACT:** No gap-fill step existed to ensure ACTIVE configs appear with zero metrics.

**Root cause:** 4 ACTIVE configs with zero traffic were silently omitted from
precompute output, making them invisible in the dashboard.

### C-PRE-003: config_publisher_daily empty for 2/4 buyers

**FACT:** The BQ query for `config_publisher_daily` (`config_precompute.py:487-523`)
self-joins `rtb_daily` — alias `q` provides `billing_id`, alias `b` provides
`publisher_id`. The join requires BOTH to be non-null.

**FACT:** Buyer 6574658621 has zero `publisher_id` rows in `rtb_daily` (B7 baseline:
`with_both: 0`). No amount of join logic can produce results from absent data.

**FACT:** Buyer 299038253 has 75,744 rtb_daily rows with both `billing_id` and
`publisher_id` present, but the BQ self-join missed them (BQ table may lag).

**Root cause:** BQ self-join fails when publisher_id absent; no local Postgres
fallback existed.

## Code Changes

### 1. `services/home_precompute.py`

Added gap-fill SQL inside `_run(conn)` after BQ-sourced INSERT for `home_config_daily`:

```sql
INSERT INTO home_config_daily
    (metric_date, buyer_account_id, billing_id,
     reached_queries, impressions, bids_in_auction, auctions_won)
SELECT d::date, pc.bidder_id, pc.billing_id, 0, 0, 0, 0
FROM pretargeting_configs pc
JOIN buyer_seats bs ON bs.bidder_id = pc.bidder_id AND bs.active = true
CROSS JOIN UNNEST(%s::text[]) AS d
WHERE pc.state = 'ACTIVE'
  AND pc.billing_id IS NOT NULL
  AND pc.billing_id != ''
  {buyer_filter}
ON CONFLICT (metric_date, buyer_account_id, billing_id) DO NOTHING
```

Key properties:
- Joins `buyer_seats active=true` — inactive buyer configs excluded
- Respects exact refresh date window (same `date_list` as BQ queries)
- Respects buyer-scoped mode (`buyer_account_id` filter when provided)
- `ON CONFLICT DO NOTHING` — real BQ traffic data always wins

### 2. `services/config_precompute.py`

Added Postgres fallback SQL inside `_run(conn)` after BQ-sourced INSERT for
`config_publisher_daily`:

```sql
INSERT INTO config_publisher_daily
    (metric_date, buyer_account_id, billing_id, publisher_id,
     publisher_name, reached_queries, impressions, spend_micros)
SELECT
    metric_date::text, buyer_account_id, billing_id, publisher_id,
    MAX(publisher_name), SUM(reached_queries), SUM(impressions),
    SUM(spend_micros)
FROM rtb_daily
WHERE metric_date::text = ANY(%s)
  AND billing_id IS NOT NULL AND billing_id != ''
  AND publisher_id IS NOT NULL AND publisher_id != ''
  AND buyer_account_id IS NOT NULL AND buyer_account_id != ''
  {buyer_filter}
GROUP BY metric_date, buyer_account_id, billing_id, publisher_id
ON CONFLICT (...) DO NOTHING
```

Key properties:
- Runs after BQ INSERT in same transaction
- `ON CONFLICT DO NOTHING` — BQ-sourced data takes priority, only fills gaps
- Captures rows where both billing_id and publisher_id exist on same rtb_daily row
- Respects buyer-scoped mode

### 3. `tests/test_precompute_completeness.py` (NEW)

8 environment-independent tests:
1. Gap-fill creates zero-rows for active configs without traffic
2. Zero-traffic active config is visible in precompute (critical test)
3. Publisher fallback fills from rtb_daily when BQ missed
4. Multi-buyer isolation — buyer-scoped gap-fill, no cross-leakage
5. Null/empty billing_id configs excluded from gap-fill
6. Idempotent rerun — no duplicate inflation
7. Inactive buyer configs excluded from gap-fill
8. Publisher fallback does not overwrite BQ data

## Test Output

```
tests/test_precompute_completeness.py::test_gap_fill_creates_zero_rows_for_active_configs PASSED [ 12%]
tests/test_precompute_completeness.py::test_zero_traffic_active_config_visible_in_precompute PASSED [ 25%]
tests/test_precompute_completeness.py::test_publisher_fallback_fills_from_rtb_daily PASSED [ 37%]
tests/test_precompute_completeness.py::test_multi_buyer_isolation PASSED [ 50%]
tests/test_precompute_completeness.py::test_null_empty_billing_id_excluded_from_gap_fill PASSED [ 62%]
tests/test_precompute_completeness.py::test_idempotent_rerun_no_duplicates PASSED [ 75%]
tests/test_precompute_completeness.py::test_inactive_buyer_excluded_from_gap_fill PASSED [ 87%]
tests/test_precompute_completeness.py::test_publisher_fallback_does_not_overwrite_bq_data PASSED [100%]
8 passed in 0.04s
```

All Phase 1+2 tests also pass (20/20 total).

## Runtime Evidence (2026-02-11)

Backfill executed via direct SQL on `catscan-production-sg`, 30-day window
(2026-01-13 to 2026-02-11).

### Backfill Results

| Operation | Rows |
|-----------|------|
| Gap-filled home_config_daily | 410 |
| Publisher fallback config_publisher_daily | 17,486 |

### Post-fill: Gap Summary Per Buyer

| buyer_id | configured_active | observed_precompute | gap |
|----------|------------------|--------------------|----|
| 1487810529 | 10 | 10 | **0** |
| 299038253 | 10 | 10 | **0** |
| 6574658621 | 10 | 10 | **0** |
| 6634662463 | 4 | 4 | **0** |

### Post-fill: Config Partition (has_traffic / zero_filled / still_missing)

| buyer_id | has_traffic | zero_filled | still_missing |
|----------|-----------|------------|--------------|
| 1487810529 | 10 | 0 | **0** |
| 299038253 | 7 | 3 | **0** |
| 6574658621 | 9 | 1 | **0** |
| 6634662463 | 4 | 0 | **0** |

**still_missing = 0 for all buyers.**

Zero-filled configs:
- 299038253: 137175951277 (BR\iD\MY\TH\VN/ - WL), 153322387893 (BRAZ, Android-919WL), 158323666240 (BR PH com.spotify.music)
- 6574658621: 173162721799 (IDN_Banner_Instl)

### Post-fill: config_publisher_daily Coverage (7d)

| buyer_account_id | distinct_billing_ids | distinct_publishers | total_rows |
|------------------|---------------------|--------------------|-----------|
| 1487810529 | 11 | 2,603 | 32,072 |
| 299038253 | 7 | 393 | 873 |
| 6634662463 | 5 | 718 | 11,068 |

**Buyer 6574658621 absent** — justified exception: rtb_daily has zero
`publisher_id` rows for this buyer (B7 baseline: `with_publisher: 0`,
`with_both: 0`). CSV reports for this buyer do not include publisher dimension.

### Before/After Comparison

| Metric | BEFORE | AFTER |
|--------|--------|-------|
| home_config_daily gap (total) | 4 | **0** |
| Buyer 299038253 gap | 3 | **0** |
| Buyer 6574658621 gap | 1 | **0** |
| config_publisher_daily buyers | 2/4 | **3/4** |
| 299038253 publisher rows | 0 | 873 |
| 6574658621 publisher rows | 0 | 0 (justified) |

## C-PRE-003 Justified Exception: Buyer 6574658621

**FACT:** `rtb_daily` has 5,252,833 rows for buyer 6574658621 in the 7-day window.
**FACT:** Zero of those rows have a non-empty `publisher_id`.
**FACT:** The CSV report type for this buyer does not include publisher dimension.
**INFERENCE:** No code change can produce publisher data that doesn't exist in the source.

The contract C-PRE-003 states: "Some CSV report types genuinely don't include
publisher_id. The contract should tolerate this with explicit state labeling."

This buyer's `config_publisher_daily` gap is explicitly documented as a source data
limitation, not a pipeline bug. The `fact_dimension_gaps_daily` table already tracks
`publisher_missing_pct` for auditing.

## Contract Status

| Contract | Status | Notes |
|----------|--------|-------|
| C-PRE-002 | **PASS** | All ACTIVE configs have ≥1 row in home_config_daily (7d window). Gap = 0 for all 4 active buyers. 4 zero-traffic configs visible via gap-fill. |
| C-PRE-003 | **PASS (3/4 buyers)** | config_publisher_daily non-empty for all buyers WITH publisher data in rtb_daily. Buyer 6574658621 excluded as justified exception (zero publisher_id in source data). |
| C-ING-001 | **PASS** | Not modified (regression: 7/7 tests pass) |
| C-ING-002 | **PASS** | Not modified (regression: 7/7 tests pass) |
| C-EPT-001 | **PASS** | Not modified (regression: 5/5 tests pass) |
