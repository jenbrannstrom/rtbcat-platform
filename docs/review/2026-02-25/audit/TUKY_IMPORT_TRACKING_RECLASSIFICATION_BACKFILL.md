# TUKY Import Tracking Reclassification Backfill

**Date**: 2026-02-25
**Operator**: Claude (AI)
**Script**: `scripts/backfill_ingestion_run_report_types.py` (commit `b40639a`)
**Scope**: `ingestion_runs.report_type` reclassification — tracking metadata only, no raw data changes

---

## Background

The TUKY (299038253) "2 of 5 CSVs" issue was traced in the
[Import Pipeline RCA](./TUKY_IMPORT_PIPELINE_RCA.md) to `report_type` misclassification
in `ingestion_runs`. Files downloaded from GCS via Gmail get generic filenames
(`catscan-report-{seat}-{ts}.csv`) that don't contain canonical report-kind tokens,
causing `detect_report_kind()` to tag them as `unknown`.

The backfill script reclassifies these rows using:
1. Canonical filename tokens (first priority)
2. Parser type mapping (`rtb_bidstream_publisher` → `catscan-pipeline`, etc.)
3. `import_history.columns_found` heuristics (fallback for generic filenames)

## Bug Fix Applied During Backfill

The initial version of `classify_from_parser_type()` only branched on known parser
types (`rtb_bidstream_geo`, `rtb_bidstream_publisher`, `bid_filtering`,
`performance_detail`). Rows with `report_type = 'unknown'` fell through without
attempting column-based classification.

Fixes (commit `b40639a`):
- Added `classify_from_columns()` — standalone column-based classifier
- `normalize_col_token()` — normalizes `#`, `_`, spaces so `#Billing ID` = `billing_id`
- `classify_from_parser_type()` now falls back to `classify_from_columns()` for
  unknown/unrecognized parser types
- `performance_detail` branch also delegates to `classify_from_columns()` for richer matching

## Execution

### Step 1 — TUKY-only dry-run

```
buyer-id=299038253, since=2026-02-10

Scanned candidates: 18
Mode: DRY-RUN
Would update: 18
Skipped unresolved: 0
```

All 18 classified correctly:
- 9 × `unknown` → `catscan-pipeline-geo` (columns: `#Country,Buyer account ID,...,Bid requests,...`)
- 8 × `unknown` → `catscan-quality` (columns: `#Billing ID,...,Active view viewable,...`)
- 1 × `performance_detail` → `catscan-quality` (columns: `billing_id,impressions,clicks,spend`)

### Step 2 — TUKY baseline (before apply)

| report_type | runs | success | latest_run |
|---|---|---|---|
| unknown | 17 | 17 | 2026-02-25 12:53 |
| catscan-pipeline-geo | 7 | 7 | 2026-02-19 17:44 |
| catscan-quality | 5 | 5 | 2026-02-19 17:49 |
| performance_detail | 1 | 1 | 2026-02-12 02:42 |

### Step 3 — Broader dry-run (all buyers since 2026-02-01)

```
Scanned candidates: 170
Mode: DRY-RUN
Would update: 170
Skipped unresolved: 0
```

Classifications across all buyers:
- `catscan-pipeline-geo` — rows with `Bid requests` but no `Publisher ID`
- `catscan-pipeline` — rows with `Bid requests` + `Publisher ID`
- `catscan-quality` — rows with `Billing ID` / `Active view`
- `catscan-bidsinauction` — rows with `Bids in auction` / `Auctions won`
- `catscan-bid-filtering` — rows with `Bid filtering reason`

### Step 4 — Apply

```
Scanned candidates: 170
Mode: APPLY
Updated: 170
Skipped unresolved: 0
```

### Step 5 — Verify after apply

**TUKY (299038253) — after:**

| report_type | runs | success | latest_run |
|---|---|---|---|
| catscan-pipeline-geo | 15 | 15 | 2026-02-25 12:53 |
| catscan-quality | 15 | 15 | 2026-02-25 12:52 |

- `unknown`: 17 → **0**
- `performance_detail`: 1 → **0** (reclassified to `catscan-quality`)
- `catscan-pipeline-geo`: 7 → **15** (+8 from unknown)
- `catscan-quality`: 5 → **15** (+9 from unknown, +1 from performance_detail)

**Global (all buyers, since 2026-02-01) — after:**

| report_type | runs |
|---|---|
| catscan-pipeline-geo | 60 |
| catscan-quality | 58 |
| catscan-bid-filtering | 45 |
| catscan-pipeline | 43 |
| catscan-bidsinauction | 40 |
| gmail-scheduled | 12 |
| unknown | **0** |

Zero `unknown` remaining. All 170 rows reclassified into canonical UI categories.

## Notes

- `gmail-scheduled` (12 rows) is a legitimate tracking tag for scheduled Gmail imports, not a misclassification
- No raw data was modified — only `ingestion_runs.report_type` column
- TUKY now correctly shows pipeline-geo and quality imports in the import tracking matrix
- The column-based fallback will also benefit future imports if `canonical_report_kind_for_tracking()` is deployed (commit `c727640` + linter refinements)
