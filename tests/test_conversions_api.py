"""API tests for conversion endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import conversions as conversions_router


def _hmac_sig(secret: str, payload: dict, timestamp: int | None = None) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    message = body if timestamp is None else f"{timestamp}.{body}"
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


class _StubConversionsService:
    def __init__(self):
        self.get_calls: list[dict] = []
        self.refresh_calls: list[dict] = []
        self.health_calls: list[dict] = []

    async def get_aggregates(self, **kwargs):
        self.get_calls.append(kwargs)
        return {
            "rows": [
                {
                    "agg_date": "2026-02-28",
                    "buyer_id": kwargs.get("buyer_id") or "1111111111",
                    "billing_id": "cfg-1",
                    "country": "US",
                    "publisher_id": "pub-1",
                    "creative_id": "cr-1",
                    "app_id": "com.example.app",
                    "source_type": "appsflyer",
                    "event_type": "first_deposit",
                    "event_count": 5,
                    "event_value_total": 200.0,
                    "impressions": 1000,
                    "clicks": 40,
                    "spend_usd": 80.0,
                    "cost_per_event": 16.0,
                    "event_rate_pct": 12.5,
                    "created_at": "2026-02-28T00:00:00+00:00",
                    "updated_at": "2026-02-28T00:00:00+00:00",
                }
            ],
            "meta": {
                "start_date": "2026-02-15",
                "end_date": "2026-02-28",
                "total": 1,
                "returned": 1,
                "limit": kwargs.get("limit", 200),
                "offset": kwargs.get("offset", 0),
                "has_more": False,
            },
        }

    async def refresh_aggregates(self, **kwargs):
        self.refresh_calls.append(kwargs)
        return {
            "start_date": "2026-02-15",
            "end_date": "2026-02-28",
            "buyer_id": kwargs.get("buyer_id"),
            "deleted_rows": 2,
            "upserted_rows": 3,
        }

    async def get_health(self, **kwargs):
        self.health_calls.append(kwargs)
        return {
            "state": "healthy",
            "buyer_id": kwargs.get("buyer_id"),
            "ingestion": {
                "total_events": 10,
                "max_event_ts": "2026-02-28T00:00:00+00:00",
                "last_ingested_at": "2026-02-28T00:05:00+00:00",
                "lag_hours": 1.0,
            },
            "aggregation": {
                "total_rows": 8,
                "max_agg_date": "2026-02-28",
                "last_aggregated_at": "2026-02-28T00:10:00+00:00",
                "lag_days": 0,
            },
            "checked_at": "2026-02-28T01:00:00+00:00",
        }


class _StubConversionIngestionService:
    def __init__(self, fail_provider: bool = False):
        self.fail_provider = fail_provider
        self.provider_calls: list[dict] = []
        self.csv_calls: list[dict] = []
        self.failure_records: list[dict] = []
        self.list_failures_calls: list[dict] = []
        self.replay_calls: list[int] = []
        self.discard_calls: list[int] = []
        self.stats_calls: list[dict] = []
        self.taxonomy_calls: list[dict] = []

    async def ingest_provider_payload(self, **kwargs):
        self.provider_calls.append(kwargs)
        if self.fail_provider:
            raise ValueError("forced failure for testing")
        return {
            "accepted": True,
            "duplicate": False,
            "source_type": kwargs.get("source_type", "generic"),
            "event_id": "evt-1",
            "event_type": "purchase",
            "buyer_id": kwargs.get("buyer_id_override") or "1111111111",
            "event_ts": "2026-02-28T00:00:00+00:00",
            "import_batch_id": "batch-1",
        }

    async def ingest_csv(self, **kwargs):
        self.csv_calls.append(kwargs)
        return {
            "accepted": True,
            "source_type": kwargs.get("source_type", "manual_csv"),
            "import_batch_id": "batch-2",
            "rows_read": 2,
            "rows_inserted": 2,
            "rows_duplicate": 0,
            "rows_skipped": 0,
            "errors": [],
        }

    async def record_failure(self, **kwargs):
        self.failure_records.append(kwargs)
        return 77

    async def list_failures(self, **kwargs):
        self.list_failures_calls.append(kwargs)
        return {
            "rows": [
                {
                    "id": 77,
                    "source_type": kwargs.get("source_type") or "appsflyer",
                    "buyer_id": kwargs.get("buyer_id"),
                    "endpoint_path": "/conversions/appsflyer/postback",
                    "error_code": "ingestion_error",
                    "error_message": "bad payload",
                    "payload": {"eventName": "af_purchase"},
                    "request_headers": {"Content-Type": "application/json"},
                    "idempotency_key": None,
                    "status": kwargs.get("status") or "pending",
                    "replay_attempts": 0,
                    "last_replayed_at": None,
                    "created_at": "2026-02-28T00:00:00+00:00",
                    "updated_at": "2026-02-28T00:00:00+00:00",
                }
            ],
            "meta": {
                "total": 1,
                "returned": 1,
                "limit": kwargs.get("limit", 100),
                "offset": kwargs.get("offset", 0),
                "has_more": False,
            },
        }

    async def replay_failure(self, failure_id: int):
        self.replay_calls.append(failure_id)
        return {
            "failure_id": failure_id,
            "status": "replayed",
            "result": {
                "accepted": True,
                "duplicate": False,
                "source_type": "appsflyer",
                "event_id": "evt-replay",
                "event_type": "purchase",
                "buyer_id": "1111111111",
                "event_ts": "2026-02-28T00:00:00+00:00",
                "import_batch_id": "batch-replay",
            },
        }

    async def discard_failure(self, failure_id: int):
        self.discard_calls.append(failure_id)
        return True

    async def get_ingestion_stats(self, **kwargs):
        self.stats_calls.append(kwargs)
        return {
            "days": kwargs.get("days", 7),
            "source_type": kwargs.get("source_type"),
            "buyer_id": kwargs.get("buyer_id"),
            "accepted_total": 10,
            "rejected_total": 2,
            "rows": [
                {
                    "metric_date": "2026-02-28",
                    "source_type": kwargs.get("source_type") or "appsflyer",
                    "accepted_count": 10,
                    "rejected_count": 2,
                }
            ],
        }

    async def get_failure_taxonomy(self, **kwargs):
        self.taxonomy_calls.append(kwargs)
        return {
            "days": kwargs.get("days", 7),
            "source_type": kwargs.get("source_type"),
            "buyer_id": kwargs.get("buyer_id"),
            "total_failures": 12,
            "other_count": 0,
            "rows": [
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
            ],
        }


def _build_client(
    stub_service: _StubConversionsService,
    ingestion_stub: _StubConversionIngestionService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    conversions_router._clear_webhook_rate_limit_state()
    app = FastAPI()
    app.include_router(conversions_router.router, prefix="/api")
    app.dependency_overrides[conversions_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[conversions_router.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )

    async def _resolve_buyer_id(
        buyer_id: str | None,
        store=None,
        user=None,
    ) -> str | None:
        return buyer_id

    monkeypatch.setattr(conversions_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(conversions_router, "ConversionsService", lambda: stub_service)
    monkeypatch.setattr(conversions_router, "ConversionIngestionService", lambda: ingestion_stub)
    return TestClient(app)


def test_get_conversion_aggregates_forwards_filters(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.get(
        "/api/conversions/aggregates",
        params={
            "days": 14,
            "buyer_id": "1111111111",
            "billing_id": "cfg-1",
            "source_type": "appsflyer",
            "event_type": "first_deposit",
            "limit": 50,
            "offset": 10,
        },
    )

    assert response.status_code == 200
    assert len(stub.get_calls) == 1
    assert stub.get_calls[0]["buyer_id"] == "1111111111"
    assert stub.get_calls[0]["billing_id"] == "cfg-1"
    assert stub.get_calls[0]["source_type"] == "appsflyer"
    assert stub.get_calls[0]["event_type"] == "first_deposit"
    assert stub.get_calls[0]["limit"] == 50
    assert stub.get_calls[0]["offset"] == 10

    payload = response.json()
    assert payload["meta"]["total"] == 1
    assert payload["rows"][0]["event_count"] == 5


def test_refresh_conversion_aggregates(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post(
        "/api/conversions/aggregates/refresh",
        params={
            "days": 14,
            "buyer_id": "1111111111",
        },
    )

    assert response.status_code == 200
    assert len(stub.refresh_calls) == 1
    assert stub.refresh_calls[0]["days"] == 14
    assert stub.refresh_calls[0]["buyer_id"] == "1111111111"
    payload = response.json()
    assert payload["upserted_rows"] == 3


def test_get_conversion_health(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.get(
        "/api/conversions/health",
        params={"buyer_id": "1111111111"},
    )

    assert response.status_code == 200
    assert len(stub.health_calls) == 1
    assert stub.health_calls[0]["buyer_id"] == "1111111111"
    payload = response.json()
    assert payload["state"] == "healthy"
    assert payload["ingestion"]["total_events"] == 10


def test_get_conversion_readiness(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.get(
        "/api/conversions/readiness",
        params={"buyer_id": "1111111111", "days": 14, "freshness_hours": 72},
    )

    assert response.status_code == 200
    assert len(stub.health_calls) == 1
    assert len(ingestion_stub.stats_calls) == 1
    assert ingestion_stub.stats_calls[0]["buyer_id"] == "1111111111"
    assert ingestion_stub.stats_calls[0]["days"] == 14
    payload = response.json()
    assert payload["state"] == "ready"
    assert payload["buyer_id"] == "1111111111"
    assert payload["accepted_total"] == 10
    assert payload["rejected_total"] == 2
    assert payload["active_sources"] == 1
    assert payload["ingestion_fresh"] is True
    assert payload["reasons"] == []


def test_ingest_generic_postback_forwards_payload(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post(
        "/api/conversions/generic/postback?buyer_id=1111111111",
        json={
            "source_type": "redtrack",
            "event_name": "purchase",
            "event_ts": "2026-02-28T00:00:00Z",
            "event_id": "evt-99",
        },
    )

    assert response.status_code == 200
    assert len(ingestion_stub.provider_calls) == 1
    assert ingestion_stub.provider_calls[0]["source_type"] == "redtrack"
    assert ingestion_stub.provider_calls[0]["buyer_id_override"] == "1111111111"
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["source_type"] == "redtrack"


def test_ingest_redtrack_postback_defaults_source_type(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post(
        "/api/conversions/redtrack/postback?buyer_id=1111111111",
        json={
            "event_name": "purchase",
            "event_ts": "2026-02-28T00:00:00Z",
            "event_id": "evt-rt-1",
        },
    )

    assert response.status_code == 200
    assert len(ingestion_stub.provider_calls) == 1
    assert ingestion_stub.provider_calls[0]["source_type"] == "redtrack"
    assert ingestion_stub.provider_calls[0]["buyer_id_override"] == "1111111111"
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["source_type"] == "redtrack"


def test_ingest_voluum_postback_allows_source_override(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post(
        "/api/conversions/voluum/postback?buyer_id=1111111111",
        json={
            "source_type": "custom_tracker",
            "event_name": "lead",
            "event_ts": "2026-02-28T00:00:00Z",
            "event_id": "evt-vol-1",
        },
    )

    assert response.status_code == 200
    assert len(ingestion_stub.provider_calls) == 1
    assert ingestion_stub.provider_calls[0]["source_type"] == "custom_tracker"
    assert ingestion_stub.provider_calls[0]["buyer_id_override"] == "1111111111"
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["source_type"] == "custom_tracker"


def test_ingest_conversion_pixel_returns_gif_and_forwards_payload(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.get(
        "/api/conversions/pixel",
        params={
            "buyer_id": "1111111111",
            "source_type": "pixel",
            "event_name": "purchase",
            "event_ts": "2026-02-28T00:00:00Z",
            "event_id": "evt-px-1",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/gif")
    assert response.headers["x-catscan-conversion-status"] == "accepted"
    assert response.content.startswith(b"GIF89a")
    assert len(ingestion_stub.provider_calls) == 1
    assert ingestion_stub.provider_calls[0]["source_type"] == "pixel"
    assert ingestion_stub.provider_calls[0]["buyer_id_override"] == "1111111111"


def test_ingest_conversion_pixel_records_dlq_on_ingest_failure(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService(fail_provider=True)
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.get(
        "/api/conversions/pixel",
        params={
            "buyer_id": "1111111111",
            "source_type": "pixel",
            "event_name": "purchase",
            "event_ts": "2026-02-28T00:00:00Z",
            "event_id": "evt-px-2",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/gif")
    assert response.headers["x-catscan-conversion-status"] == "rejected"
    assert response.content.startswith(b"GIF89a")
    assert len(ingestion_stub.provider_calls) == 1
    assert len(ingestion_stub.failure_records) == 1
    assert ingestion_stub.failure_records[0]["source_type"] == "pixel"
    assert ingestion_stub.failure_records[0]["buyer_id"] == "1111111111"


def test_ingest_conversion_pixel_requires_generic_secret_when_configured(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)
    monkeypatch.setenv("CATSCAN_GENERIC_CONVERSION_WEBHOOK_SECRET", "pixel-secret")

    no_secret = client.get(
        "/api/conversions/pixel",
        params={"event_name": "purchase", "event_ts": "2026-02-28T00:00:00Z"},
    )
    assert no_secret.status_code == 401

    with_secret = client.get(
        "/api/conversions/pixel",
        params={"event_name": "purchase", "event_ts": "2026-02-28T00:00:00Z"},
        headers={"X-Webhook-Secret": "pixel-secret"},
    )
    assert with_secret.status_code == 200
    assert with_secret.headers["content-type"].startswith("image/gif")
    assert len(ingestion_stub.provider_calls) == 1


def test_ingest_appsflyer_requires_secret_when_configured(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)
    monkeypatch.setenv("CATSCAN_APPSFLYER_WEBHOOK_SECRET", "top-secret")

    no_secret = client.post(
        "/api/conversions/appsflyer/postback",
        json={"eventName": "af_purchase"},
    )
    assert no_secret.status_code == 401

    with_secret = client.post(
        "/api/conversions/appsflyer/postback",
        headers={"X-Webhook-Secret": "top-secret"},
        json={"eventName": "af_purchase"},
    )
    assert with_secret.status_code == 200
    assert len(ingestion_stub.provider_calls) == 1
    assert ingestion_stub.provider_calls[0]["source_type"] == "appsflyer"


def test_ingest_appsflyer_requires_valid_hmac_when_configured(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)
    monkeypatch.setenv("CATSCAN_APPSFLYER_WEBHOOK_HMAC_SECRET", "hmac-secret")

    payload = {"eventName": "af_purchase", "eventTime": "2026-02-28T00:00:00Z"}
    normalized = conversions_router.normalize_appsflyer_payload(payload)
    signature = _hmac_sig("hmac-secret", normalized)

    invalid = client.post(
        "/api/conversions/appsflyer/postback",
        headers={"X-Signature": "bad-signature"},
        json=payload,
    )
    assert invalid.status_code == 401

    valid = client.post(
        "/api/conversions/appsflyer/postback",
        headers={"X-Signature": f"sha256={signature}"},
        json=payload,
    )
    assert valid.status_code == 200
    assert len(ingestion_stub.provider_calls) == 1
    assert ingestion_stub.provider_calls[0]["source_type"] == "appsflyer"


def test_ingest_appsflyer_rejects_stale_timestamp_when_enforced(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)
    monkeypatch.setenv("CATSCAN_APPSFLYER_WEBHOOK_HMAC_SECRET", "hmac-secret")
    monkeypatch.setenv("CATSCAN_CONVERSIONS_ENFORCE_FRESHNESS", "1")
    monkeypatch.setenv("CATSCAN_CONVERSIONS_MAX_SKEW_SECONDS", "30")
    monkeypatch.setattr(conversions_router, "_current_unix_ts", lambda: 1_700_000_000)

    payload = {"eventName": "af_purchase", "eventTime": "2026-02-28T00:00:00Z"}
    normalized = conversions_router.normalize_appsflyer_payload(payload)
    stale_ts = 1_699_999_000
    signature = _hmac_sig("hmac-secret", normalized, timestamp=stale_ts)

    response = client.post(
        "/api/conversions/appsflyer/postback",
        headers={
            "X-Webhook-Timestamp": str(stale_ts),
            "X-Signature": signature,
        },
        json=payload,
    )

    assert response.status_code == 401
    assert len(ingestion_stub.provider_calls) == 0


def test_ingest_generic_postback_rate_limited_when_enabled(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)
    monkeypatch.setenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setattr(conversions_router, "_current_unix_ts", lambda: 1_700_000_000)

    first = client.post(
        "/api/conversions/generic/postback?buyer_id=1111111111",
        json={
            "source_type": "redtrack",
            "event_name": "purchase",
            "event_ts": "2026-02-28T00:00:00Z",
            "event_id": "evt-100",
        },
    )
    second = client.post(
        "/api/conversions/generic/postback?buyer_id=1111111111",
        json={
            "source_type": "redtrack",
            "event_name": "purchase",
            "event_ts": "2026-02-28T00:00:01Z",
            "event_id": "evt-101",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert len(ingestion_stub.provider_calls) == 1


def test_ingest_csv_upload(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    files = {"file": ("events.csv", "event_id,event_name,event_ts\n1,purchase,2026-02-28T00:00:00Z\n", "text/csv")}
    data = {"source_type": "manual_csv", "buyer_id": "1111111111"}
    response = client.post("/api/conversions/csv/upload", files=files, data=data)

    assert response.status_code == 200
    assert len(ingestion_stub.csv_calls) == 1
    assert ingestion_stub.csv_calls[0]["source_type"] == "manual_csv"
    assert ingestion_stub.csv_calls[0]["buyer_id_override"] == "1111111111"
    payload = response.json()
    assert payload["rows_inserted"] == 2


def test_ingest_failure_records_dlq_item(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService(fail_provider=True)
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post(
        "/api/conversions/generic/postback?buyer_id=1111111111",
        json={"source_type": "generic", "event_name": "purchase"},
    )

    assert response.status_code == 400
    assert len(ingestion_stub.failure_records) == 1
    failure = ingestion_stub.failure_records[0]
    assert failure["source_type"] == "generic"
    assert failure["buyer_id"] == "1111111111"
    payload = response.json()
    assert payload["detail"]["failure_id"] == 77


def test_list_ingestion_failures(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.get(
        "/api/conversions/ingestion/failures",
        params={
            "source_type": "appsflyer",
            "buyer_id": "1111111111",
            "status": "pending",
            "limit": 20,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    assert len(ingestion_stub.list_failures_calls) == 1
    call = ingestion_stub.list_failures_calls[0]
    assert call["source_type"] == "appsflyer"
    assert call["buyer_id"] == "1111111111"
    assert call["status"] == "pending"
    payload = response.json()
    assert payload["meta"]["total"] == 1
    assert payload["rows"][0]["id"] == 77


def test_replay_ingestion_failure(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post("/api/conversions/ingestion/failures/77/replay")

    assert response.status_code == 200
    assert ingestion_stub.replay_calls == [77]
    payload = response.json()
    assert payload["failure_id"] == 77
    assert payload["status"] == "replayed"
    assert payload["result"]["event_id"] == "evt-replay"


def test_discard_ingestion_failure(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post("/api/conversions/ingestion/failures/77/discard")

    assert response.status_code == 200
    assert ingestion_stub.discard_calls == [77]
    payload = response.json()
    assert payload["failure_id"] == 77
    assert payload["discarded"] is True


def test_get_ingestion_stats(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.get(
        "/api/conversions/ingestion/stats",
        params={
            "days": 14,
            "source_type": "appsflyer",
            "buyer_id": "1111111111",
        },
    )

    assert response.status_code == 200
    assert len(ingestion_stub.stats_calls) == 1
    call = ingestion_stub.stats_calls[0]
    assert call["days"] == 14
    assert call["source_type"] == "appsflyer"
    assert call["buyer_id"] == "1111111111"
    payload = response.json()
    assert payload["accepted_total"] == 10
    assert payload["rejected_total"] == 2


def test_get_ingestion_error_taxonomy(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.get(
        "/api/conversions/ingestion/error-taxonomy",
        params={
            "days": 14,
            "source_type": "appsflyer",
            "buyer_id": "1111111111",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert len(ingestion_stub.taxonomy_calls) == 1
    call = ingestion_stub.taxonomy_calls[0]
    assert call["days"] == 14
    assert call["source_type"] == "appsflyer"
    assert call["buyer_id"] == "1111111111"
    assert call["limit"] == 10
    payload = response.json()
    assert payload["total_failures"] == 12
    assert payload["rows"][0]["error_code"] == "invalid_payload"


def test_adjust_callback_accepts_form_payload(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post(
        "/api/conversions/adjust/callback?buyer_id=1111111111",
        data={
            "event_token": "first_deposit",
            "created_at": "2026-02-28T00:00:00Z",
            "revenue": "40.0",
            "currency": "usd",
        },
    )

    assert response.status_code == 200
    assert len(ingestion_stub.provider_calls) == 1
    call = ingestion_stub.provider_calls[0]
    assert call["source_type"] == "adjust"
    assert call["buyer_id_override"] == "1111111111"
    assert call["payload"]["event_name"] == "first_deposit"
    assert call["payload"]["event_ts"] == "2026-02-28T00:00:00Z"


def test_branch_webhook_accepts_query_payload(monkeypatch: pytest.MonkeyPatch):
    stub = _StubConversionsService()
    ingestion_stub = _StubConversionIngestionService()
    client = _build_client(stub, ingestion_stub, monkeypatch)

    response = client.post(
        "/api/conversions/branch/webhook",
        params={
            "name": "purchase",
            "timestamp": "2026-02-28T00:00:00Z",
            "~campaign": "camp-1",
        },
    )

    assert response.status_code == 200
    assert len(ingestion_stub.provider_calls) == 1
    call = ingestion_stub.provider_calls[0]
    assert call["source_type"] == "branch"
    assert call["payload"]["event_name"] == "purchase"
    assert call["payload"]["event_ts"] == "2026-02-28T00:00:00Z"
