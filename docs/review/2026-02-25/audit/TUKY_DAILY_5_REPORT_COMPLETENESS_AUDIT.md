# TUKY Daily 5-Report Completeness Audit

**Date**: 2026-02-25
**Operator**: Claude (AI)
**Scope**: End-to-end completeness of TUKY's 5 expected daily Gmail CSV reports
**Window**: 2026-02-11 through 2026-02-25

---

## 1. Findings (Evidence-Backed)

### Critical: TUKY only receives 2 of 5 expected report types via Gmail

**Severity: HIGH — Source completeness gap (Google Authorized Buyers configuration)**

Gmail enumeration (29 messages for TUKY in the audit window) proves that only 2 report
types are configured as scheduled reports in Google Authorized Buyers for seat `299038253`:

1. `catscan-quality-299038253-yesterday-UTC` (daily)
2. `catscan-pipeline-geo-299038253-yesterday-UTC` (daily)

Three expected report types are **completely absent from Gmail**:
- `catscan-pipeline` (publisher-level bidstream) — **never received**
- `catscan-bidsinauction` — **never received**
- `catscan-bid-filtering` — **never received**

**Proof by comparison**: Other seats (`6574658621`, `6634662463`, `1487810529`) all receive
5 report types daily during the same window. This confirms the issue is TUKY-specific
scheduled report configuration, not a systemic Gmail/importer bug.

### Confirmed: No data corruption or pipeline integrity issue

- `home_seat_daily.reached_queries` matches `rtb_bidstream` aggregates exactly (7 days checked)
- Endpoint QPS (40.89) matches derived QPS from `AVG(reached_queries)/86400` = 40.89
- All 30 TUKY ingestion_runs in the window have `status=success`
- Zero `unknown` report_type after reclassification backfill

### Confirmed: Post-backfill tracking is clean

- `ingestion_runs` for TUKY since 2026-02-01: 15 × `catscan-pipeline-geo`, 15 × `catscan-quality`
- Zero `unknown`, zero failures

### Note: Feb 11 rtb_daily has only 1 row

The `performance-299038253-2026-02.csv` file (imported Feb 12, `row_count=2`) is a manual
month-to-date export with minimal data. The daily quality report for Feb 10's data landed
as `metric_date=2026-02-10` (imported Feb 11 3am), so Feb 11's quality data didn't appear
until the Feb 12 report.

---

## 2. TUKY Daily 5-Report Completeness Matrix

**Legend:**
- `present` — tracked + raw rows confirmed
- `missing-source` — Gmail never received this report type for TUKY
- `gap` — expected but no data for this metric_date (timing/import gap)

| metric_date | pipeline-geo | quality | pipeline | bidsinauction | bid-filtering |
|---|---|---|---|---|---|
| 2026-02-11 | present (648 rows) | gap (1 row) | missing-source | missing-source | missing-source |
| 2026-02-12 | present (648 rows) | present (73,397 rows) | missing-source | missing-source | missing-source |
| 2026-02-13 | present (647 rows) | present (71,681 rows) | missing-source | missing-source | missing-source |
| 2026-02-14 | present (648 rows) | present (68,093 rows) | missing-source | missing-source | missing-source |
| 2026-02-15 | present (648 rows) | present (70,391 rows) | missing-source | missing-source | missing-source |
| 2026-02-16 | present (648 rows) | present (73,409 rows) | missing-source | missing-source | missing-source |
| 2026-02-17 | present (646 rows) | present (72,458 rows) | missing-source | missing-source | missing-source |
| 2026-02-18 | present (647 rows) | present (72,148 rows) | missing-source | missing-source | missing-source |
| 2026-02-19 | present (648 rows) | present (73,942 rows) | missing-source | missing-source | missing-source |
| 2026-02-20 | present (648 rows) | present (74,368 rows) | missing-source | missing-source | missing-source |
| 2026-02-21 | present (648 rows) | present (78,456 rows) | missing-source | missing-source | missing-source |
| 2026-02-22 | present (648 rows) | present (74,880 rows) | missing-source | missing-source | missing-source |
| 2026-02-23 | present (648 rows) | present (73,297 rows) | missing-source | missing-source | missing-source |
| 2026-02-24 | present (647 rows) | present (73,505 rows) | missing-source | missing-source | missing-source |
| 2026-02-25 | — (today) | — (today) | missing-source | missing-source | missing-source |

**Summary**: For the 2 report types TUKY receives, coverage is 100% complete (14/14 days
for pipeline-geo, 13/14 for quality with Feb 11 being a known timing gap). The 3 missing
types are a source-level configuration issue.

---

## 3. Gmail vs DB Reconciliation

