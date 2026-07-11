from __future__ import annotations

from scripts import check_gmail_import_idle


def test_guard_allows_deploy_when_import_is_idle(monkeypatch) -> None:
    monkeypatch.setattr(check_gmail_import_idle, "get_status", lambda: {"running": False})
    assert check_gmail_import_idle.main() == 0


def test_guard_blocks_deploy_when_import_is_running(monkeypatch) -> None:
    monkeypatch.setattr(check_gmail_import_idle, "get_status", lambda: {"running": True})
    assert check_gmail_import_idle.main() == 1
