"""API tests for creative language flag coverage endpoint."""

from __future__ import annotations

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
        if "GROUP BY creative_id, country" in sql:
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
        buyer_id: str | None,
        search: str | None,
        scan_limit: int,
    ):
        assert buyer_id == "1487810529"
        assert search is None
        assert scan_limit == 250
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
    assert payload["summary"]["language_orange"] == 1
    assert payload["summary"]["geo_red"] == 1


def test_language_flag_coverage_endpoint_tolerates_bad_raw_data_and_aux_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = object()

    async def _resolve_buyer_id(buyer_id, store=None, user=None):
        _ = (store, user)
        return buyer_id

    async def _fake_list_creatives_for_language_flag_coverage(
        buyer_id: str | None,
        search: str | None,
        scan_limit: int,
    ):
        assert buyer_id == "1487810529"
        assert search is None
        assert scan_limit == 250
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
        buyer_id: str | None,
        search: str | None,
        scan_limit: int,
    ):
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
