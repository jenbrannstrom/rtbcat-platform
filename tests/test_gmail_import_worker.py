from __future__ import annotations

import sys

from scripts import gmail_import_worker


def test_worker_refreshes_endpoints_after_successful_import(monkeypatch) -> None:
    calls: list[tuple[str, int | None]] = []

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

    def _refresh_home_precompute(*, start_date: str, end_date: str):
        calls.append(("home", start_date, end_date))

    def _refresh_config_precompute(*, start_date: str, end_date: str):
        calls.append(("config", start_date, end_date))

    def _refresh_rtb_precompute(*, start_date: str, end_date: str):
        calls.append(("rtb", start_date, end_date))

    def _refresh_legacy_performance(*, start_date: str, end_date: str):
        calls.append(("legacy", start_date, end_date))

    def _refresh_endpoint_snapshot():
        calls.append(("endpoints", None))

    monkeypatch.setattr(gmail_import_worker, "_refresh_home_precompute", _refresh_home_precompute)
    monkeypatch.setattr(gmail_import_worker, "_refresh_config_precompute", _refresh_config_precompute)
    monkeypatch.setattr(gmail_import_worker, "_refresh_rtb_precompute", _refresh_rtb_precompute)
    monkeypatch.setattr(
        gmail_import_worker,
        "_refresh_legacy_performance",
        _refresh_legacy_performance,
    )
    monkeypatch.setattr(gmail_import_worker, "_refresh_endpoint_snapshot", _refresh_endpoint_snapshot)
    monkeypatch.setattr(
        sys,
        "argv",
        ["gmail_import_worker.py", "--job-id", "job-1", "--quiet"],
    )

    assert gmail_import_worker.main() == 0
    assert calls == [
        ("home", "2026-07-10", "2026-07-10"),
        ("config", "2026-07-10", "2026-07-10"),
        ("rtb", "2026-07-10", "2026-07-10"),
        ("legacy", "2026-07-10", "2026-07-10"),
        ("endpoints", None),
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
        raise AssertionError("exact duplicate run must not refresh published data")

    monkeypatch.setattr(gmail_import_worker, "_refresh_home_precompute", _unexpected)
    monkeypatch.setattr(gmail_import_worker, "_refresh_config_precompute", _unexpected)
    monkeypatch.setattr(gmail_import_worker, "_refresh_rtb_precompute", _unexpected)
    monkeypatch.setattr(gmail_import_worker, "_refresh_legacy_performance", _unexpected)
    monkeypatch.setattr(gmail_import_worker, "_refresh_endpoint_snapshot", _unexpected)
    monkeypatch.setattr(
        sys,
        "argv",
        ["gmail_import_worker.py", "--job-id", "job-duplicate", "--quiet"],
    )

    assert gmail_import_worker.main() == 0
    assert "All imported files were exact duplicates" in capsys.readouterr().out
