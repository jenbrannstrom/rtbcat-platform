"""Exception observability tests for SystemService fallbacks."""

from __future__ import annotations

import logging
import subprocess

import pytest

import services.system_service as system_service
from services.system_service import SystemService


def test_get_node_version_logs_warning_on_subprocess_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(system_service.shutil, "which", lambda _name: "/usr/bin/node")

    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="node --version", timeout=5)

    monkeypatch.setattr(system_service.subprocess, "run", _raise_timeout)

    service = SystemService()
    with caplog.at_level(logging.WARNING):
        available, version = service._get_node_version()

    assert available is True
    assert version is None
    assert "Failed to resolve node version" in caplog.text


@pytest.mark.asyncio
async def test_lookup_geo_names_logs_and_falls_back_on_db_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _raise_db_error(*_args, **_kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(system_service, "pg_query", _raise_db_error)

    service = SystemService()
    with caplog.at_level(logging.WARNING):
        result = await service.lookup_geo_names(["2840", "9999"])

    assert result["2840"] == "USA"
    assert result["9999"] == "9999"
    assert "using fallback mapping" in caplog.text.lower()


@pytest.mark.asyncio
async def test_search_geo_targets_logs_and_returns_empty_on_db_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _raise_db_error(*_args, **_kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(system_service, "pg_query", _raise_db_error)

    service = SystemService()
    with caplog.at_level(logging.WARNING):
        result = await service.search_geo_targets("united")

    assert result == []
    assert "returning empty result" in caplog.text.lower()
