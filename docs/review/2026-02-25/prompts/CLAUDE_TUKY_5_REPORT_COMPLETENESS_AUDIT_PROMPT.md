# Claude Prompt: TUKY Daily 5-Report Completeness Audit (Gmail -> Import -> Raw -> Precompute -> Home)

```text
Run a full TUKY completeness audit for the expected **5 Gmail CSV reports per day** and trace them end-to-end into Cat-Scan.

This is the next step after the `unknown` report_type reclassification backfill. We are now auditing **completeness**, not just tracking labels.

Context (important)
- We already proved:
  1) TUKY Home endpoint observed values (`4.5`, `13.6`, `22.7`) were a **unit mismatch** (QPS), not data corruption.
  2) TUKY “2 of 5 CSVs” in the Import UI was partly a **tracking misclassification** (`ingestion_runs.report_type='unknown'`) and a reclassification backfill has been applied.
- We still need to verify whether TUKY is actually receiving/importing all 5 expected report types daily.
- User expectation (for every seat, daily via Gmail): **5 reports**

Expected daily report set (user requirement)
1. `catscan-bidsinauction` -> `rtb_daily`
   Required columns: Day, Country, Creative ID, Buyer account ID, Bids in auction, Auctions won, Bids, Impressions
2. `catscan-quality` -> `rtb_daily`
   Required columns: Day, Pretargeting config (Billing ID), Creative ID, Creative size, Reached queries, Impressions, Active view viewable
3. `catscan-pipeline-geo` -> `rtb_bidstream`
   Required columns: Day, Country, Hour, Bid requests, Bids, Impressions
4. `catscan-pipeline` -> `rtb_bidstream`
   Required columns: Day, Country, Publisher ID, Publisher name, Bid requests, Bids, Impressions
5. `catscan-bid-filtering` -> `rtb_bid_filtering`
   Required columns: Day, Country, Creative ID, Bid filtering reason, Bids

Target test case
- Seat / buyer_id: `299038253` (`Tuky Display`)
- Primary window: `2026-02-11` through `2026-02-25` (covers stragglers + recent runs)
- Focus first on TUKY; if a systemic issue is proven, note how it likely affects other seats.

Goal
Determine, for each day in the window, for each of the 5 expected report types:
- Was a Gmail report email/attachment present?
- Was it seen by the importer?
- Was an `ingestion_runs` row recorded?
- Did import succeed?
- Did rows land in the correct raw table(s)?
- Did precompute/home reflect the data?
- If missing, where exactly did it break (Gmail absent, skipped, parse fail, tracking fail, import fail, zero-row legitimate, etc.)?

Do NOT guess. Produce an evidence-backed per-day x per-report matrix.

Constraints / guardrails
- Prefer read-only prod inspection first.
- Do not rerun mass imports blindly.
- If you need to reprocess a small set of messages for evidence, document exactly what changed.
- Do not claim “all seats are broken” from TUKY alone.
- Do not claim “corruption” unless source and stored values disagree after unit normalization.

Environment
- VM: `catscan-production-sg`
- API container: `catscan-api`
- Use `gcloud compute ssh ... --tunnel-through-iap`
- `psql` is not available in `catscan-api`; use `python + psycopg` inside container for SQL

Artifacts already available (review before starting)
- `docs/review/2026-02-25/audit/TUKY_IMPORT_PIPELINE_RCA.md`
- `docs/review/2026-02-25/audit/TUKY_IMPORT_TRACKING_RECLASSIFICATION_BACKFILL.md`
- `docs/review/2026-02-25/notes/CODEX_TUKY_IMPORT_PIPELINE_LOCAL_CODE_FINDINGS.md`

PHASE 0 — Baseline / sanity check (read-only)
1) Confirm TUKY seat identity and account mapping
- Query `buyer_seats` for `buyer_id='299038253'` and `display_name ILIKE '%Tuky%'`
- Capture `buyer_id`, `bidder_id`, `display_name`, `active`

2) Confirm current post-backfill import tracking counts for TUKY (baseline)
- Query `ingestion_runs` grouped by `report_type`, `status` since `2026-02-01`
- Confirm `unknown=0` for TUKY after the backfill

PHASE 1 — Build the TUKY completeness matrix from production DB (read-only)
Build a matrix with rows = `report_day` (`2026-02-11` .. `2026-02-25`) and columns = 5 expected report types.

For each cell, produce at minimum:
- `tracking_seen` (yes/no)
- `tracking_status` (success/failed/missing)
- `raw_rows_present` (yes/no + row count)
- `notes`

Use these sources:

A) `ingestion_runs` (tracking, importer events)
- Query TUKY rows in window and inspect:
  - `report_type`, `status`, `filename`, `row_count`, `error_summary`, `import_trigger`, `started_at`, `finished_at`
- Group by event day and `report_type`
- Important: event day != report day; do not rely on this alone for final completeness

B) `import_history` (import outcomes + filenames)
- Query TUKY rows in same window
- Capture:
  - `filename`, `rows_imported`, `rows_duplicate`, `status`, `error_message`, `import_trigger`, `imported_at`, `columns_found` (if present)
- Use this to reconcile ambiguous tracking rows

C) Raw table presence by `metric_date` and TUKY buyer
1. `rtb_bid_filtering` -> `catscan-bid-filtering`
- Count rows by `metric_date` for `buyer_account_id='299038253'`

2. `rtb_bidstream` -> split into:
- `catscan-pipeline` (publisher report): rows where `publisher_id` is present
- `catscan-pipeline-geo` (geo report): rows where `publisher_id` is null/blank
- Count rows by `metric_date` and class

3. `rtb_daily` -> split into:
- `catscan-quality` (rows with `billing_id` / reached queries / Active View-style metrics)
- `catscan-bidsinauction` (rows with `bids_in_auction` / `auctions_won`)
- Count rows by `metric_date` and class

Important:
- Inspect actual column names first (schema can vary).
- Use explicit classification logic based on columns present/non-null, not assumptions.
- If `rtb_daily` rows can match both classifications, define precedence and document it.

Deliverable for Phase 1:
- A table (markdown or CSV in the doc) covering all days and all 5 report types with statuses:
  - `present-imported`
  - `present-zero-rows` (if legitimate)
  - `tracking-only`
  - `raw-only` (should be rare; indicates tracking gap)
  - `missing`

PHASE 2 — Gmail evidence for missing/ambiguous cells (read-only if possible)
Goal: For any matrix cell that is `missing` or ambiguous, prove whether Gmail actually had the expected report.

You must inspect message/attachment-level evidence for TUKY in the window.

1) Inspect Gmail batch/checkpoint/status state
- `gmail_import_batch.py --status`
- dump `/home/catscan/.catscan/gmail_import_status.json`
- dump `/home/catscan/.catscan/gmail_batch_checkpoint.json`
- tail `/home/catscan/.catscan/logs/gmail_import_worker.log`

2) Enumerate relevant Gmail report messages/attachments for TUKY (2026-02-11..2026-02-25)
- Prefer a read-only listing path using existing scripts/CLI if available.
- If no listing mode exists, use a targeted Gmail API read-only query using existing creds/token on the VM.
- Capture per message:
  - Gmail message ID
  - date/time
  - subject
  - attachment filenames
  - inferred report type(s)
  - whether checkpoint marks it processed

3) Build a Gmail-side daily matrix for TUKY
- Rows = report day
- Cols = 5 expected reports
- Values = `seen attachment`, `not seen`, `unclear`

4) Reconcile Gmail matrix against Phase 1 DB matrix
Classify each missing/ambiguous case into one of:
- Gmail absent (report was not received)
- Gmail present but skipped intentionally (allowlist/filter)
- Gmail present but importer parse/classification failure
- Gmail present and imported, but tracking mismatch (should now be rare post-backfill)
- Imported with zero rows (legitimate empty report)
- Imported to wrong seat/account (serious bug; prove it)

PHASE 3 — End-to-end integrity spot checks (raw -> precompute -> Home)
Goal: confirm the TUKY UI numbers are plausible reflections of raw data for the same window.

1) Home seat daily reconciliation (TUKY)
- Query `home_seat_daily` for `2026-02-18..2026-02-24`
- Compare with raw-table-derived aggregates for:
  - `reached_queries`
  - `impressions`
- If there is a significant mismatch, quantify it and localize the break (raw vs precompute)

2) Endpoint observed QPS sanity (TUKY)
- Query `rtb_endpoints_current` + `rtb_endpoints`
- Show:
  - endpoint current_qps values
  - sum(current_qps)
- Compare with `AVG(home_seat_daily.reached_queries) / 86400`
- Confirm this path is behaving as expected (or identify divergence)

3) BQ involvement (important)
- Determine whether the current Gmail import -> serving data path for these 5 reports uses BigQuery in this deployment/workflow.
- If yes, trace one report type through BQ staging/intermediate tables with evidence.
- If no, state explicitly that the relevant path is Postgres-direct and BQ is not in-path for this issue.

PHASE 4 — Root cause analysis and fixes
Based on the matrix and evidence, identify the actual root causes for TUKY not showing all 5 expected daily reports.

Separate these categories clearly:
1. Source completeness issue (Gmail reports not received)
2. Importer logic issue (parse/skip/failure)
3. Tracking/observability issue (UI/import tracking mismatch)
4. Precompute/UI representation issue (unit/labeling, aggregation view)
5. Product expectation mismatch (e.g., some reports may not be guaranteed daily for all seats; prove/disprove)

Then provide a ranked fix plan:
- Highest impact, lowest risk first
- Exact files/functions to patch
- Whether backfill/repair is needed after code change
- Whether monitoring/alerts should be added

If you find a small, obviously correct bug fix while auditing (e.g. one-line classification/guard fix), you may patch it, but:
- keep code changes separate from the RCA doc commit
- explain why it is safe

Required output format (strict)
Return a structured summary with these sections:

1. **Findings (Evidence-backed)**
- Severity-ordered bullets
- Include file/line refs for code issues
- Include key prod query results

2. **TUKY Daily 5-Report Completeness Matrix**
- One row per day (`2026-02-11..2026-02-25`)
- One column per expected report type
- Status + short note per cell

3. **Gmail vs DB Reconciliation**
- Missing/ambiguous cases and exact classification

4. **Raw -> Precompute -> Home Reconciliation**
- Numeric checks and conclusion on corruption vs completeness vs unit mismatch

5. **Root Causes**
- Separate tracking bug(s) from ingestion completeness gaps

6. **Fix Plan (Ranked)**
- Exact files/functions
- Data repair steps (if any)

7. **Residual Risks / Open Questions**

Documentation (required)
- Create a review note:
  - `docs/review/2026-02-25/audit/TUKY_DAILY_5_REPORT_COMPLETENESS_AUDIT.md`
- Include:
  - commands run
  - query summaries
  - matrix
  - conclusions
  - proposed fixes

Do not mark any roadmap item complete in this pass unless the matrix and Gmail reconciliation prove it.
```

