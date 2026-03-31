from __future__ import annotations

import sys

from scripts import gmail_import_worker


def test_worker_refreshes_endpoints_after_successful_import(monkeypatch) -> None:
    calls: list[tuple[str, int | None]] = []

    monkeypatch.setattr(
        gmail_import_worker,
        "_run_import",
        lambda **_kwargs: {"success": True, "files_imported": 2},
    )

    def _refresh_home_precompute(*, days: int):
        calls.append(("home", days))

    def _refresh_config_precompute(*, days: int):
        calls.append(("config", days))

    def _refresh_endpoint_snapshot():
        calls.append(("endpoints", None))

    monkeypatch.setattr(gmail_import_worker, "_refresh_home_precompute", _refresh_home_precompute)
    monkeypatch.setattr(gmail_import_worker, "_refresh_config_precompute", _refresh_config_precompute)
    monkeypatch.setattr(gmail_import_worker, "_refresh_endpoint_snapshot", _refresh_endpoint_snapshot)
    monkeypatch.setattr(
        sys,
        "argv",
        ["gmail_import_worker.py", "--job-id", "job-1", "--quiet"],
    )

    assert gmail_import_worker.main() == 0
    assert calls == [("home", 30), ("config", 30), ("endpoints", None)]
