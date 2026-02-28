"""API tests for /system/data-health filter forwarding and response shape."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import system as system_router


def _base_payload() -> dict:
    return {
        "checked_at": "2026-02-28T00:00:00+00:00",
        "days": 7,
        "buyer_id": None,
        "state": "healthy",
        "source_freshness": {
            "rtb_daily": {"rows": 10, "max_metric_date": "2026-02-28"},
            "rtb_geo_daily": {"rows": 8, "max_metric_date": "2026-02-28"},
        },
        "serving_freshness": {
            "home_geo_daily": {"rows": 10, "max_metric_date": "2026-02-28"},
            "config_geo_daily": {"rows": 10, "max_metric_date": "2026-02-28"},
            "config_publisher_daily": {"rows": 10, "max_metric_date": "2026-02-28"},
        },
        "coverage": {
            "total_rows": 10,
            "country_missing_pct": 0.0,
            "publisher_missing_pct": 0.0,
            "billing_missing_pct": 0.0,
            "availability_state": "healthy",
        },
        "ingestion_runs": {
            "total_runs": 3,
            "successful_runs": 3,
            "failed_runs": 0,
            "last_started_at": None,
            "last_finished_at": None,
        },
        "optimizer_readiness": {
            "report_completeness": {
                "expected_report_types": 5,
                "available_report_types": 5,
                "coverage_pct": 100.0,
                "missing_report_types": [],
                "availability_state": "healthy",
                "tables": {
                    "rtb_daily": {
                        "rows": 10,
                        "active_days": 7,
                        "expected_days": 7,
                        "coverage_pct": 100.0,
                        "max_metric_date": "2026-02-28",
                        "availability_state": "healthy",
                    }
                },
            },
            "rtb_quality_freshness": {
                "rows": 10,
                "max_metric_date": "2026-02-28",
                "age_days": 0,
                "fresh_within_days": 2,
                "availability_state": "healthy",
            },
            "bidstream_dimension_coverage": {
                "total_rows": 10,
                "platform_missing_pct": 0.0,
                "environment_missing_pct": 0.0,
                "transaction_type_missing_pct": 0.0,
                "availability_state": "healthy",
            },
            "seat_day_completeness": {
                "rows": [
                    {
                        "metric_date": "2026-02-28",
                        "buyer_account_id": "1111111111",
                        "has_rtb_daily": True,
                        "has_rtb_bidstream": True,
                        "has_rtb_bid_filtering": True,
                        "has_rtb_quality": True,
                        "has_web_domain_daily": True,
                        "available_report_types": 5,
                        "expected_report_types": 5,
                        "completeness_pct": 100.0,
                        "availability_state": "healthy",
                        "refreshed_at": "2026-02-28T00:00:00+00:00",
                    }
                ],
                "summary": {
                    "total_seat_days": 1,
                    "healthy_seat_days": 1,
                    "degraded_seat_days": 0,
                    "unavailable_seat_days": 0,
                    "avg_completeness_pct": 100.0,
                    "min_completeness_pct": 100.0,
                    "max_completeness_pct": 100.0,
                },
                "availability_state": "healthy",
                "refreshed_at": "2026-02-28T00:00:00+00:00",
            },
        },
    }


class _StubDataHealthService:
    def __init__(self):
        self.calls: list[dict] = []

    async def get_data_health(self, **kwargs):
        self.calls.append(kwargs)
        payload = _base_payload()
        payload["days"] = kwargs.get("days", payload["days"])
        payload["buyer_id"] = kwargs.get("buyer_id")
        return payload


def _build_client(
    stub_service: _StubDataHealthService,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    app = FastAPI()
    app.include_router(system_router.router, prefix="/api")
    app.dependency_overrides[system_router.get_store] = lambda: SimpleNamespace()
    app.dependency_overrides[system_router.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )

    async def _resolve_buyer_id(
        buyer_id: str | None,
        store=None,
        user=None,
    ) -> str | None:
        return buyer_id

    monkeypatch.setattr(system_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(system_router, "DataHealthService", lambda: stub_service)
    return TestClient(app)


def test_data_health_forwards_filter_params(monkeypatch: pytest.MonkeyPatch):
    stub = _StubDataHealthService()
    client = _build_client(stub, monkeypatch)

    response = client.get(
        "/api/system/data-health",
        params={
            "days": 14,
            "buyer_id": "1111111111",
            "availability_state": "degraded",
            "min_completeness_pct": 70.0,
            "limit": 50,
        },
    )

    assert response.status_code == 200
    assert len(stub.calls) == 1
    assert stub.calls[0] == {
        "days": 14,
        "buyer_id": "1111111111",
        "availability_state": "degraded",
        "min_completeness_pct": 70.0,
        "limit": 50,
    }

    payload = response.json()
    assert payload["optimizer_readiness"]["seat_day_completeness"]["summary"]["total_seat_days"] == 1


def test_data_health_uses_default_filters_when_omitted(monkeypatch: pytest.MonkeyPatch):
    stub = _StubDataHealthService()
    client = _build_client(stub, monkeypatch)

    response = client.get("/api/system/data-health")

    assert response.status_code == 200
    assert len(stub.calls) == 1
    assert stub.calls[0] == {
        "days": 7,
        "buyer_id": None,
        "availability_state": None,
        "min_completeness_pct": None,
        "limit": 200,
    }
