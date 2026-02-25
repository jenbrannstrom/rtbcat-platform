# Codex Local Findings: TUKY Import Pipeline Audit (Code-Path Side)

Status: preliminary local code audit (awaiting Claude's prod evidence for final RCA)

## Executive Summary

The local code strongly suggests the TUKY issue is **not primary numeric corruption**, but a combination of:

1. **Import tracking/report-type misclassification** for Gmail GCS-downloaded reports (`unknown` report_type risk)
2. **Message-level checkpoint/read semantics that can hide partial failures**
3. **Batch importer correctness bug** (`CatscanImportResult` object unpacked as tuple)
4. **Unit mismatch / UX confusion** on Home "Observed QPS" (QPS vs daily reached queries)

There are also additional end-to-end correctness risks where pipeline/precompute failures can be ignored while the email is still marked processed.

## Findings (Local Code Evidence)

### 1. High: Gmail GCS downloads are renamed to generic filenames, which likely breaks import tracking report-type classification

- `scripts/gmail_import.py:821` starts GCS download path (`download_from_url`)
- `scripts/gmail_import.py:840`-`scripts/gmail_import.py:846` assigns a generic local filename:
  - `catscan-report-<seat_id>-<timestamp>.csv` (or `report_<timestamp>_<message>.csv`)
- `scripts/gmail_import.py:290`-`scripts/gmail_import.py:303` `detect_report_kind()` infers canonical report kind from filename substrings like `catscan-bidsinauction`, `catscan-pipeline-geo`, etc.
- `scripts/gmail_import.py:1318`-`scripts/gmail_import.py:1323` (non-batch path) uses `detect_report_kind(filepath.name)` for `record_import_run(...)`
- `scripts/gmail_import_batch.py:191`-`scripts/gmail_import_batch.py:197` (batch path) does the same

Impact:
- If a report is successfully imported via GCS download, it may still be recorded as `report_type='unknown'` in `ingestion_runs`, causing the Import UI matrix to underreport imported CSV types.
- This can make the UI show "2 of 5" even when more report types were ingested.

Why this matches the user symptom:
- The Import page can represent all 5 expected CSV types (`services/uploads_service.py:95`-`services/uploads_service.py:101`).
- The screenshot showing only `quality` + `pipeline-geo` may reflect classification loss, not necessarily missing ingestion.
- The import matrix query canonicalizes only known `report_type` values and maps everything else to `NULL`:
  - `storage/postgres_repositories/uploads_repo.py:13`-`storage/postgres_repositories/uploads_repo.py:22`
- Then it explicitly filters out unknowns (`csv_type IS NOT NULL`):
  - `storage/postgres_repositories/uploads_repo.py:214`-`storage/postgres_repositories/uploads_repo.py:216`

### 2. High: Batch importer unpacks `CatscanImportResult` as a tuple (known bug), which can import data but break tracking/pipeline flow

- `scripts/gmail_import.py:962`-`scripts/gmail_import.py:1007` defines `CatscanImportResult` and returns that object from `import_to_catscan()`
- `scripts/gmail_import_batch.py:191` incorrectly unpacks:
  - `success, report_type, rows_imported, rows_dup, error = import_to_catscan(filepath)`

Impact:
- `import_to_catscan()` may successfully import rows before returning the result object
- Then tuple-unpack raises an exception, causing:
  - `record_import_run(...)` not to execute
  - pipeline step not to run
  - message to be handled by exception path instead of normal success path
- This matches the previously observed "imports succeed, counters/tracking broken" behavior

### 3. High: Message-level checkpoint + mark-as-read can hide partial file failures within a single email

Batch importer (`scripts/gmail_import_batch.py`):
- Iterates files in a message: `scripts/gmail_import_batch.py:185`-`scripts/gmail_import_batch.py:212`
- Regardless of per-file failures, it marks the whole message read and processed after the loop:
  - `scripts/gmail_import_batch.py:213`-`scripts/gmail_import_batch.py:215`

Impact:
- If an email contains multiple CSVs and at least one file import fails while another succeeds:
  - the message can still be marked read and checkpointed
  - failed files are not retried via Gmail because the message is considered done

This is a real end-to-end correctness risk (silent partial ingestion).

### 4. High: Pipeline result is ignored after successful import (raw import can succeed while downstream data remains stale)

Batch path:
- `scripts/gmail_import_batch.py:204`-`scripts/gmail_import_batch.py:209`
- Calls `run_pipeline_for_file(filepath, seat_id, verbose=False)` and ignores the boolean return value

Non-batch path:
- `scripts/gmail_import.py:1335`-`scripts/gmail_import.py:1339`
- Same pattern: pipeline return value ignored
- Then message is marked read anyway: `scripts/gmail_import.py:1340`

Impact:
- CSV may import into Postgres raw tables, but pipeline (Parquet -> BQ -> aggregate to PG UI tables) can fail silently relative to email processing
- Email is still marked read, reducing natural retry visibility
- Home/precompute data can lag behind import success

### 5. Medium: Failed message IDs are treated as already processed in batch checkpointing (no automatic retry)

- `scripts/gmail_import_batch.py:88`-`scripts/gmail_import_batch.py:90`
- `get_processed_ids()` returns the union of `processed_ids` and `failed_ids`

Impact:
- Any message that enters the exception path is excluded from future runs unless `--reset` is used
- This can strand recoverable failures indefinitely (especially transient errors)

### 6. Medium: Home endpoint "Observed" values are QPS, not daily reached queries (likely unit mismatch, not corruption)

- `storage/postgres_repositories/endpoints_repo.py:95`-`storage/postgres_repositories/endpoints_repo.py:100` documents observed QPS derivation
- Formula in SQL:
  - `SUM(hsd.reached_queries) / COUNT(DISTINCT hsd.metric_date) / 86400` at `storage/postgres_repositories/endpoints_repo.py:131`-`storage/postgres_repositories/endpoints_repo.py:134`
- Endpoint values are then allocated proportionally by `maximum_qps` at `storage/postgres_repositories/endpoints_repo.py:116`-`storage/postgres_repositories/endpoints_repo.py:119`

Impact:
- Home endpoint values like `4.5`, `13.6`, `22.7` are expected to be **QPS**, not millions/day
- A direct comparison to "Reached queries/day" from the CSV is a unit mismatch unless converted

### 7. Medium: Home seat daily precompute depends on `rtb_bidstream_publisher` only

- `scripts/bq_aggregate_to_pg.py:112`-`scripts/bq_aggregate_to_pg.py:126`
- `home_seat_daily` aggregates from BigQuery `rtb_bidstream` where `report_type = 'rtb_bidstream_publisher'`

Impact:
- If `pipeline-publisher` ingestion/pipeline is missing, Home seat-level traffic metrics can be stale or incomplete even if other report types (`quality`, `pipeline-geo`) are present
- This makes accurate import tracking for `pipeline-publisher` especially important

### 8. Medium: Pipeline date parsing helper does not support 2-digit years in several code paths

- `scripts/gmail_import.py:109` only tries `%Y-%m-%d`, `%d/%m/%Y`, `%m/%d/%Y`
- `scripts/run_pipeline.py:220` same pattern in `detect_metric_date_from_csv()`

Impact:
- CSV dates like `2/18/26` (2-digit year) may fail date parsing
- In `run_pipeline_for_file`, failure falls back to `today()` (`scripts/gmail_import.py:118`-`scripts/gmail_import.py:120`)
- Depending on the actual Gmail report date format and downstream parsing, this may mis-target aggregation date or create freshness confusion

Note:
- This is a plausible correctness risk, but needs prod evidence to confirm actual scheduled-report CSV date format.

## Likely Explanation for the TUKY Symptoms (Pending Prod Proof)

1. **Home observed QPS mismatch**
- Likely a unit mismatch (QPS values compared against daily reached queries)
- Not primary numeric corruption

2. **Import UI showing only 2 of 5 CSVs**
- Likely import tracking/report-type misclassification (`unknown`) for GCS-downloaded files
- Potentially compounded by batch importer result-unpack bug preventing tracking updates

3. **Unread stragglers**
- Could be checkpointed/failed message behavior, not necessarily unimported data
- Batch checkpoint semantics and exception handling make this plausible

## Candidate Fixes (Ranked, not applied yet)

1. **Fix batch importer `CatscanImportResult` handling**
- File: `scripts/gmail_import_batch.py`
- Use object attributes (`imp = import_to_catscan(filepath)`) instead of tuple unpack

2. **Record report type from parsed import result (or original report source), not local temp filename**
- Files: `scripts/gmail_import.py`, `scripts/gmail_import_batch.py`
- Prefer `CatscanImportResult.report_type` (normalized from `unified_import`)
- Preserve original report filename / report kind from email subject or GCS object path for observability

3. **Do not mark message processed/read when any file in the message fails**
- Files: `scripts/gmail_import.py`, `scripts/gmail_import_batch.py`
- Track per-message success and only mark read/checkpoint on full success

4. **Treat pipeline failure as a first-class failure state (or at least record it explicitly)**
- Files: `scripts/gmail_import.py`, `scripts/gmail_import_batch.py`
- Today pipeline boolean return is ignored

5. **Retry policy for failed message IDs**
- File: `scripts/gmail_import_batch.py`
- Do not merge `failed_ids` into `processed_ids` forever, or add retry/backoff categories

6. **Add 2-digit year parsing support**
- Files: `scripts/gmail_import.py`, `scripts/run_pipeline.py`
- Add `%m/%d/%y` and `%d/%m/%y`

## What Claude's Prod Evidence Should Confirm / Deny

1. Whether TUKY `home_seat_daily` matches CSV reached/impression scale in the 7-day window
2. Whether `rtb_endpoints_current` sums align with `avg(reached_queries)/86400`
3. Whether TUKY `ingestion_runs` contains many `report_type='unknown'`
4. Whether `import_history` has generic `catscan-report-299038253-...` filenames
5. Whether unread Feb 11–14 messages are true missed imports vs checkpointed/failed/misclassified cases
