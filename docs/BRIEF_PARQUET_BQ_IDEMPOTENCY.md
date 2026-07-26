# Engineering brief — make the parquet→BigQuery spend lane idempotent

**Status:** option A implemented locally 2026-07-22 (not deployed); durable option C remains open
**Owner:** unassigned — this brief is the starting point for whoever picks it up
**Background reading:** `investigations/RCA-mobyoung-daily-spend-2026-07-13.md`,
`investigations/RCA-mobyoung-0705-multiplied-2026-07-21.md`

## Why now

Re-ingesting any spend CSV **appends** a new batch to BigQuery `rtb_daily` and
the inline publisher immediately republishes the day as the SUM of all
batches. Three double-count incidents in two weeks, all this mechanism:

| Metric date | What happened | Published effect |
|---|---|---|
| 2026-07-01 | Out-of-band replay of a spend CSV (batch `583a4d26`) | day 2× |
| 2026-07-12 | Mis-scoped `12JULY` AB re-run auto-ingested (batch `adc8623e`) | day 2× for ~1h |
| 2026-07-05 | Recurring `5JULY` AB re-run schedule delivered daily Jul 15–21 (7 batches) | day **7×**, +$99,433 served to a billing consumer for days |

Each cleanup is manual (backup batch → BQ DELETE → re-materialize) and the
07-05 case shipped a ~30% month-to-date over-report into a client's
billing/balance automation. The watchdog alerts (journal-only) and its
duplicate sweep goes blind once the metric date is >14 days old — exactly
when the 07-05 case needed it.

## Current mechanics (verified 2026-07-21, with code refs)

Email → `scripts/gmail_import.py` classifies + imports:

1. **Postgres import lane — already idempotent at row level.** A re-delivered
   identical file records `rows_imported=0, rows_duplicate=N` in
   `import_history` (observed for all six 07-05 re-deliveries). But it is
   recorded as `status=success`.
2. **The active raw-export lane is embedded in that same import.**
   `unified_import()` creates a `ParquetExportManager`
   (`importers/unified_importer.py:1480`), buffers every parsed CSV row before
   knowing how many PG inserts conflict, then unconditionally calls
   `finalize()` (~line 1549). Finalization uploads the parquet and loads it
   with `WriteDisposition.WRITE_APPEND`
   (`importers/parquet_pipeline.py:472`). No key, merge, or dedup exists, so
   every run appends a full new `import_batch_id` for the same
   `(report_type, buyer_account_id, metric_date)`. Production has
   `CATSCAN_GCS_BUCKET` and `CATSCAN_BQ_DATASET` set, so this exporter is
   implicitly enabled even though `CATSCAN_RAW_EXPORT_ENABLED` is unset.
   The separate `run_pipeline_for_file()` path is disabled in production
   (`CATSCAN_PIPELINE_ENABLED=false`) and was not the source of these batches.
3. **Inline publisher** `publish_buyer_spend_range`
   (`scripts/gmail_import.py:975`, invoked ~line 1888) →
   `refresh_rtb_summaries` (`services/rtb_precompute.py`, the only reader of
   `report_type='buyer_spend'`, ~line 241) recomputes the serving table
   `rtb_buyer_spend_daily` as `SUM(spend_micros)` over **all** batches for
   the day. The PG side of that refresh is DELETE+INSERT (idempotent); the
   corruption is purely that the BQ input contains N copies.

So: the import has a reliable PG duplicate signal (step 1), but its parallel
raw exporter ignores that signal and feeds an append-only sink (step 2) whose
reader assumes single-batch days (step 3).

## Requirement

A re-delivered or backfilled report for a day must **replace** that day's
rows, not add to them (this is also the documented expectation of the Agent
API consumer). Recovery/backfill workflows (`investigations/
ingest_0705_recovered.sh`-style) must become safe to run twice.

## Solution options (recommendation: A now, then C)

**A. Entry guard — discard raw export on 100%-duplicate imports (small, ship first).**
When the PG import result has `rows_read > 0 and rows_imported == 0` (file is
entirely known rows), close/delete the buffered parquet instead of uploading
or loading it, then skip the inline publish and log/alert instead. This alone
would have prevented six of the seven 07-05 batches. It does not protect a
manual `run_pipeline.py` invocation that bypasses PG (the 07-01 replay class).
Limitation: does not catch *restated* files (same day, different numbers) or
partial overlaps — those still append.

**B. Replace-by-scope load — delete-before-load.**
Before the BQ load, `DELETE FROM rtb_daily WHERE report_type = X AND
buyer_account_id = Y AND metric_date IN (dates present in the file)`, then
append. True last-write-wins upsert semantics. Care needed: multi-day files,
concurrent loads for the same seat, DML quota, and the loss of the previous
batch as an in-table audit trail (export it first, or rely on backups).
Note last-write-wins is *usually* right but degraded the 07-05 case slightly
(later re-run exports carry 2 dp display-format drift); acceptable.

