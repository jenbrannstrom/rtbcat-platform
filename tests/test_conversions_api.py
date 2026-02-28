"""API tests for conversion endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import conversions as conversions_router


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
    def __init__(self):
        self.provider_calls: list[dict] = []
        self.csv_calls: list[dict] = []

    async def ingest_provider_payload(self, **kwargs):
        self.provider_calls.append(kwargs)
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


def _build_client(
    stub_service: _StubConversionsService,
    ingestion_stub: _StubConversionIngestionService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
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
