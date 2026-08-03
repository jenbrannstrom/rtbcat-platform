"""Tests for the durable precompute job queue."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import pytest

from scripts import gmail_import
from services import precompute_queue


class FakeCursor:
    def __init__(self, row: Optional[dict]) -> None:
        self._row = row

    def fetchone(self) -> Optional[dict]:
        return self._row


class FakeConn:
    """Scripted connection: returns queued rows per executed statement."""

    def __init__(self, rows: list[Optional[dict]]) -> None:
        self._rows = list(rows)
        self.statements: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()) -> FakeCursor:
        self.statements.append((sql, params))
        return FakeCursor(self._rows.pop(0) if self._rows else None)


def _run_in_fake_transaction(conn: FakeConn):
    async def _fake_transaction(func):
        return func(conn)

    return _fake_transaction


def test_enqueue_inserts_new_job(monkeypatch) -> None:
    conn = FakeConn([{"id": 7, "status": "queued"}])
    monkeypatch.setattr(
        precompute_queue, "pg_transaction_async", _run_in_fake_transaction(conn)
    )

    result = asyncio.run(
        precompute_queue.enqueue_precompute_job(
            source="scheduler",
            start_date="2026-08-01",
            end_date="2026-08-02",
            dedupe_key="precompute-refresh:2026-08-02T22:30:00Z",
        )
    )

    assert result == {"job_id": 7, "status": "queued", "deduplicated": False}
    assert "INSERT INTO precompute_jobs" in conn.statements[0][0]


def test_enqueue_returns_active_job_for_same_dedupe_key(monkeypatch) -> None:
    # INSERT hits the partial unique index (returns no row); the active job
    # for the same scheduled execution is returned instead.
    conn = FakeConn([None, {"id": 3, "status": "running"}])
    monkeypatch.setattr(
        precompute_queue, "pg_transaction_async", _run_in_fake_transaction(conn)
    )

    result = asyncio.run(
        precompute_queue.enqueue_precompute_job(
            source="scheduler",
            start_date="2026-08-01",
            end_date="2026-08-02",
            dedupe_key="precompute-refresh:2026-08-02T22:30:00Z",
        )
    )

    assert result == {"job_id": 3, "status": "running", "deduplicated": True}


def test_worker_defers_to_active_gmail_import(monkeypatch) -> None:
    monkeypatch.setattr(gmail_import, "get_status", lambda: {"running": True})

    async def _must_not_claim(_func):
        raise AssertionError("claim attempted while Gmail import is running")

    monkeypatch.setattr(precompute_queue, "pg_transaction_async", _must_not_claim)

    assert asyncio.run(precompute_queue.process_queue_once()) is False


def test_worker_executes_claimed_job(monkeypatch) -> None:
    monkeypatch.setattr(gmail_import, "get_status", lambda: {"running": False})

    job = {
        "id": 11,
        "source": "scheduler",
        "start_date": "2026-08-01",
        "end_date": "2026-08-02",
        "include_legacy_performance": False,
        "run_validation": True,
        "attempts": 1,
    }

    async def _fake_claim(func):
        return job

    executed: list[dict[str, Any]] = []

    async def _fake_execute(claimed):
        executed.append(claimed)

    monkeypatch.setattr(precompute_queue, "pg_transaction_async", _fake_claim)
    monkeypatch.setattr(precompute_queue, "_execute_job", _fake_execute)

    assert asyncio.run(precompute_queue.process_queue_once()) is True
    assert executed == [job]


def test_worker_idles_when_queue_empty(monkeypatch) -> None:
    monkeypatch.setattr(gmail_import, "get_status", lambda: {"running": False})

    async def _fake_claim(func):
        return None

    monkeypatch.setattr(precompute_queue, "pg_transaction_async", _fake_claim)

    assert asyncio.run(precompute_queue.process_queue_once()) is False


@pytest.mark.parametrize(
    ("attempts", "expected_status"),
    [(1, "queued"), (precompute_queue.MAX_ATTEMPTS, "failed")],
)
def test_failed_job_requeues_until_attempts_exhausted(
    monkeypatch, attempts: int, expected_status: str
) -> None:
    job = {
        "id": 5,
        "source": "scheduler",
        "start_date": "2026-08-01",
        "end_date": "2026-08-02",
        "include_legacy_performance": False,
        "run_validation": True,
        "attempts": attempts,
    }

    async def _boom(_job):
        raise RuntimeError("refresh exploded")

    updates: list[tuple[str, tuple]] = []

    async def _capture_execute(sql: str, params: tuple = ()) -> int:
        updates.append((sql, params))
        return 1

    monkeypatch.setattr(precompute_queue, "_run_refresh_chain", _boom)

    import storage.postgres_database as pg_db

    monkeypatch.setattr(pg_db, "pg_execute", _capture_execute)

    asyncio.run(precompute_queue._execute_job(job))

    final_update = updates[-1]
    assert final_update[1][0] == expected_status
    assert "refresh exploded" in final_update[1][1]


def test_claim_sql_serializes_and_skips_when_job_running() -> None:
    # Lock refused -> no claim.
    conn = FakeConn([{"locked": False}])
    assert precompute_queue._claim_next(conn) is None
    assert len(conn.statements) == 1

    # Lock held but another job is live -> no claim, reclaim ran first.
    conn = FakeConn([{"locked": True}, None, None, {"1": 1}])
    assert precompute_queue._claim_next(conn) is None
    reclaim_sql = " ".join(sql for sql, _ in conn.statements)
    assert "heartbeat_at <" in reclaim_sql
    assert "FOR UPDATE SKIP LOCKED" not in reclaim_sql

    # Lock held, queue has work -> oldest queued job claimed.
    claimed = {
        "id": 9,
        "source": "scheduler",
        "start_date": "2026-08-01",
        "end_date": "2026-08-02",
        "include_legacy_performance": False,
        "run_validation": True,
        "attempts": 1,
    }
    conn = FakeConn([{"locked": True}, None, None, None, claimed])
    assert precompute_queue._claim_next(conn) == claimed
    assert "FOR UPDATE SKIP LOCKED" in conn.statements[-1][0]
