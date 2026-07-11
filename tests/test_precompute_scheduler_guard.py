from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import precompute
from scripts import gmail_import


class _Secrets:
    def get(self, name: str) -> str:
        assert name == "PRECOMPUTE_REFRESH_SECRET"
        return "scheduler-secret"


def test_scheduled_precompute_refuses_to_compete_with_gmail_import(monkeypatch) -> None:
    monkeypatch.setattr(precompute, "get_secrets_manager", lambda: _Secrets())
    monkeypatch.setattr(gmail_import, "get_status", lambda: {"running": True})
    request = SimpleNamespace(headers={"X-Precompute-Refresh-Secret": "scheduler-secret"})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(precompute.refresh_precompute_scheduled(request))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Gmail import is still running"
