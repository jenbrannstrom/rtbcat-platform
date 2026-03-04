"""Exception observability tests for system router fallbacks."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from api.routers import system as system_router


@pytest.mark.asyncio
async def test_health_check_logs_warning_when_service_account_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _FailingStore:
        async def get_service_accounts(self, active_only: bool = False):
            del active_only
            raise RuntimeError("db unavailable")

    async def _pg_ok(*_args, **_kwargs):
        return {"ok": 1}

    monkeypatch.setattr(system_router, "pg_query_one", _pg_ok)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with caplog.at_level(logging.WARNING):
        payload = await system_router.health_check(
            config=SimpleNamespace(),
            store=_FailingStore(),
        )

    assert payload.configured is False
    assert payload.has_credentials is False
    assert "Health check failed to read service accounts" in caplog.text


@pytest.mark.asyncio
async def test_health_check_logs_warning_when_database_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _HealthyStore:
        async def get_service_accounts(self, active_only: bool = False):
            del active_only
            return []

    async def _pg_fail(*_args, **_kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(system_router, "pg_query_one", _pg_fail)
    monkeypatch.setenv("POSTGRES_DSN", "postgres://example")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with caplog.at_level(logging.WARNING):
        payload = await system_router.health_check(
            config=SimpleNamespace(),
            store=_HealthyStore(),
        )

    assert payload.database_exists is False
    assert "Health check database probe failed" in caplog.text