**C. Batch-aware readers — append stays, readers pick one winning batch.**
Keep `WRITE_APPEND` as an audit log; make `refresh_rtb_summaries` (and the
watchdog's notion of "duplicate") aggregate only the winning
`import_batch_id` per `(buyer_account_id, metric_date)` — e.g. latest by
`import_history.imported_at` (batch ids carry no ordering; either join PG
`import_history` or add an `ingested_at` column to the BQ schema).
Self-heals any historical contamination automatically and keeps every
delivered batch inspectable. Slightly more query complexity in the one
reader that matters.

A is an afternoon of work and removes the recurring-schedule failure mode
immediately; C is the durable end state. B is acceptable if C's
batch-ordering plumbing is deemed too invasive, but C is preferred because it
also retro-protects history and preserves audit data.

## Option A implementation (local branch, 2026-07-22)

`unified_import()` now consumes the PG result before publication. When
`rows_read > 0`, `rows_imported == 0`, and `rows_duplicate == rows_read`, it
calls `ParquetExportManager.discard()` instead of `finalize()`. Discard closes
writers and removes local buffered parquet without any GCS upload or BQ load.
The strict equality avoids misclassifying empty or wholly-invalid files as
safe replays.

`scripts/gmail_import.py` also routes the returned result through
`run_pipeline_after_import`; the same condition returns `SKIPPED_DUPLICATE`,
does not call any separately enabled pipeline, and does not run the inline
buyer-spend publisher. The skip is emitted even in quiet mode and is included
in the returned/status-JSON payload as `duplicate_downstream_skips`.

Both Gmail entry points (`gmail_import.py` and `gmail_import_batch.py`) use the
guard. The local, gitignored `investigations/ingest_0705_recovered.sh` recovery
runner was also changed to use it, so an exact second run is a successful
no-op. The detached Gmail worker also suppresses its broad post-import refresh
when every imported file was skipped as an exact duplicate. Focused tests
simulate the 557,102-row 07-05 replay and prove that neither the BQ loader nor
publisher is called; partial overlap still proceeds to the pipeline. Option A
deliberately does not provide replace semantics for restated or partially
overlapping files; option B or C is still required for those cases.

## Prerequisite / trap: script drift

The on-VM state dir (`/home/catscan/.catscan/`, mounted in the container as
`/home/rtbcat/.catscan/`) holds drifted copies of
`export_csv_to_parquet.py`, `load_parquet_to_bigquery.py`,
`bq_aggregate_to_pg.py` (handover 2026-07-14). The in-container Gmail-import
path imports repo code from `/app` (so an image deploy fixes it), but before
relying on that, **verify which copy each entry point actually executes**
(container imports vs any VM cron invoking the state-dir copies) and
reconcile the state-dir scripts into git. Fixing only the repo while a
drifted copy still runs would look done and not be.

Read-only production verification on 2026-07-22 established that the active
Cloud Scheduler job calls the API, whose worker imports
`/app/scripts/gmail_import.py` from image `sha-30f2477`. The active container's
three pipeline-script checksums match the `/home/jen/catscan-work/scripts/`
checkout. Root, `catscan`, and VM-user crontabs were empty; systemd had no
references to the three state-dir pipeline copies. Those copies are older
January implementations and currently unused (the delivery watchdog has a
separate state-dir fallback). Therefore an image deploy changes the active
ingestion path; the old copies should be removed or explicitly retired in a
separate housekeeping change, not merged back into the newer repo code.

The same inspection also corrected the original handoff assumption about the
active append path: `CATSCAN_PIPELINE_ENABLED=false`, while the embedded raw
exporter is active because its GCS bucket and BQ dataset are configured. The
Option A guard therefore exists inside `unified_import()` as well as at its
Gmail caller; a caller-only guard would be too late.

## Acceptance criteria

1. Ingest the same spend CSV twice (scratch BQ dataset or a test seat):
   published day value unchanged after the second run; either no second
   batch exists (A/B) or the reader provably ignores it (C).
2. A restated file for an existing day replaces the day (B/C; A: documented
   as out of scope with the alert firing instead).
3. `scripts/check_report_delivery.py` duplicate sweep is green afterwards,
   and its definition of "duplicate" matches the chosen semantics (under C,
   >1 batch is normal — the sweep must instead compare published vs winning
   batch).
4. Unit/integration tests cover: exact re-delivery, restated day, multi-day
   file, and the recovery-script path run twice.
5. Deployed via the normal merge→main→CI→manual deploy flow (no VM edits).

## Adjacent open hardening (separate, don't scope-creep into this)

- Watchdog alerts are journal/status-JSON only and the permanent seat
  299038253 alert masks new ones; duplicates age out of the 14-day sweep.
  Latching + a human alert channel is tracked separately (see 07-21 RCA
  remediation list).
- BQ backup tables awaiting client reconciliation before drop:
  `rtb_daily_dupbatch_583a4d26_bak_20260713`,
  `rtb_daily_dupbatch_adc8623e_bak_20260714`,
  `rtb_daily_dupbatch_0705x6_bak_20260721`.