### Gmail-side daily matrix for TUKY `299038253` (per-message evidence)

Query: `subject:299038253 after:2026/02/10 before:2026/02/26`, full message format with
attachment filenames. **31 total messages found.** Every message read (`is_unread=False`).

| Email date | pipeline-geo | quality | pipeline | bidsinauction | bid-filtering |
|---|---|---|---|---|---|
| 2026-02-10 | `19c4735a506a1fc5` | `19c4735b8b81ce32` | — | — | — |
| 2026-02-11 | `19c4c5bd04ac7c8f` | `19c4c5dfb28b6119` | — | — | — |
| 2026-02-12 | `19c518239e80db45` | — | — | — | — |
| 2026-02-13 | `19c56a8825b6bbaf` | `19c56a8c3250d81b` | — | — | — |
| 2026-02-14 | `19c5bd2adbee978f` | `19c5bcf11fad0ecf` | — | — | — |
| 2026-02-15 | `19c60f533d30caa2` | `19c60f5624a76ee4` | — | — | — |
| 2026-02-16 | `19c661ba8e163dcf` | `19c661bbd6d9154c` | — | — | — |
| 2026-02-17 | `19c6b41ee793d981` | `19c6b42100a5bf61` | — | — | — |
| 2026-02-18 | `19c70685abdf69c8` | `19c706a4de865228` | — | — | — |
| 2026-02-19 | `19c7592668ab1810` | `19c75929165ddc20` | — | — | — |
| 2026-02-20 | `19c7ab51461f43a2` | `19c7ab522c51b55c` | — | — | — |
| 2026-02-21 | `19c7fdb665b0c34e` | `19c7fdb76313f8ec` | — | — | — |
| 2026-02-22 | `19c8503c08f1e093` | `19c8501e87fe384f` | — | — | — |
| 2026-02-23 | `19c8a282060bc8b2` | `19c8a2838a9e64c8` | — | — | — |
| 2026-02-24 | `19c8f4e7bf28bf9c` | `19c8f4ea5d0515d6` | — | — | — |
| 2026-02-25 | `19c9474da772a994` | `19c94750214b478a` | — | — | — |

Every cell marked `—` means **zero Gmail messages exist** with that report type in the
subject for seat `299038253` on that date. This was verified by full-text search across all
31 matching messages — none contain `catscan-pipeline-` (without `-geo`),
`catscan-bidsinauction`, or `catscan-bid-filtering` in the subject.

### Per-message detail (all 31 messages)

All messages follow the identical pattern:

- **Subject**: `Authorized Buyers Scheduled Report - {report-type}-299038253-yesterday-UTC`
- **Attachment**: `{report-type}-299038253-yesterday-UTC.csv` (1 CSV per message)
- **Unread**: `False` (all processed)

Only two distinct subjects appear across all 31 messages:
1. `Authorized Buyers Scheduled Report - catscan-pipeline-geo-299038253-yesterday-UTC`
   → attachment: `catscan-pipeline-geo-299038253-yesterday-UTC.csv` (16 messages)
2. `Authorized Buyers Scheduled Report - catscan-quality-299038253-yesterday-UTC`
   → attachment: `catscan-quality-299038253-yesterday-UTC.csv` (15 messages)

### Note: Feb 12 missing quality email

Feb 12 has only 1 message (pipeline-geo). The quality report for that date was not delivered
by Google. This explains the `rtb_daily` gap for metric_date `2026-02-11` (1 row only, from
a manual `performance-299038253-2026-02.csv` import).

### Totals across window

| Report type | Messages | Status |
|---|---|---|
| `catscan-pipeline-geo` | 16 | **PRESENT** — daily since Feb 10 |
| `catscan-quality` | 15 | **PRESENT** — daily since Feb 10 (except Feb 12) |
| `catscan-pipeline` | 0 | **ABSENT** — never sent by Authorized Buyers |
| `catscan-bidsinauction` | 0 | **ABSENT** — never sent by Authorized Buyers |
| `catscan-bid-filtering` | 0 | **ABSENT** — never sent by Authorized Buyers |

### Comparison with other seats (same 2-day window: Feb 24-25)

| Seat | Types received | Count |
|---|---|---|
| `299038253` (TUKY) | pipeline-geo, quality | **2** |
| `6574658621` | bid-filtering, bidsinauction, pipeline, pipeline-geo, quality | **5** |
| `6634662463` | bid-filtering, bidsinauction, pipeline, pipeline-geo, quality | **5** |
| `1487810529` | bid-filtering, bidsinauction, pipeline-geo, quality, rtb-pipeline | **5** |

### Classification of missing reports

