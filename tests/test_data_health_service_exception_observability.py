"""Exception observability fallback tests for DataHealthService."""

from __future__ import annotations

import logging

import pytest

import services.data_health_service as data_health_service
from services.data_health_service import DataHealthService


@pytest.mark.asyncio
async def test_get_ingestion_summary_logs_warning_and_returns_default_on_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _raise(*_args, **_kwargs):
        raise RuntimeError("db unavailable")

    service = DataHealthService()
    monkeypatch.setattr(service, "_query_one_with_timeout", _raise)

    with caplog.at_level(logging.WARNING):
        result = await service._get_ingestion_summary(days=7, buyer_id="1111111111")

    assert result["total_runs"] == 0
    assert result["last_finished_at"] is None
    assert "Data health ingestion summary query failed" in caplog.text


@pytest.mark.asyncio
async def test_get_report_completeness_logs_warning_and_marks_tables_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _raise(*_args, **_kwargs):
        raise RuntimeError("query failed")

    service = DataHealthService()
    monkeypatch.setattr(service, "_query_one_with_timeout", _raise)

    with caplog.at_level(logging.WARNING):
        result = await service._get_report_completeness(days=7, buyer_id="1111111111")

    assert result["available_report_types"] == 0
    assert result["availability_state"] == "unavailable"
    assert "report-completeness query failed for table" in caplog.text


@pytest.mark.asyncio
async def test_get_seat_day_completeness_logs_warning_and_returns_unavailable_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _raise(*_args, **_kwargs):
        raise RuntimeError("seat query failed")

    service = DataHealthService()
    monkeypatch.setattr(data_health_service, "pg_query", _raise)

    with caplog.at_level(logging.WARNING):
        result = await service._get_seat_day_completeness(
            days=7,
            buyer_id="1111111111",
            availability_state=None,
            min_completeness_pct=None,
            limit=100,
        )

    assert result["availability_state"] == "unavailable"
    assert result["summary"]["total_seat_days"] == 0
    assert "Seat-day completeness query failed" in caplog.text
