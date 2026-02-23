"""Tests for BigQuery helper retry/timeout behavior."""

from __future__ import annotations

import pytest

pytest.importorskip("google.cloud.bigquery")

from storage.bigquery import run_query


class FakeJob:
    def __init__(self, *, rows=None, error: Exception | None = None) -> None:
        self._rows = rows or []
        self._error = error
        self.cancel_called = False

    def result(self, timeout=None):
        if self._error:
            raise self._error
        return self._rows

    def cancel(self) -> None:
        self.cancel_called = True


class FakeClient:
    def __init__(self, jobs: list[FakeJob]) -> None:
        self.jobs = jobs
        self.calls = 0

    def query(self, _sql, job_config=None):
        self.calls += 1
        return self.jobs[self.calls - 1]


def test_run_query_retries_timeout_then_succeeds(monkeypatch):
    monkeypatch.setattr("storage.bigquery.time.sleep", lambda _sec: None)

    first = FakeJob(error=TimeoutError("timed out"))
    second = FakeJob(rows=[{"ok": 1}])
    client = FakeClient([first, second])

    rows = run_query(
        client,
        sql="SELECT 1",
        params=[],
        timeout_seconds=1,
        max_retries=1,
    )

    assert rows == [{"ok": 1}]
    assert client.calls == 2
    assert first.cancel_called is True


def test_run_query_does_not_retry_non_retryable_errors(monkeypatch):
    monkeypatch.setattr("storage.bigquery.time.sleep", lambda _sec: None)

    first = FakeJob(error=ValueError("bad query"))
    client = FakeClient([first])

    with pytest.raises(ValueError, match="bad query"):
        run_query(
            client,
            sql="SELECT broken",
            params=[],
            timeout_seconds=1,
            max_retries=2,
        )

    assert client.calls == 1
    assert first.cancel_called is True
