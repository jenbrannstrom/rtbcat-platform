from __future__ import annotations

import sys

from scripts import gmail_import_worker


def test_worker_enqueues_refresh_after_successful_import(monkeypatch) -> None:
    calls: list[dict] = []

    monkeypatch.setattr(
        gmail_import_worker,
        "_run_import",
        lambda **_kwargs: {
            "success": True,
            "files_imported": 2,
            "imported_date_start": "2026-07-10",
            "imported_date_end": "2026-07-10",
        },
    )

    def _enqueue_refresh(*, start_date: str, end_date: str, job_id: str) -> dict:
        calls.append({"start_date": start_date, "end_date": end_date, "job_id": job_id})
        return {"job_id": 12, "status": "queued", "deduplicated": False}

    monkeypatch.setattr(gmail_import_worker, "_enqueue_refresh", _enqueue_refresh)
    monkeypatch.setattr(
        sys,
        "argv",
        ["gmail_import_worker.py", "--job-id", "job-1", "--quiet"],
    )

    assert gmail_import_worker.main() == 0
    assert calls == [
        {"start_date": "2026-07-10", "end_date": "2026-07-10", "job_id": "job-1"}
    ]


def test_worker_skips_refresh_when_all_imports_are_exact_duplicates(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        gmail_import_worker,
        "_run_import",
        lambda **_kwargs: {
            "success": True,
            "files_imported": 1,
            "duplicate_downstream_skip_count": 1,
            "imported_date_start": "2026-07-05",
            "imported_date_end": "2026-07-05",
        },
    )

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("exact duplicate run must not enqueue a refresh")

    monkeypatch.setattr(gmail_import_worker, "_enqueue_refresh", _unexpected)
    monkeypatch.setattr(
        sys,
        "argv",
        ["gmail_import_worker.py", "--job-id", "job-duplicate", "--quiet"],
    )

    assert gmail_import_worker.main() == 0
    assert "All imported files were exact duplicates" in capsys.readouterr().out
