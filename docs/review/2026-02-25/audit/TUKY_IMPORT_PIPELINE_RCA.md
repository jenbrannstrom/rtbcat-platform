# TUKY Import Pipeline RCA (End-to-End)

**Date:** 2026-02-25
**Operator:** Claude (automated)
**Target account:** `299038253` ("Tuky Display")
**Audit window:** 2026-02-18 through 2026-02-24

---

## 1. Findings (Evidence-backed)

### HIGH — Import tracking misclassification (tracking/observability bug)

- `detect_report_kind()` in `scripts/gmail_import.py:290-303` only recognizes 5 canonical filename tokens: `catscan-bid-filtering`, `catscan-bidsinauction`, `catscan-pipeline-geo`, `catscan-pipeline`, `catscan-quality`.
- `download_from_url()` in `scripts/gmail_import.py:843` renames GCS-downloaded files to `catscan-report-{seat_id}-{timestamp}.csv` — a generic name that matches **none** of the 5 canonical patterns.
- `record_import_run()` receives `report_kind = detect_report_kind(filepath.name)`, which returns `"unknown"` for all GCS-downloaded files.
- **Prod evidence:** 17 of 30 TUKY `ingestion_runs` since Feb 10 have `report_type='unknown'`, all `status='success'`. Only 12 runs from manual uploads with canonical filenames got correct types (7 `catscan-pipeline-geo`, 5 `catscan-quality`).
- **Impact:** Import UI matrix shows only 2 of 5 CSV types for TUKY despite all types being successfully imported.

### MEDIUM — Batch script CatscanImportResult unpack bug

- `scripts/gmail_import_batch.py:191` unpacks `import_to_catscan()` return as 5-tuple, but it returns a `CatscanImportResult` object.
- Actual DB imports succeed (rows inserted before the error), but `record_import_run()` is skipped and batch counters are wrong.
- Deployed image `sha-f6c83e7` still has this bug in the batch script.

### LOW — Home endpoint "Observed" values are QPS, not daily counts (UX labeling)

- User expected ~3.5M reached queries but saw `4.5`, `13.6`, `22.7` on Home.
- These are correct QPS values: `avg_reached_per_day / 86400 = 40.89 QPS`, distributed across 3 endpoints by `maximum_qps` ratio.
- No data corruption.

---

## 2. TUKY Numeric Reconciliation

### Source data (home_seat_daily, 7 days)

| Date | reached_queries | impressions |
|---|---|---|
| 2026-02-18 | 3,419,051 | 826,622 |
| 2026-02-19 | 3,698,135 | 857,468 |
| 2026-02-20 | 3,522,935 | 846,509 |
| 2026-02-21 | 3,571,379 | 837,459 |
| 2026-02-22 | 3,576,303 | 862,878 |
| 2026-02-23 | 3,434,274 | 839,914 |
| 2026-02-24 | 3,507,108 | 829,810 |

**7-day totals:** 24,729,185 reached / 5,900,660 impressions
**Average per day:** 3,532,741 reached / 842,951 impressions

### Derived QPS

- `avg_reached_per_day / 86400 = 40.888 QPS` (matches attached CSV expectation of ~3.5M/day)

### Endpoint current_qps (rtb_endpoints_current)

| endpoint_id | maximum_qps | current_qps |
|---|---|---|
| 13761 | 5,222 | 4.543 |
| 14379 | 15,666 | 13.629 |
| 14478 | 26,111 | 22.716 |

**Sum current_qps:** 40.888

### QPS derivation formula (confirmed)

`endpoints_repo.py:128-133`:
```sql
SUM(hsd.reached_queries)::real
    / GREATEST(COUNT(DISTINCT hsd.metric_date), 1)
    / 86400 AS observed_qps
```
Then distributed by endpoint `maximum_qps / total_max_qps` ratio.

### Conclusion: **NOT corruption.** Unit mismatch — Home shows per-endpoint QPS derived from daily reached_queries, matching screenshot values exactly.

---

## 3. Import Tracking Audit

### ingestion_runs by report_type (TUKY, since Feb 10)

| report_type | runs | success_runs | latest_run |
|---|---|---|---|
| `unknown` | 17 | 17 | 2026-02-25 12:53 |
| `catscan-pipeline-geo` | 7 | 7 | 2026-02-19 17:44 |
| `catscan-quality` | 5 | 5 | 2026-02-19 17:49 |
| `performance_detail` | 1 | 1 | 2026-02-12 02:42 |

### import_history filenames

- **Generic names** (`catscan-report-299038253-*.csv`): all marked `unknown` — these are GCS-downloaded files from Gmail auto-import
- **Canonical names** (`catscan-quality-*`, `catscan-pipeline-geo-*`): correctly classified — these are manual uploads with original filenames
- All 30 entries show `status=complete` with 647–78,456 rows each

### What's actually in the data (by row count pattern)

- ~648 rows/import → `rtb_bidstream` geo/publisher data (matches `rtb_bidstream` 647-648 rows/day for TUKY)
- ~72K-78K rows/import → `rtb_daily` performance detail (matches `rtb_daily` 72K-78K rows/day for TUKY)
- The "unknown" imports contain both rtb_daily and rtb_bidstream data — they are correctly imported but misclassified in tracking

### Raw table evidence (TUKY, Feb 18-24)

| Table | Rows/day | Days covered |
|---|---|---|
| `rtb_daily` | 72K-78K | 7/7 |
| `rtb_bidstream` | 647-648 | 7/7 |
| `rtb_bid_filtering` | 0 | 0/7 |
| `rtb_quality` | 0 | 0/7 |
| `rtb_publisher_daily` | 0 | 0/7 |

