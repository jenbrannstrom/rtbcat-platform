"""Ingestion observability tests (C-ING-001 / C-ING-002).

Environment-independent: uses in-memory stubs for UploadsRepository and
sync psycopg so no database connection is required.
"""

import uuid
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

from storage.postgres_repositories.uploads_repo import UploadsRepository
from services.performance_service import PerformanceService


# ---------------------------------------------------------------------------
# Stub UploadsRepository that records calls in memory
# ---------------------------------------------------------------------------

class StubUploadsRepo(UploadsRepository):
    """In-memory stub that captures all calls for assertion."""

    def __init__(self):
        self.ingestion_runs: dict[str, dict] = {}
        self.import_history: list[dict] = []
        self._current_date = "2026-02-11"

    async def start_ingestion_run(
        self, run_id, source_type, buyer_id=None, bidder_id=None,
        report_type=None, filename=None,
    ):
        self.ingestion_runs[run_id] = {
            "run_id": run_id,
            "source_type": source_type,
            "buyer_id": buyer_id,
            "bidder_id": bidder_id,
            "status": "running",
            "report_type": report_type,
            "filename": filename,
            "row_count": 0,
            "error_summary": None,
            "finished_at": None,
        }

    async def finish_ingestion_run(
        self, run_id, status, row_count=0, error_summary=None,
    ):
        run = self.ingestion_runs.get(run_id)
        if run and run["finished_at"] is None:
            run["status"] = status
            run["row_count"] = row_count
            run["error_summary"] = error_summary
            run["finished_at"] = "2026-02-11T00:00:00+00:00"

    async def record_import_history(self, **kwargs):
        self.import_history.append(kwargs)

    async def get_current_date(self):
        return self._current_date

    async def update_daily_upload_summary(self, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Test 1: Success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_success_path_sets_row_count():
    repo = StubUploadsRepo()
    run_id = str(uuid.uuid4())

    await repo.start_ingestion_run(run_id=run_id, source_type="csv", buyer_id="123456")
    assert repo.ingestion_runs[run_id]["status"] == "running"

    await repo.finish_ingestion_run(run_id=run_id, status="success", row_count=500)

    run = repo.ingestion_runs[run_id]
    assert run["status"] == "success"
    assert run["row_count"] == 500
    assert run["finished_at"] is not None


# ---------------------------------------------------------------------------
# Test 2: Failure path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failure_path_sets_error_and_finished_at():
    repo = StubUploadsRepo()
    run_id = str(uuid.uuid4())

    await repo.start_ingestion_run(run_id=run_id, source_type="csv")
    await repo.finish_ingestion_run(
        run_id=run_id, status="failed", row_count=0, error_summary="bad CSV header",
    )

    run = repo.ingestion_runs[run_id]
    assert run["status"] == "failed"
    assert run["error_summary"] == "bad CSV header"
    assert run["finished_at"] is not None


# ---------------------------------------------------------------------------
# Test 3: import_history buyer_id populated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_import_history_buyer_id_populated():
    repo = StubUploadsRepo()
    svc = PerformanceService(uploads_repo=repo)

    await svc.record_import(
        batch_id="batch-001",
        filename="catscan-pipeline-123456-yesterday-UTC.csv",
        rows_read=100,
        rows_imported=95,
        rows_skipped=5,
        rows_duplicate=0,
        date_range_start="2026-02-10",
        date_range_end="2026-02-10",
        columns_found=["Day", "Impressions"],
        status="complete",
        error_message=None,
        file_size_bytes=1024,
        buyer_id="123456",
        bidder_id="123456",
    )

    assert len(repo.import_history) == 1
    record = repo.import_history[0]
    assert record["buyer_id"] == "123456"
    assert record["bidder_id"] == "123456"
    assert record["batch_id"] == "batch-001"


# ---------------------------------------------------------------------------
# Test 4: Multi-file / multi-buyer coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_file_multi_buyer():
    repo = StubUploadsRepo()
    svc = PerformanceService(uploads_repo=repo)

    buyers = [
        ("buyer-A", "batch-a", "report-a.csv"),
        ("buyer-B", "batch-b", "report-b.csv"),
        ("buyer-C", "batch-c", "report-c.csv"),
    ]

    for buyer_id, batch_id, filename in buyers:
        run_id = str(uuid.uuid4())
        await repo.start_ingestion_run(
            run_id=run_id, source_type="csv", buyer_id=buyer_id, filename=filename,
        )
        await repo.finish_ingestion_run(run_id=run_id, status="success", row_count=10)

        await svc.record_import(
            batch_id=batch_id,
            filename=filename,
            rows_read=10,
            rows_imported=10,
            rows_skipped=0,
            rows_duplicate=0,
            date_range_start="2026-02-10",
            date_range_end="2026-02-10",
            columns_found=[],
            status="complete",
            error_message=None,
            file_size_bytes=512,
            buyer_id=buyer_id,
        )

    assert len(repo.ingestion_runs) == 3
    assert all(r["status"] == "success" for r in repo.ingestion_runs.values())
    assert len(repo.import_history) == 3
    recorded_buyers = {r["buyer_id"] for r in repo.import_history}
    assert recorded_buyers == {"buyer-A", "buyer-B", "buyer-C"}


# ---------------------------------------------------------------------------
# Test 5: No duplicate finalization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_duplicate_finalization():
    repo = StubUploadsRepo()
    run_id = str(uuid.uuid4())

    await repo.start_ingestion_run(run_id=run_id, source_type="csv")
    await repo.finish_ingestion_run(run_id=run_id, status="success", row_count=100)

    # Second finish should be a no-op (finished_at already set)
    await repo.finish_ingestion_run(
        run_id=run_id, status="failed", row_count=0, error_summary="should not apply",
    )

    run = repo.ingestion_runs[run_id]
    assert run["status"] == "success"
    assert run["row_count"] == 100
    assert run["error_summary"] is None


# ---------------------------------------------------------------------------
# Test 6: Gmail record_import_run mock test
# ---------------------------------------------------------------------------

def test_gmail_record_import_run_writes_both_tables():
    """Verify record_import_run INSERTs ingestion_runs and import_history
    with correct buyer_id/bidder_id via sync psycopg."""
    import sys

    # Provide stubs for google.* packages that gmail_import imports at module level.
    for mod_name in [
        "google", "google.auth", "google.auth.transport",
        "google.auth.transport.requests", "google.oauth2",
        "google.oauth2.credentials", "google_auth_oauthlib",
        "google_auth_oauthlib.flow", "googleapiclient",
        "googleapiclient.discovery", "google.cloud",
        "google.cloud.storage",
    ]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()

    from scripts.gmail_import import record_import_run

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    with patch("scripts.gmail_import._get_sync_connection", return_value=mock_conn):
        record_import_run(
            seat_id="654321",
            report_kind="catscan-pipeline",
            filename="catscan-pipeline-654321-yesterday-UTC.csv",
            success=True,
            rows_imported=200,
            rows_duplicate=5,
            rows_read=210,
            file_size_bytes=2048,
            batch_id="gmail-batch-001",
            date_range_start="2026-02-10",
            date_range_end="2026-02-10",
            columns_found="Day,Impressions,Clicks",
        )

    # Should have exactly 3 execute calls: INSERT running, UPDATE success, INSERT import_history
    assert mock_conn.execute.call_count == 3

    # First call: INSERT ingestion_runs with status='running'
    first_sql = mock_conn.execute.call_args_list[0][0][0]
    first_params = mock_conn.execute.call_args_list[0][0][1]
    assert "INSERT INTO ingestion_runs" in first_sql
    assert "'running'" in first_sql
    # buyer_id and bidder_id should be seat_id
    assert first_params[1] == "654321"  # buyer_id
    assert first_params[2] == "654321"  # bidder_id

    # Second call: UPDATE to final status
    second_sql = mock_conn.execute.call_args_list[1][0][0]
    second_params = mock_conn.execute.call_args_list[1][0][1]
    assert "UPDATE ingestion_runs" in second_sql
    assert second_params[0] == "success"
    assert second_params[1] == 200  # row_count

    # Third call: INSERT import_history
    third_sql = mock_conn.execute.call_args_list[2][0][0]
    third_params = mock_conn.execute.call_args_list[2][0][1]
    assert "INSERT INTO import_history" in third_sql
    assert third_params[0] == "gmail-batch-001"  # batch_id
    # buyer_id and bidder_id at end of params
    assert "654321" in third_params  # buyer_id present
