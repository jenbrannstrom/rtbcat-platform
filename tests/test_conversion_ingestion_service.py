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


@pytest.mark.asyncio
async def test_record_failure_returns_inserted_id(monkeypatch: pytest.MonkeyPatch):
    async def _stub_insert(sql: str, params: tuple = ()) -> int:
        assert "INSERT INTO conversion_ingestion_failures" in sql
        assert params[0] == "appsflyer"
        assert params[3] == "ingestion_error"
        return 77

    monkeypatch.setattr("services.conversion_ingestion_service.pg_insert_returning_id", _stub_insert)
    service = ConversionIngestionService()

    failure_id = await service.record_failure(
        source_type="appsflyer",
        payload={"eventName": "af_purchase"},
        error_code="ingestion_error",
        error_message="bad payload",
        buyer_id="1111111111",
        endpoint_path="/conversions/appsflyer/postback",
        idempotency_key="idem-1",
        headers={"Content-Type": "application/json"},
    )

    assert failure_id == 77


@pytest.mark.asyncio
async def test_list_failures_shapes_rows_and_meta(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM conversion_ingestion_failures" in sql
        return [
            {
                "id": 77,
                "source_type": "appsflyer",
                "buyer_id": "1111111111",
                "endpoint_path": "/conversions/appsflyer/postback",
                "error_code": "ingestion_error",
                "error_message": "bad payload",
                "payload": {"eventName": "af_purchase"},
                "request_headers": {"Content-Type": "application/json"},
                "idempotency_key": "idem-1",
                "status": "pending",
                "replay_attempts": 0,
                "last_replayed_at": None,
                "created_at": datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
            }
        ]

    async def _stub_query_one(sql: str, params: tuple = ()):
        return {"total_rows": 1}

    monkeypatch.setattr("services.conversion_ingestion_service.pg_query", _stub_query)
    monkeypatch.setattr("services.conversion_ingestion_service.pg_query_one", _stub_query_one)
    service = ConversionIngestionService()

    payload = await service.list_failures(
        source_type="appsflyer",
        buyer_id="1111111111",
        status="pending",
        limit=20,
        offset=0,
    )

    assert payload["meta"]["total"] == 1
    assert payload["meta"]["returned"] == 1
    assert payload["rows"][0]["id"] == 77
    assert payload["rows"][0]["source_type"] == "appsflyer"


@pytest.mark.asyncio
async def test_replay_failure_updates_status(monkeypatch: pytest.MonkeyPatch):
    updates: list[tuple[str, tuple]] = []

    async def _stub_query_one(sql: str, params: tuple = ()):
        return {
            "id": 77,
            "source_type": "appsflyer",
            "buyer_id": "1111111111",
            "payload": {"eventName": "af_purchase"},
            "idempotency_key": "idem-1",
            "replay_attempts": 0,
        }

    async def _stub_execute(sql: str, params: tuple = ()) -> int:
        updates.append((sql, params))
        return 1

    async def _stub_ingest(self, **kwargs):
        return {
            "accepted": True,
            "duplicate": False,
            "source_type": "appsflyer",
            "event_id": "evt-1",
            "event_type": "purchase",
            "buyer_id": "1111111111",
            "event_ts": "2026-02-28T00:00:00+00:00",
            "import_batch_id": "batch-1",
        }

    monkeypatch.setattr("services.conversion_ingestion_service.pg_query_one", _stub_query_one)
    monkeypatch.setattr("services.conversion_ingestion_service.pg_execute", _stub_execute)
    monkeypatch.setattr(ConversionIngestionService, "ingest_provider_payload", _stub_ingest)
    service = ConversionIngestionService()

    payload = await service.replay_failure(77)

    assert payload["failure_id"] == 77
    assert payload["status"] == "replayed"
    assert len(updates) == 1
    assert "status = 'replayed'" in updates[0][0]


@pytest.mark.asyncio
async def test_get_ingestion_stats_returns_totals(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query(sql: str, params: tuple = ()):
        return [
            {
                "metric_date": "2026-02-28",
                "source_type": "appsflyer",
                "accepted_count": 10,
                "rejected_count": 2,
            }
        ]

    monkeypatch.setattr("services.conversion_ingestion_service.pg_query", _stub_query)
    service = ConversionIngestionService()

    payload = await service.get_ingestion_stats(
        days=14,
        source_type="appsflyer",
        buyer_id="1111111111",
    )

    assert payload["days"] == 14
    assert payload["source_type"] == "appsflyer"
    assert payload["buyer_id"] == "1111111111"
    assert payload["accepted_total"] == 10
    assert payload["rejected_total"] == 2
    assert payload["rows"][0]["source_type"] == "appsflyer"


@pytest.mark.asyncio
async def test_get_failure_taxonomy_returns_breakdown(monkeypatch: pytest.MonkeyPatch):
    async def _stub_query(sql: str, params: tuple = ()):
        assert "FROM conversion_ingestion_failures" in sql
        return [
            {
                "error_code": "invalid_payload",
                "failure_count": 7,
                "last_seen_at": "2026-02-28T00:00:00+00:00",
                "sample_error_message": "missing event_name",
            },
            {
                "error_code": "auth_failed",
                "failure_count": 5,
                "last_seen_at": "2026-02-28T01:00:00+00:00",
                "sample_error_message": "bad signature",
            },
        ]

    async def _stub_query_one(sql: str, params: tuple = ()):
        return {"total_failures": 12}

    monkeypatch.setattr("services.conversion_ingestion_service.pg_query", _stub_query)
    monkeypatch.setattr("services.conversion_ingestion_service.pg_query_one", _stub_query_one)
    service = ConversionIngestionService()

    payload = await service.get_failure_taxonomy(
        days=14,
        source_type="appsflyer",
        buyer_id="1111111111",
        limit=10,
    )

    assert payload["days"] == 14
    assert payload["source_type"] == "appsflyer"
    assert payload["buyer_id"] == "1111111111"
    assert payload["total_failures"] == 12
    assert payload["other_count"] == 0
    assert payload["rows"][0]["error_code"] == "invalid_payload"