**Note:** `rtb_bid_filtering` and `rtb_quality` having zero TUKY rows may be expected if TUKY's Gmail reports don't include those CSV types, or if those types were only imported manually (pre-Feb 19 canonical uploads). `rtb_publisher_daily` being empty for TUKY suggests the precompute for publisher breakdowns either hasn't run or doesn't cover this seat.

---

## 4. Unread Straggler Classification

**Current state:** 30 unread Gmail report emails (down from 33 at session start).

**Batch checkpoint (from earlier run today):**
- 15 emails found, all processed
- 13 imported successfully (~3M rows total) but recorded as "failed" due to CatscanImportResult unpack bug
- 2 emails had no CSV (GCS auth failed + no attachment fallback)
- Scheduled importer processed 3 more since then (30 → 30 remained after scheduler run)

**Classification (best estimate from available evidence):**
- The 30 "unread" emails are likely already-processed messages where the Gmail mark-as-read succeeded for the import but the straggler count reflects older messages that were processed in prior runs without mark-as-read (or messages that truly lack downloadable content)
- No evidence of true missed imports in the 7-day window: `rtb_daily` and `rtb_bidstream` have full 7-day coverage for TUKY
- Cannot fully characterize all 30 without inspecting individual message subjects/dates (would require Gmail API enumeration beyond read-only SQL)

---

## 5. Root Causes

### 1. Tracking/observability bug (primary user-visible issue)
`detect_report_kind()` cannot classify GCS-downloaded files because `download_from_url()` uses a generic filename pattern. The Import UI matrix depends on `report_type` from `ingestion_runs`, so it shows only types imported via manual upload with canonical names.

### 2. UX labeling confusion (secondary)
Home "Observed" column shows per-endpoint QPS derived from daily reached_queries, not the raw daily counts. Users comparing the CSV's ~3.5M reached_queries/day to the displayed `4.5` / `13.6` / `22.7` conclude data is corrupted, but these are just different units.

### 3. No data correctness bug found
`home_seat_daily` values match raw table sums. QPS derivation formula is correct. No numeric corruption detected.

---

## 6. Fix Plan (ranked)

### Fix 1: Classify report type from CSV content, not filename (HIGH impact, ~20 lines)
**File:** `scripts/gmail_import.py`
**Function:** `detect_report_kind()` or new `detect_report_kind_from_content(filepath)` helper
**Change:** After download, sniff the first row of the CSV to identify column headers (e.g., `reached_queries` → `performance_detail`; `bid_filtering_status` → `catscan-bid-filtering`; `creative_quality_signal_type` → `catscan-quality`; `country_code` + `bid_requests` → `catscan-pipeline-geo`). Fall back to filename-based detection.
**Also wire in:** `record_import_run()` calls and the batch script's import tracking path.

### Fix 2: Reclassify existing `unknown` ingestion_runs (backfill, ~10 lines)
**File:** New one-off script or inline in `backfill_bidder_ids_pg.py`
**Change:** For `ingestion_runs` where `report_type='unknown'` and `filename` matches `catscan-report-*`, look up the corresponding `import_history` row and infer type from `rows_imported` count pattern or re-sniff the archived CSV if available.

### Fix 3: Fix CatscanImportResult tuple-unpack in batch script (MEDIUM, 1 line)
**File:** `scripts/gmail_import_batch.py:191`
**Change:** Replace `success, report_type, rows_imported, rows_dup, error = import_to_catscan(filepath)` with attribute access on the `CatscanImportResult` object (e.g., `result = import_to_catscan(filepath); success = result.success; ...`).

### Fix 4: Add QPS unit label to Home endpoint UI (LOW, UX)
**File:** `dashboard/src/` Home endpoint component
**Change:** Label the "Observed" column as "Observed QPS" or add a tooltip explaining the derivation.

### No data backfill needed
Raw fact tables have full 7-day coverage for TUKY. The issue is purely in tracking metadata and UI presentation.

---

## 7. Residual Risks

- **30 unread Gmail emails not fully characterized.** Individual message inspection would require Gmail API enumeration; cannot confirm they are all processed without that.
- **`rtb_bid_filtering` and `rtb_quality` zero rows for TUKY.** May be expected (TUKY may not have these report types), but not confirmed against Gmail report subjects.
- **`rtb_publisher_daily` empty for TUKY.** Suggests publisher precompute either doesn't cover this seat or ran before TUKY data was ingested. May need a targeted precompute refresh.
- **`config_publisher_daily` precompute `metric_date::text` bug** was fixed (`2b45dd9`) and deployed, but config breakdowns haven't been refreshed yet on prod.

---

## Commands Run (Reference)

All commands executed read-only against `catscan-production-sg` via IAP tunnel, inside `catscan-api` container using `python + psycopg`.

```
Phase A: buyer_seats lookup, home_seat_daily 7-day query, seat_daily existence check
Phase B: 7-day avg QPS derivation, rtb_endpoints_current query
Phase C: ingestion_runs by report_type, unknown-type detail, import_history filenames
Phase D: gmail_import_batch --status, gmail_import_status.json
Phase E: rtb_daily/rtb_bidstream/rtb_bid_filtering/rtb_quality coverage, rtb_publisher_daily check
Phase F: detect_report_kind() code review, download_from_url() filename pattern, endpoints_repo refresh formula
```
