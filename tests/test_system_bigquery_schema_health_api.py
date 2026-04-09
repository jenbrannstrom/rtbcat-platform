"""API tests for /system/bigquery-raw-schema-health."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from tests.support.asgi_client import SyncASGIClient

from api.routers import system as system_router


def test_bigquery_raw_schema_health_endpoint_returns_admin_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "checked_at": "2026-04-09T00:00:00+00:00",
        "enabled": True,
        "project": "catscan-prod-202601",
        "dataset": "rtbcat_analytics",
        "bucket": "raw-bucket",
        "healthy": False,
        "status": "degraded",
        "summary": {
            "tables_checked": 4,
            "healthy_tables": 3,
            "degraded_tables": 1,
            "unavailable_tables": 0,
            "missing_columns": 1,
        },
        "tables": [
            {
                "table_name": "rtb_bid_filtering",
                "table_id": "catscan-prod-202601.rtbcat_analytics.rtb_bid_filtering",
                "exists": True,
                "status": "degraded",
                "expected_columns": ["metric_date", "report_type"],
                "actual_columns": ["metric_date"],
                "missing_columns": ["report_type"],
                "error": None,
            }
        ],
    }

    app = FastAPI()
    app.include_router(system_router.router, prefix="/api")
    app.dependency_overrides[system_router.require_admin] = lambda: SimpleNamespace(
        id="u1", role="sudo", email="admin@example.com"
    )
    monkeypatch.setattr(system_router, "get_bigquery_raw_schema_health", lambda: payload)

    client = SyncASGIClient(app)
    response = client.get("/api/system/bigquery-raw-schema-health")

    assert response.status_code == 200
    assert response.json()["summary"]["degraded_tables"] == 1
    assert response.json()["tables"][0]["missing_columns"] == ["report_type"]
