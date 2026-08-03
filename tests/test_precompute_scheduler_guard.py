from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import precompute


class _Secrets:
    def get(self, name: str) -> str:
        assert name == "PRECOMPUTE_REFRESH_SECRET"
        return "scheduler-secret"

    def get_int(self, name: str, default: int) -> int:
        assert name == "PRECOMPUTE_REFRESH_DAYS"
        return default


def _enqueue_recorder(calls: list[dict]):
    async def _enqueue(**kwargs):
        calls.append(kwargs)
        return {"job_id": 42, "status": "queued", "deduplicated": False}

    return _enqueue


def test_scheduled_precompute_is_blocked_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER", "false")
    request = SimpleNamespace(headers={"X-Precompute-Refresh-Secret": "scheduler-secret"})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(precompute.refresh_precompute_scheduled(request))

    assert exc_info.value.status_code == 503
    assert "CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER" in exc_info.value.detail


def test_scheduled_precompute_rejects_bad_secret(monkeypatch) -> None:
    monkeypatch.setenv("CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER", "true")
    monkeypatch.setattr(precompute, "get_secrets_manager", lambda: _Secrets())
    request = SimpleNamespace(headers={"X-Precompute-Refresh-Secret": "wrong"})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(precompute.refresh_precompute_scheduled(request))

    assert exc_info.value.status_code == 403


def test_scheduled_precompute_enqueues_and_returns_immediately(monkeypatch) -> None:
    monkeypatch.setenv("CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER", "true")
    monkeypatch.setattr(precompute, "get_secrets_manager", lambda: _Secrets())
    calls: list[dict] = []
    monkeypatch.setattr(precompute, "enqueue_precompute_job", _enqueue_recorder(calls))
    request = SimpleNamespace(headers={"X-Precompute-Refresh-Secret": "scheduler-secret"})

    response = asyncio.run(precompute.refresh_precompute_scheduled(request))

    assert response.accepted is True
    assert response.job_id == 42
    assert response.status == "queued"
    assert response.deduplicated is False
    assert len(calls) == 1
    assert calls[0]["source"] == "scheduler"
    assert calls[0]["start_date"] == response.start_date
    assert calls[0]["end_date"] == response.end_date
    # Without Cloud Scheduler headers the window identifies the execution.
    assert calls[0]["dedupe_key"] == (
        f"scheduler:{response.start_date}:{response.end_date}"
    )


def test_scheduled_precompute_dedupes_on_cloud_scheduler_headers(monkeypatch) -> None:
    monkeypatch.setenv("CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER", "true")
    monkeypatch.setattr(precompute, "get_secrets_manager", lambda: _Secrets())
    calls: list[dict] = []
    monkeypatch.setattr(precompute, "enqueue_precompute_job", _enqueue_recorder(calls))
    request = SimpleNamespace(
        headers={
            "X-Precompute-Refresh-Secret": "scheduler-secret",
            "X-CloudScheduler-JobName": "precompute-refresh",
            "X-CloudScheduler-ScheduleTime": "2026-08-03T22:30:00Z",
        }
    )

    asyncio.run(precompute.refresh_precompute_scheduled(request))

    # Retries of one scheduled execution keep the same schedule time, so
    # they collapse onto the same job.
    assert calls[0]["dedupe_key"] == "precompute-refresh:2026-08-03T22:30:00Z"


def test_scheduled_precompute_accepts_while_gmail_import_runs(monkeypatch) -> None:
    """Enqueue must not 409 during an import; the worker defers instead."""
    from scripts import gmail_import

    monkeypatch.setenv("CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER", "true")
    monkeypatch.setattr(precompute, "get_secrets_manager", lambda: _Secrets())
    monkeypatch.setattr(gmail_import, "get_status", lambda: {"running": True})
    calls: list[dict] = []
    monkeypatch.setattr(precompute, "enqueue_precompute_job", _enqueue_recorder(calls))
    request = SimpleNamespace(headers={"X-Precompute-Refresh-Secret": "scheduler-secret"})

    response = asyncio.run(precompute.refresh_precompute_scheduled(request))

    assert response.accepted is True
    assert len(calls) == 1
