# Phase 3 Baseline: Precompute Completeness (C-PRE-002 + C-PRE-003)

**Date:** 2026-02-11
**Branch:** unified-platform
**Captured on:** catscan-production-sg (before code changes)

## B1: Active buyers/bidders

| buyer_id | bidder_id | active |
|----------|-----------|--------|
| 1487810529 | 1487810529 | true |
| 299038253 | 299038253 | true |
| 6574658621 | 6574658621 | true |
| 6634662463 | 6634662463 | true |

## B2: ACTIVE configs per buyer

| buyer_id | active_configs | with_billing_id | null_billing |
|----------|---------------|-----------------|-------------|
| 1487810529 | 10 | 10 | 0 |
| 299038253 | 10 | 10 | 0 |
| 6574658621 | 10 | 10 | 0 |
| 6634662463 | 4 | 4 | 0 |

**Total ACTIVE configs:** 34 (all have non-null billing_id)

## B3: home_config_daily coverage (7d window)

| buyer_account_id | distinct_billing_ids | total_reached | total_rows |
|------------------|---------------------|---------------|-----------|
| 1487810529 | 11 | 32,919,000 | 53 |
| 299038253 | 7 | 33,421,991 | 35 |
| 6574658621 | 10 | 2,547,520,765 | 48 |
| 6634662463 | 5 | 671,674,790 | 25 |

Note: Some buyers have billing_ids in home_config_daily that aren't ACTIVE configs
(e.g., billing_id='unknown', or PAUSED configs that had historical traffic).

## B4: config_publisher_daily coverage (7d window)

| buyer_account_id | distinct_billing_ids | distinct_publishers | total_rows |
|------------------|---------------------|--------------------|-----------|
| 1487810529 | 11 | 2,493 | 28,231 |
| 6634662463 | 5 | 710 | 10,477 |

**MISSING:** Buyers 299038253 and 6574658621 have **zero rows**.

## B5: Missing ACTIVE configs from home_config_daily (7d)

| buyer_id | billing_id | display_name |
|----------|-----------|-------------|
| 299038253 | 137175951277 | BR\iD\MY\TH\VN/ - WL |
| 299038253 | 153322387893 | BRAZ, Android-919WL |
| 299038253 | 158323666240 | BR PH com.spotify.music |
| 6574658621 | 173162721799 | IDN_Banner_Instl |

**4 ACTIVE configs** with non-null billing_id have zero rows in home_config_daily.

## B6: Gap summary per buyer

| buyer_id | configured_active | observed_precompute | gap |
|----------|------------------|--------------------|----|
| 1487810529 | 10 | 10 | **0** |
| 299038253 | 10 | 7 | **3** |
| 6574658621 | 10 | 9 | **1** |
| 6634662463 | 4 | 4 | **0** |

**Total gap: 4 ACTIVE configs missing.**

## B7: rtb_daily publisher_id sparseness per buyer (7d)

| buyer_account_id | total_rows | with_publisher | with_billing | with_both |
|------------------|-----------|---------------|-------------|----------|
| 1487810529 | 1,998,365 | 1,998,365 | 1,998,365 | 1,998,365 |
| 299038253 | 274,888 | 75,744 | 274,888 | 75,744 |
| 6574658621 | 5,252,833 | 0 | 5,252,833 | 0 |
| 6634662463 | 1,791,702 | 659,623 | 1,791,702 | 659,623 |

**Critical finding for C-PRE-003:**
- 6574658621: **zero** publisher_id in rtb_daily — no Postgres fallback possible.
  This is a justified data sparsity exception (CSV reports lack publisher dimension).
- 299038253: 75,744 rows with both — fallback will produce config_publisher_daily rows.

## B8: config_publisher_daily total rows per buyer (all time)

| buyer_account_id | total_rows |
|------------------|-----------|
| 1487810529 | 85,337 |
| 6634662463 | 21,620 |

Buyers 299038253 and 6574658621 have **zero rows** all-time.