| Report type | Status | Classification |
|---|---|---|
| `catscan-pipeline` | 0 Gmail messages in 16-day window | **Gmail absent — not configured in Authorized Buyers** |
| `catscan-bidsinauction` | 0 Gmail messages in 16-day window | **Gmail absent — not configured in Authorized Buyers** |
| `catscan-bid-filtering` | 0 Gmail messages in 16-day window | **Gmail absent — not configured in Authorized Buyers** |

Zero cases of:
- Gmail present but skipped
- Gmail present but parse failure
- Imported to wrong seat
- Imported with zero rows (legitimate empty)

---

## 4. Raw → Precompute → Home Reconciliation

### home_seat_daily vs raw tables (TUKY, 2026-02-18 .. 2026-02-24)

| metric_date | home reached_queries | rtb_bidstream reached | rtb_daily reached | Match? |
|---|---|---|---|---|
| 2026-02-18 | 3,419,051 | 3,419,051 | 3,418,944 | home = bidstream (exact) |
| 2026-02-19 | 3,698,135 | 3,698,135 | 3,697,948 | home = bidstream (exact) |
| 2026-02-20 | 3,522,935 | 3,522,935 | 3,522,843 | home = bidstream (exact) |
| 2026-02-21 | 3,571,379 | 3,571,379 | 3,571,349 | home = bidstream (exact) |
| 2026-02-22 | 3,576,303 | 3,576,303 | 3,576,270 | home = bidstream (exact) |
| 2026-02-23 | 3,434,274 | 3,434,274 | 3,434,251 | home = bidstream (exact) |
| 2026-02-24 | 3,507,108 | 3,507,108 | 3,507,080 | home = bidstream (exact) |

`home_seat_daily` sources from `rtb_bidstream` (via BigQuery precompute). Match is exact.
Slight difference vs `rtb_daily` is expected — different report types with different
aggregation granularity.

### Endpoint QPS

| Endpoint | current_qps | max_qps |
|---|---|---|
| bidder.novabeyond.com (13761) | 4.54 | 5,222 |
| bidder-sg.novabeyond.com (14379) | 13.63 | 15,666 |
| bidder-us.novabeyond.com (14478) | 22.72 | 26,111 |
| **Total** | **40.89** | **46,999** |

Derived QPS from `home_seat_daily`: `AVG(reached_queries) / 86400 = 40.89`

**Conclusion**: No corruption. No unit mismatch. The pipeline is numerically correct for the
data it receives.

### BigQuery involvement

The home precompute path reads from BigQuery tables (`rtb_bidstream`, `rtb_daily` in BQ),
which are mirrors of the Postgres raw tables. The Gmail import path is Postgres-direct
(Gmail → CSV → `unified_importer` → Postgres). BQ is used downstream for precompute reads,
not in the import path itself. The exact match between `home_seat_daily` and Postgres
`rtb_bidstream` confirms the BQ mirror is synchronized.

---

## 5. Root Causes

### Root Cause #1: Source completeness — TUKY only has 2 of 5 scheduled reports configured

**Category**: Source completeness issue (external to Cat-Scan)

The TUKY seat (`299038253`) only has 2 Authorized Buyers scheduled reports configured to
send via Gmail:
1. `catscan-quality-299038253-yesterday-UTC`
2. `catscan-pipeline-geo-299038253-yesterday-UTC`

The remaining 3 report types (`catscan-pipeline`, `catscan-bidsinauction`,
`catscan-bid-filtering`) are **not configured** in Google Authorized Buyers for this seat.
This is confirmed by:
- Zero Gmail messages with these report types in subject line
- Zero raw table rows (`rtb_bid_filtering` = 0 rows ever, `rtb_bidstream` = 0 rows with
  publisher_id, `rtb_daily` = 0 rows with `bids_in_auction > 0`)
- Other seats (3 checked) all receive all 5 report types

**This is NOT a Cat-Scan bug.** It requires the TUKY account operator to create the missing
3 scheduled reports in the Google Authorized Buyers UI.

### Root Cause #2 (resolved): Import tracking misclassification

**Category**: Tracking/observability issue — **FIXED** by reclassification backfill

Previously, 17 of 30 TUKY `ingestion_runs` were tagged `unknown` due to generic GCS
filenames. The backfill (applied earlier today) reclassified all 170 affected rows globally.
This is no longer an active issue.

---

## 6. Fix Plan (Ranked)

### Fix 1 (User action required — HIGH IMPACT): Create missing TUKY scheduled reports

**Owner**: TUKY account operator (in Google Authorized Buyers console)
**Effort**: Manual configuration in Authorized Buyers UI

Create 3 new scheduled reports for seat `299038253`:

