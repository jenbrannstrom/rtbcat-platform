"""Fixture-driven tests for provider conversion connector payloads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.conversion_ingestion_service import ConversionIngestionService
from services.conversion_normalizers import (
    normalize_adjust_payload,
    normalize_appsflyer_payload,
    normalize_branch_payload,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "conversions"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "source_type,fixture_file,normalizer,expectations",
    [
        (
            "appsflyer",
            "appsflyer_postback.json",
            normalize_appsflyer_payload,
            {
                "event_name": "af_first_deposit",
                "event_ts": "2026-02-28T12:34:56Z",
                "buyer_id": "1111111111",
                "billing_id": "cfg-100",
                "click_id": "af-click-1",
                "country": "US",
            },
        ),
        (
            "adjust",
            "adjust_callback.json",
            normalize_adjust_payload,
            {
                "event_name": "first_deposit",
                "event_ts": "2026-02-28T13:00:00Z",
                "click_ts": "2026-02-28T12:50:00Z",
                "campaign_id": "campaign-beta",
                "event_value": "15.75",
                "currency": "eur",
            },
        ),
        (
            "branch",
            "branch_webhook.json",
            normalize_branch_payload,
            {
                "event_name": "first_purchase",
                "event_ts": "2026-02-28T14:00:00Z",
                "campaign_id": "campaign-gamma",
                "click_id": "branch-click-7",
                "event_value": 9.99,
                "currency": "USD",
            },
        ),
    ],
)
def test_provider_fixture_normalization(
    source_type: str,
    fixture_file: str,
    normalizer,
    expectations: dict[str, object],
):
    payload = _load_fixture(fixture_file)
    normalized = normalizer(payload)
    for key, expected in expectations.items():
        assert normalized.get(key) == expected, f"{source_type}: expected {key}={expected!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source_type,fixture_file,normalizer,expected_event_type",
    [
        ("appsflyer", "appsflyer_postback.json", normalize_appsflyer_payload, "first_deposit"),
        ("adjust", "adjust_callback.json", normalize_adjust_payload, "first_deposit"),
        ("branch", "branch_webhook.json", normalize_branch_payload, "first_purchase"),
    ],
)
async def test_provider_fixture_ingestion(
    source_type: str,
    fixture_file: str,
    normalizer,
    expected_event_type: str,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: list[tuple[str, tuple]] = []

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        captured.append((sql, params))
        return 1

    monkeypatch.setattr("services.conversion_ingestion_service.pg_execute", _stub_execute)
    service = ConversionIngestionService()

    payload = normalizer(_load_fixture(fixture_file))
    result = await service.ingest_provider_payload(
        source_type=source_type,
        payload=payload,
        buyer_id_override="1111111111",
    )

    assert result["accepted"] is True
    assert result["duplicate"] is False
    assert result["source_type"] == source_type
    assert result["event_type"] == expected_event_type
    assert result["buyer_id"] == "1111111111"
    assert captured
    assert "INSERT INTO conversion_events" in captured[0][0]

