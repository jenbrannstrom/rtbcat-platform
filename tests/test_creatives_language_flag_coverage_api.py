"""API tests for creative language flag coverage endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from api.routers import creatives as creatives_router
from tests.support.asgi_client import SyncASGIClient


def _build_client(store: object) -> SyncASGIClient:
    app = FastAPI()
    app.include_router(creatives_router.router, prefix="/api")
    app.dependency_overrides[creatives_router.get_store] = lambda: store
    app.dependency_overrides[creatives_router.get_current_user] = lambda: SimpleNamespace(
        id="u1",
        role="sudo",
        email="admin@example.com",
    )
    return SyncASGIClient(app)


@pytest.mark.asyncio
async def test_language_flag_coverage_list_uses_store_list_creatives() -> None:
    calls: list[dict[str, object]] = []

    class _Store:
        async def list_creatives(self, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(id="creative-1")]

    rows = await creatives_router._list_creatives_for_language_flag_coverage(
        _Store(),
        buyer_id="1487810529",
        search="creative",
        scan_limit=350,
    )

    assert [row.id for row in rows] == ["creative-1"]
    assert calls == [
        {
            "buyer_id": "1487810529",
            "search": "creative",
            "limit": 350,
            "offset": 0,
            "include_raw_data": True,
            "sort_by": "spend",
            "sort_days": 30,
        }
    ]


def test_language_flag_coverage_serializes_geo_completed_at_datetime() -> None:
    row = creatives_router.build_creative_language_flag_row(
        creative=SimpleNamespace(
            id="creative-1",
            name="Creative",
            buyer_id="1487810529",
            format="HTML",
            approval_status="APPROVED",
            advertiser_name=None,
            detected_language=None,
            detected_language_code=None,
            raw_data={},
        ),
        serving_countries=["IN"],
        latest_geo_run={
            "status": "failed",
            "error_message": "AI report failed",
            "completed_at": datetime(2026, 6, 6, tzinfo=timezone.utc),
            "result": {},
        },
    )

    model = creatives_router.CreativeLanguageFlagCoverageRow(**row)

    assert model.geo_linguistic_completed_at == "2026-06-06T00:00:00+00:00"


def test_language_flag_coverage_endpoint_returns_expected_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = object()

    async def _resolve_buyer_id(buyer_id, store=None, user=None):
        _ = (store, user)
        return buyer_id

    async def _fake_pg_query(sql: str, params: tuple):
        if "FROM config_creative_daily" in sql:
            return [
                {
                    "creative_id": "1987702299778854923",
                    "spend": 53420000,
                    "imps": 174230,
                    "last_active": "2026-04-13",
                }
            ]
        if "FROM performance_metrics" in sql and "GROUP BY creative_id, geography" in sql:
            return [
                {
                    "creative_id": "1987702299778854923",
                    "country_code": "PH",
                    "spend_micros": 53420000,
                }
            ]
        raise AssertionError(f"Unexpected SQL: {sql}")

    async def _fake_get_latest_runs(_creative_ids):
        return {}

    async def _fake_list_creatives_for_language_flag_coverage(
        passed_store,
        buyer_id: str | None,
        search: str | None,
        scan_limit: int,
    ):
        assert passed_store is store
        assert buyer_id == "1487810529"
        assert search is None
        assert scan_limit == 3000
        return [
            SimpleNamespace(
                id="1987702299778854923",
                name="AED free shipping creative",
                buyer_id="1487810529",
                format="HTML",
                approval_status="APPROVED",
                advertiser_name=None,
                detected_language=None,
                detected_language_code=None,
                raw_data={
                    "html": {
                        "snippet": "Only for new app users AED 0 FREE SHIPPING",
                    }
                },
            )
        ]

    monkeypatch.setattr(creatives_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(creatives_router, "pg_query", _fake_pg_query)
    monkeypatch.setattr(creatives_router.analysis_repo, "get_latest_runs", _fake_get_latest_runs)
    monkeypatch.setattr(
        creatives_router,
        "_list_creatives_for_language_flag_coverage",
        _fake_list_creatives_for_language_flag_coverage,
    )

    client = _build_client(store)
    response = client.get("/api/creatives/language-flag-coverage?buyer_id=1487810529")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    row = payload["rows"][0]
    assert row["creative_id"] == "1987702299778854923"
    assert row["language_flag_status"] == "orange"
    assert row["currency_flag_status"] == "red"
    assert row["geo_linguistic_status"] == "red"
    assert row["serving_countries"] == ["PH"]
    assert row["detected_currencies"] == ["AED"]
    assert "language_analysis_error" in row
    assert payload["summary"]["language_orange"] == 1
    assert payload["summary"]["geo_red"] == 1
    assert payload["summary"]["count_confirmed"] == 1
    assert payload["summary"]["spend_confirmed_micros"] == 53420000
    assert payload["summary"]["spend_at_risk_micros"] == 53420000


def test_language_flag_coverage_sorts_by_severity_then_spend_and_filters_severity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = object()

    async def _resolve_buyer_id(buyer_id, store=None, user=None):
        _ = (store, user)
        return buyer_id

    creatives = [
        SimpleNamespace(id="red-low", name="Red low", buyer_id="1487810529"),
        SimpleNamespace(id="red-high", name="Red high", buyer_id="1487810529"),
        SimpleNamespace(id="review-high", name="Review high", buyer_id="1487810529"),
    ]

    async def _fake_list_creatives_for_language_flag_coverage(
        passed_store,
        buyer_id: str | None,
        search: str | None,
        scan_limit: int,
    ):
        _ = (passed_store, buyer_id, search, scan_limit)
        return creatives

    async def _fake_spend_snapshot(_creative_ids):
        return {
            "red-low": {"spend": 100, "imps": 10, "last_active": "2026-06-01"},
            "red-high": {"spend": 500, "imps": 50, "last_active": "2026-06-01"},
            "review-high": {"spend": 1000, "imps": 100, "last_active": "2026-06-01"},
        }

    async def _fake_serving_country_map(_creative_ids, _days):
        return {creative.id: ["DE"] for creative in creatives}

    async def _fake_get_latest_runs(_creative_ids):
        return {}

    def _fake_build_row(creative, serving_countries, latest_geo_run):
        _ = (serving_countries, latest_geo_run)
        status = "orange" if creative.id == "review-high" else "red"
        return {
            "creative_id": creative.id,
            "creative_name": creative.name,
            "buyer_id": creative.buyer_id,
            "format": "HTML",
            "approval_status": "APPROVED",
            "detected_language": "Spanish",
            "detected_language_code": "es",
            "language_confidence": None,
            "language_source": "heuristic",
            "language_analyzed_at": None,
            "language_analysis_error": None,
            "heuristic_language_code": "es",
            "effective_language_code": "es",
            "serving_countries": ["DE"],
            "detected_currencies": [],
            "language_flag_status": "green",
            "language_flag_reason": "Language accepted",
            "language_flag_source": "heuristic",
            "currency_flag_status": "green",
            "currency_flag_reason": "No currency issue",
            "geo_linguistic_status": status,
            "geo_linguistic_reason": "Market mismatch",
            "geo_linguistic_decision": "needs_review" if status == "orange" else "mismatch",
            "geo_linguistic_completed_at": None,
        }

    monkeypatch.setattr(creatives_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(
        creatives_router,
        "_list_creatives_for_language_flag_coverage",
        _fake_list_creatives_for_language_flag_coverage,
    )
    monkeypatch.setattr(creatives_router, "_get_spend_snapshot", _fake_spend_snapshot)
    monkeypatch.setattr(creatives_router, "_get_serving_country_map", _fake_serving_country_map)
    monkeypatch.setattr(creatives_router.analysis_repo, "get_latest_runs", _fake_get_latest_runs)
    monkeypatch.setattr(creatives_router, "build_creative_language_flag_row", _fake_build_row)

    client = _build_client(store)
    response = client.get("/api/creatives/language-flag-coverage?buyer_id=1487810529")

    assert response.status_code == 200
    payload = response.json()
    assert [row["creative_id"] for row in payload["rows"]] == [
        "red-high",
        "red-low",
        "review-high",
    ]
    assert payload["summary"]["count_confirmed"] == 2
    assert payload["summary"]["count_review"] == 1
    assert payload["summary"]["spend_confirmed_micros"] == 600
    assert payload["summary"]["spend_review_micros"] == 1000

    filtered = client.get(
        "/api/creatives/language-flag-coverage?buyer_id=1487810529&severity=review"
    )
    assert filtered.status_code == 200
    assert [row["creative_id"] for row in filtered.json()["rows"]] == ["review-high"]


def test_language_flag_coverage_endpoint_tolerates_bad_raw_data_and_aux_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = object()

    async def _resolve_buyer_id(buyer_id, store=None, user=None):
        _ = (store, user)
        return buyer_id

    async def _fake_list_creatives_for_language_flag_coverage(
        passed_store,
        buyer_id: str | None,
        search: str | None,
        scan_limit: int,
    ):
        assert passed_store is store
        assert buyer_id == "1487810529"
        assert search is None
        assert scan_limit == 3000
        return [
            SimpleNamespace(
                id="broken-raw-data",
                name="Broken raw data creative",
                buyer_id="1487810529",
                format="HTML",
                approval_status="APPROVED",
                advertiser_name=None,
                detected_language=None,
                detected_language_code=None,
                raw_data="not-json",
            )
        ]

    async def _fail_spend_snapshot(_creative_ids):
        raise RuntimeError("spend snapshot unavailable")

    async def _fail_serving_countries(_creative_ids, _days):
        raise RuntimeError("serving countries unavailable")

    async def _fail_geo_runs(_creative_ids):
        raise RuntimeError("geo repo unavailable")

    monkeypatch.setattr(creatives_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(
        creatives_router,
        "_list_creatives_for_language_flag_coverage",
        _fake_list_creatives_for_language_flag_coverage,
    )
    monkeypatch.setattr(creatives_router, "_get_spend_snapshot", _fail_spend_snapshot)
    monkeypatch.setattr(creatives_router, "_get_serving_country_map", _fail_serving_countries)
    monkeypatch.setattr(creatives_router.analysis_repo, "get_latest_runs", _fail_geo_runs)

    client = _build_client(store)
    response = client.get("/api/creatives/language-flag-coverage?buyer_id=1487810529")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    row = payload["rows"][0]
    assert row["creative_id"] == "broken-raw-data"
    assert row["language_flag_status"] == "orange"
    assert row["language_flag_reason"] == "No serving-country data available"
    assert row["detected_currencies"] == []
    assert row["spend_30d_micros"] == 0


def test_language_flag_refresh_endpoint_queues_batch_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = object()
    captured: list[dict[str, object]] = []

    async def _resolve_buyer_id(buyer_id, store=None, user=None):
        _ = (store, user)
        return buyer_id

    async def _fake_list_creatives_for_language_flag_coverage(
        passed_store,
        buyer_id: str | None,
        search: str | None,
        scan_limit: int,
    ):
        assert passed_store is store
        assert buyer_id == "1487810529"
        assert search == "2013919535262576642"
        assert scan_limit == 500
        return [
            SimpleNamespace(id="2013919535262576642"),
            SimpleNamespace(id="1987702299778854923"),
        ]

    async def _fake_refresh_language_flag_coverage_batch(
        creative_ids,
        store,
        triggered_by,
        force,
        days,
    ):
        captured.append(
            {
                "creative_ids": creative_ids,
                "store": store,
                "triggered_by": triggered_by,
                "force": force,
                "days": days,
            }
        )

    monkeypatch.setattr(creatives_router, "resolve_buyer_id", _resolve_buyer_id)
    monkeypatch.setattr(
        creatives_router,
        "_list_creatives_for_language_flag_coverage",
        _fake_list_creatives_for_language_flag_coverage,
    )
    monkeypatch.setattr(
        creatives_router,
        "_refresh_language_flag_coverage_batch",
        _fake_refresh_language_flag_coverage_batch,
    )

    client = _build_client(store)
    response = client.post(
        "/api/creatives/language-flag-coverage/refresh"
        "?buyer_id=1487810529&search=2013919535262576642&refresh_limit=500"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["buyer_id"] == "1487810529"
    assert payload["queued_creatives"] == 2
    assert payload["refresh_limit"] == 500
    assert payload["force"] is True
    assert payload["message"] == "Queued refresh for 2 creatives."
    assert captured == [
        {
            "creative_ids": ["2013919535262576642", "1987702299778854923"],
            "store": store,
            "triggered_by": "admin@example.com",
            "force": True,
            "days": 7,
        }
    ]
