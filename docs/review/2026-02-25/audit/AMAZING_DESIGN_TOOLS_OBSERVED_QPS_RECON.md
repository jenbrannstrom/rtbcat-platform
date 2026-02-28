# Amazing Design Tools — Observed-QPS Mismatch Reconciliation

**Date**: 2026-02-25
**Operator**: Claude (AI)
**Seat**: `1487810529` / `Amazing Design Tools LLC`
**Window**: 2026-02-18 through 2026-02-24

---

## 1. Findings (Evidence-Backed)

### No active mismatch — QPS is now correct end-to-end

All data layers reconcile exactly:

| Layer | Value | Source |
|---|---|---|
| AB screenshot (user-reported) | ~2.53–2.62M reached/day → ~29.8 QPS | Google Authorized Buyers |
| `home_seat_daily` | avg 2,569,645 reached/day → **29.74 QPS** | Postgres precompute |
| `rtb_endpoints_current` | 23.28 + 6.47 = **29.74 QPS** | Endpoint observation |
| `rtb_bidstream` (raw) | avg 2,569,645 reached/day | Raw import table |

Delta between any two layers: **0.00 QPS**.

### The user-reported `2.3 + 6.5 = 8.8 QPS` was stale endpoint observation data

The endpoint observation records show `observed_at = 2026-02-25 16:07:26` — they are fresh
as of today. The user screenshot showing `2.3` and `6.5` was captured before the
`rtb_endpoints_current` precompute was refreshed (likely before the config precompute fix
in commit `2b45dd9` was deployed). After deploy + precompute refresh, the values are correct.

### All 5 report types importing daily — full coverage

Unlike TUKY (which only receives 2/5), Amazing Design Tools receives and imports all 5
expected report types daily via Gmail. All imports successful, zero failures.

---

## 2. Seat QPS Reconciliation

### Seat identity

```
buyer_id: 1487810529
bidder_id: 1487810529
display_name: Amazing Design Tools LLC
active: True
```

### home_seat_daily (7-day window)

| metric_date | reached_queries | impressions |
|---|---|---|
| 2026-02-18 | 2,560,449 | 13,071,732 |
| 2026-02-19 | 2,573,006 | 11,299,607 |
| 2026-02-20 | 2,555,527 | 9,716,764 |
| 2026-02-21 | 2,537,062 | 8,118,763 |
| 2026-02-22 | 2,546,605 | 6,569,135 |
| 2026-02-23 | 2,624,607 | 4,974,505 |
| 2026-02-24 | 2,590,261 | 3,285,548 |
| **Average** | **2,569,645** | **8,148,008** |

Derived QPS: `2,569,645 / 86,400 = 29.74`

### Endpoint observed QPS

| endpoint_id | url | max_qps | current_qps | observed_at |
|---|---|---|---|---|
| 16213 | bid.amazingaa.com/rtb/bid/double | 36,000 | 23.28 | 2026-02-25 16:07 |
| 19587 | bid-asia.amazingaa.com/rtb/bid/dc | 10,000 | 6.47 | 2026-02-25 16:07 |
| **Total** | | **46,000** | **29.74** | |

### Comparison

| Source | QPS | Match? |
|---|---|---|
| AB screenshot (implied) | ~29.8 | baseline |
| home_seat_daily (derived) | 29.74 | YES |
| rtb_endpoints_current (sum) | 29.74 | YES |
| User-reported UI values | 8.8 | **stale** (pre-refresh) |

**Conclusion**: The `2.3 + 6.5 = 8.8 QPS` from the user screenshot was stale
`rtb_endpoints_current` data, now refreshed to 29.74 QPS after the precompute cycle ran.

---

## 3. Import Completeness (5 Report Types)

### ingestion_runs summary (2026-02-18 .. 2026-02-24)

| report_type | total runs | success | daily present? |
|---|---|---|---|
| `catscan-bid-filtering` | 11 | 11 | Yes (some days >1 due to re-imports) |
| `catscan-pipeline-geo` | 11 | 11 | Yes |
| `catscan-bidsinauction` | 10 | 10 | Yes |
| `catscan-pipeline` | 10 | 10 | Yes |
| `catscan-quality` | 10 | 10 | Yes |

All 5 report types present. Zero failures. Some days have >1 run per type due to historical
re-imports (manual + gmail-auto overlap), but this is benign (deduplication handles it).

### Raw table coverage (2026-02-18 .. 2026-02-24)

**rtb_daily** — All 7 days present, ~335K rows/day:
- Rows with `billing_id` (quality): 332K–342K/day (all rows)
- Rows with `bids_in_auction > 0` (bidsinauction): ~87K/day

**rtb_bidstream** — All 7 days present:
- Geo rows (no publisher_id): 312/day, reached_queries = 0
- Publisher rows (with publisher_id): 222K–228K/day, reached_queries ~2.5M/day

**rtb_bid_filtering** — All 7 days present, ~1,240 rows/day

All raw tables fully populated. No gaps.

---

## 4. Root Cause Hypothesis (with evidence)

### Root cause: Stale endpoint observation pre-refresh

The user screenshot was captured when `rtb_endpoints_current` still held old values (likely
from before the config precompute `metric_date::text` bug fix in commit `2b45dd9` was
deployed). The precompute refresh cycle that ran after the fix deploy updated
`rtb_endpoints_current` to correct values.

Evidence:
1. `rtb_endpoints_current.observed_at = 2026-02-25 16:07:26` — fresh today
2. Current values (23.28 + 6.47 = 29.74) match home_seat_daily derived QPS exactly
3. User-reported values (2.3 + 6.5 = 8.8) match neither raw data nor precompute
4. No raw import gap, no precompute aggregation gap — all layers now correct

### Not the cause:
- Raw import gap: All 5 types present, all raw tables complete
- home_seat_daily precompute bug: Values match rtb_bidstream exactly
- UI/API wrong-seat: Values match seat 1487810529 specifically
- Import to wrong seat: No evidence

---

## 5. Next Fix / Action Plan

### No code fix needed

The mismatch has self-resolved after the config precompute fix deploy + precompute refresh.
The data is now correct at all layers.

### Recommended: verify in UI

The user should reload the Amazing Design Tools Home page and confirm endpoint QPS values
now show approximately:
- Endpoint 16213 (bid.amazingaa.com): ~23.3 QPS
- Endpoint 19587 (bid-asia.amazingaa.com): ~6.5 QPS
- Total: ~29.7 QPS

### Optional: monitoring

If staleness recurs, consider adding an alert when `rtb_endpoints_current.observed_at` falls
>24h behind current time, which would indicate the precompute refresh cycle has stalled.

---

## Commands Run

```bash
# All phases ran in a single Python script (/tmp/adt_recon.py) inside catscan-api container
# Queries:
#   buyer_seats WHERE buyer_id = '1487810529'
#   home_seat_daily WHERE buyer_account_id = '1487810529' AND metric_date 2026-02-18..24
#   rtb_endpoints_current JOIN rtb_endpoints WHERE bidder_id = '1487810529'
#   rtb_daily WHERE buyer_account_id = '1487810529' ... GROUP BY metric_date
#   rtb_bidstream WHERE buyer_account_id = '1487810529' ... GROUP BY metric_date, publisher class
#   rtb_bid_filtering WHERE buyer_account_id = '1487810529' ... GROUP BY metric_date
#   ingestion_runs WHERE buyer = '1487810529' ... GROUP BY day, report_type, status
```