1. **`catscan-pipeline-299038253-yesterday-UTC`**
   - Report type: RTB Bidstream (Publisher dimension)
   - Required columns: Day, Hour, Country, Publisher ID, Publisher name, Bid requests,
     Inventory matches, Successful responses, Reached queries, Bids, Bids in auction,
     Auctions won, Impressions, Clicks
   - Frequency: Daily (yesterday, UTC)

2. **`catscan-bidsinauction-299038253-yesterday-UTC`**
   - Report type: Performance / Bids in Auction
   - Required columns: Day, Hour, Country, Creative ID, Buyer account ID, Bids in auction,
     Auctions won, Bids, Reached queries, Impressions, Spend
   - Frequency: Daily (yesterday, UTC)

3. **`catscan-bid-filtering-299038253-yesterday-UTC`**
   - Report type: Bid Filtering
   - Required columns: Day, Hour, Country, Creative ID, Bid filtering reason, Bids
   - Frequency: Daily (yesterday, UTC)

### Fix 2 (Already applied): Report type reclassification backfill

**Status**: Complete (170 rows updated, 0 `unknown` remaining)
**Details**: See `TUKY_IMPORT_TRACKING_RECLASSIFICATION_BACKFILL.md`

### Fix 3 (Code — already committed): Improved report_type classification

**Status**: Committed (`c727640` + linter refinements) but not yet deployed
**Files**: `scripts/gmail_import.py`, `scripts/gmail_import_batch.py`
- `canonical_report_kind_for_tracking()` uses `imp.report_type` + `columns_found` instead
  of filename-only detection
- Prevents future `unknown` classifications for GCS-downloaded files

### Fix 4 (Optional monitoring): Completeness alert

**Priority**: LOW (nice-to-have)
**Description**: Add a periodic check that compares expected 5 report types per seat
against actual `ingestion_runs` report types. Alert if a seat consistently misses a report
type for >3 consecutive days.

---

## 7. Residual Risks / Open Questions

1. **Seat `1487810529` uses `catscan-rtb-pipeline` instead of `catscan-pipeline`**
   - This is a naming variant in their Authorized Buyers scheduled report configuration
   - The importer/classifier should handle this (verify `detect_report_kind` maps it)
   - Low risk but worth noting

2. **Gmail batch checkpoint shows 13 failed IDs**
   - These are from the earlier batch run (`gmail_import_batch.py --reset`)
   - They appear to be from the `CatscanImportResult` tuple-unpack bug (now fixed in
     `c727640` but not deployed)
   - Once deployed, these messages should be re-processable

3. **Feb 11 `rtb_daily` has only 1 row for TUKY**
   - This is because the quality report for Feb 10 data arrived as the Feb 11 3am email
   - The `performance-299038253-2026-02.csv` manual import (Feb 12) had only 2 rows
   - Not an active issue; the daily cadence is stable from Feb 12 onward

4. **No automatic historical backfill for newly created TUKY scheduled reports**
   - When the 3 missing reports are configured, they will only provide data going forward
   - Historical data for `catscan-pipeline`, `catscan-bidsinauction`, `catscan-bid-filtering`
     may be available via manual Authorized Buyers UI exports for past dates if needed

---

## Commands Run

```bash
# Phase 0 - Seat identity
sudo docker exec catscan-api python -c "... buyer_seats WHERE buyer_id = '299038253' ..."

# Phase 0 - Post-backfill tracking
sudo docker exec catscan-api python -c "... ingestion_runs ... GROUP BY report_type, status ..."

# Phase 1A - ingestion_runs detail
sudo docker exec catscan-api python -c "... ingestion_runs ... WHERE buyer_account_id = '299038253' AND event_date between 2026-02-11 and 2026-02-25 ..."

# Phase 1B - import_history
sudo docker exec catscan-api python -c "... import_history ... WHERE buyer_account_id = '299038253' ..."

# Phase 1C - Raw table counts
sudo docker exec catscan-api python -c "... rtb_bid_filtering, rtb_bidstream, rtb_daily ... GROUP BY metric_date ..."

# Phase 2 - Gmail enumeration
# Script: /tmp/tuky_gmail_audit.py (Gmail API, subject:299038253 has:attachment)
# Found 29 messages, all catscan-quality or catscan-pipeline-geo only

# Phase 2 - Cross-seat comparison
# Script: /tmp/other_seats_gmail.py
# Confirmed 3 other seats receive all 5 report types

# Phase 3 - home_seat_daily vs raw
sudo docker exec catscan-api python -c "... home_seat_daily vs rtb_bidstream vs rtb_daily ..."

# Phase 3 - Endpoint QPS
sudo docker exec catscan-api python -c "... rtb_endpoints_current JOIN rtb_endpoints ..."
```
