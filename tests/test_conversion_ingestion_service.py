"""Tests for conversion ingestion normalization and idempotency."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.conversion_ingestion_service import ConversionIngestionService


@pytest.mark.asyncio
async def test_ingest_provider_payload_normalizes_appsflyer(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, tuple] = {}

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        captured["sql"] = sql
        captured["params"] = params
        return 1

    monkeypatch.setattr("services.conversion_ingestion_service.pg_execute", _stub_execute)
    service = ConversionIngestionService()

    payload = {
        "appsflyer_id": "af-user-1",
        "eventName": "af_complete_registration",
        "eventTime": "2026-02-28T12:00:00Z",
        "eventValue": '{"af_revenue":"12.34","af_currency":"usd"}',
        "buyer_account_id": "1111111111",
        "billing_id": "cfg-1",
        "campaign_id": "camp-1",
        "country": "US",
        "platform": "android",
        "click_id": "clk-1",
    }

    result = await service.ingest_provider_payload(
        source_type="appsflyer",
        payload=payload,
    )

    assert result["accepted"] is True
    assert result["duplicate"] is False
    assert result["source_type"] == "appsflyer"
    assert result["event_type"] == "registration"
    assert result["buyer_id"] == "1111111111"
    assert result["event_id"].startswith("af-user-1:")

    sql = str(captured.get("sql") or "")
    params = tuple(captured.get("params") or ())
    assert "INSERT INTO conversion_events" in sql
    assert params[0].startswith("af-user-1:")
    assert params[5] == "registration"
    assert params[7] == 12.34
    assert params[8] == "USD"
    assert params[18] is None  # click_ts
    assert isinstance(params[19], datetime)
    assert params[19].tzinfo is not None


@pytest.mark.asyncio
async def test_ingest_provider_payload_marks_duplicates(monkeypatch: pytest.MonkeyPatch):
    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        return 0

    monkeypatch.setattr("services.conversion_ingestion_service.pg_execute", _stub_execute)
    service = ConversionIngestionService()

    result = await service.ingest_provider_payload(
        source_type="generic",
        payload={
            "event_id": "evt-1",
            "event_name": "purchase",
            "event_ts": "2026-02-28T00:00:00Z",
            "buyer_id": "1111111111",
        },
    )

    assert result["accepted"] is True
    assert result["duplicate"] is True
    assert result["event_id"] == "evt-1"
    assert result["event_type"] == "purchase"


@pytest.mark.asyncio
async def test_ingest_csv_counts_rows(monkeypatch: pytest.MonkeyPatch):
    call_count = 0

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        nonlocal call_count
        call_count += 1
        # Mark second row as duplicate
        return 1 if call_count != 2 else 0

    monkeypatch.setattr("services.conversion_ingestion_service.pg_execute", _stub_execute)
    service = ConversionIngestionService()

    csv_text = "\n".join(
        [
            "event_id,event_name,event_ts,buyer_id,billing_id,event_value,currency",
            "evt-1,purchase,2026-02-27T00:00:00Z,1111111111,cfg-1,20,usd",
            "evt-2,registration,2026-02-27T01:00:00Z,1111111111,cfg-1,0,usd",
            ",bad_row,not-a-time,1111111111,cfg-1,1,usd",
        ]
    )

    result = await service.ingest_csv(
        csv_text=csv_text,
        source_type="manual_csv",
    )

    assert result["accepted"] is True
    assert result["rows_read"] == 3
    assert result["rows_inserted"] == 2
    assert result["rows_duplicate"] == 1
    assert result["rows_skipped"] == 0
    # Third row still ingests with fallback event_ts=now and generated event_id.


def test_normalized_event_uses_hash_when_no_id():
    service = ConversionIngestionService()
    now = datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc)
    event = service._normalize_event(  # type: ignore[attr-defined] - unit test on internal helper
        source_type="generic",
        payload={
            "event_name": "purchase",
            "event_ts": now.isoformat(),
            "buyer_id": "1111111111",
            "billing_id": "cfg-1",
        },
        buyer_id_override=None,
        idempotency_key=None,
        import_batch_id="batch-1",
    )

    assert event["event_id"]
    assert len(event["event_id"]) >= 20
    assert event["event_type"] == "purchase"
