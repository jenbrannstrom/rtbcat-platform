# Phase 1: Ingestion Observability Implementation

**Date:** 2026-02-11
**Branch:** unified-platform
**Contracts:** C-ING-001, C-ING-002

## Summary

Instrumented all import paths so `ingestion_runs` and `import_history` tables are reliably populated with buyer attribution.

## Changes Made

### 1. Migration `039_ingestion_runs_extend.sql`
- Added `report_type TEXT`, `filename TEXT`, `bidder_id TEXT` to `ingestion_runs`
- Added `buyer_id TEXT`, `bidder_id TEXT` to `import_history`
- All idempotent (`ADD COLUMN IF NOT EXISTS`)

### 2. `storage/postgres_repositories/uploads_repo.py`
- `record_import_history()`: added `buyer_id` and `bidder_id` params (default None), included in INSERT
- `start_ingestion_run()`: new method — INSERT with status='running'
- `finish_ingestion_run()`: new method — UPDATE with `WHERE finished_at IS NULL` guard (no double-write)

### 3. `services/performance_service.py`
- `record_import()`: added `buyer_id`/`bidder_id` params, forwarded to `uploads_repo.record_import_history()`
- `finalize_import()`: added `buyer_id`/`bidder_id` params, forwarded to `uploads_repo.record_import_history()`

### 4. `scripts/gmail_import.py`
- `record_import_run()`: replaced no-op with real sync psycopg writes — single transaction: INSERT ingestion_runs (running), UPDATE to final status, INSERT import_history. `buyer_id = seat_id` (explicit).
- `import_to_catscan()`: returns `CatscanImportResult` dataclass with full metadata (report_type, date_range, columns, file_size, rows_read, batch_id)
- Call site updated to use `CatscanImportResult` fields

### 5. `api/routers/performance.py`
- `import_performance_csv`: wraps import in `start_ingestion_run` / `finish_ingestion_run`
- Extracts `buyer_id` via `parse_bidder_id_from_filename`; stores `buyer_id_unresolved_from_upload` in `error_summary` when unresolvable
- Failure path records ingestion_run as failed with error_summary
- Passes `buyer_id`/`bidder_id` to `perf_service.record_import()`

### 6. `tests/test_ingestion_observability.py`
6 environment-independent tests, all passing:
1. Success path (start + finish success, row_count set)
2. Failure path (finish failed, error_summary set, finished_at always set)
3. import_history buyer_id populated
4. Multi-file/multi-buyer fixture coverage
5. No duplicate finalization (second finish is no-op)
6. Gmail record_import_run mock test (both INSERTs with correct buyer_id/bidder_id)

## Test Output

```
tests/test_ingestion_observability.py::test_success_path_sets_row_count PASSED
tests/test_ingestion_observability.py::test_failure_path_sets_error_and_finished_at PASSED
tests/test_ingestion_observability.py::test_import_history_buyer_id_populated PASSED
tests/test_ingestion_observability.py::test_multi_file_multi_buyer PASSED
tests/test_ingestion_observability.py::test_no_duplicate_finalization PASSED
tests/test_ingestion_observability.py::test_gmail_record_import_run_writes_both_tables PASSED
6 passed in 0.39s
```

## Post-Deploy Verification SQL

```sql
-- Ingestion runs by buyer/report_type/status
SELECT buyer_id, report_type, status, COUNT(*)
FROM ingestion_runs
GROUP BY buyer_id, report_type, status
ORDER BY buyer_id, report_type;

-- Import history by buyer_id
SELECT buyer_id, COUNT(*) as imports, SUM(rows_imported) as total_rows
FROM import_history
WHERE buyer_id IS NOT NULL
GROUP BY buyer_id
ORDER BY buyer_id;
```

## Status Model

- **CSV upload path (async):** `start_ingestion_run(running)` -> import -> `finish_ingestion_run(success|failed)`
- **Gmail path (sync):** single transaction INSERT running + UPDATE to final status (import completes before recording, intentional)
- **Guard:** `WHERE finished_at IS NULL` prevents duplicate finalization
