"""Exception observability tests for SeatsService credential fallback."""

from __future__ import annotations

import logging

import pytest

from services.seats_service import BuyerSeat, SeatsService


@pytest.mark.asyncio
async def test_get_credentials_with_fallback_logs_warning_on_legacy_config_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Config:
        def is_configured(self) -> bool:
            return True

        def get_service_account_path(self):
            raise RuntimeError("legacy credentials missing")

    service = SeatsService()
    seat = BuyerSeat(buyer_id="1111111111", bidder_id="1111111111", display_name="Customer Alpha")

    async def _no_multi_account(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "get_credentials_for_seat", _no_multi_account)
    monkeypatch.setenv("OAUTH2_PROXY_ENABLED", "1")

    with caplog.at_level(logging.WARNING):
        result = await service.get_credentials_with_fallback(seat=seat, config=_Config())

    assert result is None
    assert "Legacy ConfigManager credential fallback failed" in caplog.text
