"""Scheduler ownership flag tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import gmail
from services import secrets_health_service
from services.scheduler_guard import scheduler_enabled


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_scheduler_enabled_accepts_explicit_true_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("TEST_SCHEDULER_FLAG", value)
    assert scheduler_enabled("TEST_SCHEDULER_FLAG") is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
def test_scheduler_enabled_rejects_false_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("TEST_SCHEDULER_FLAG", value)
    assert scheduler_enabled("TEST_SCHEDULER_FLAG") is False


def test_scheduler_enabled_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("TEST_SCHEDULER_FLAG", raising=False)
    assert scheduler_enabled("TEST_SCHEDULER_FLAG") is False


def test_scheduled_gmail_import_is_blocked_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER", "false")
    request = SimpleNamespace(headers={"X-Gmail-Import-Secret": "scheduler-secret"})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(gmail.trigger_gmail_import_scheduled(request))

    assert exc_info.value.status_code == 503
    assert "CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER" in exc_info.value.detail


@pytest.mark.parametrize(
    ("flag_name", "secret_name", "enabled_probe"),
    [
        (
            "CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER",
            "GMAIL_IMPORT_SECRET",
            secrets_health_service._is_gmail_scheduler_enabled,
        ),
        (
            "CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER",
            "PRECOMPUTE_REFRESH_SECRET",
            secrets_health_service._is_precompute_scheduler_enabled,
        ),
        (
            "CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER",
            "CREATIVE_CACHE_REFRESH_SECRET",
            secrets_health_service._is_creative_cache_scheduler_enabled,
        ),
    ],
)
def test_scheduler_health_respects_disabled_flag_even_with_secret(
    monkeypatch,
    flag_name: str,
    secret_name: str,
    enabled_probe,
) -> None:
    monkeypatch.setenv(flag_name, "false")
    monkeypatch.setenv(secret_name, "configured-secret")

    assert enabled_probe() is False
