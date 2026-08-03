"""Mixed-seat isolation contracts for all recommendation analyzers."""

from __future__ import annotations

from typing import Any

import pytest

from analytics import (
    config_analyzer,
    creative_analyzer,
    fraud_analyzer,
    geo_analyzer,
    size_analyzer,
)
from analytics import recommendation_data, recommendation_engine
from analytics.recommendation_engine import (
    Action,
    Confidence,
    Impact,
    Recommendation,
    RecommendationType,
    Severity,
)


def _assert_scoped_queries(calls: list[tuple[str, tuple[Any, ...]]]) -> None:
    assert calls
    for sql, params in calls:
        assert "buyer_account_id = ?" in sql
        assert params[0] in {"buyer-a", "buyer-b"}


@pytest.mark.asyncio
async def test_size_analyzer_isolates_mixed_seats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fake_query(sql, params):
        calls.append((sql, params))
        if "config_creative_daily" in sql:
            return []
        size = "300x250" if params[0] == "buyer-a" else "728x90"
        return [{"canonical_size": size, "request_count": 140_000}]

    monkeypatch.setattr(size_analyzer, "db_query", fake_query)
    analyzer = size_analyzer.SizeAnalyzer()

    buyer_a = await analyzer.analyze(buyer_id="buyer-a", days=7)
    buyer_b = await analyzer.analyze(buyer_id="buyer-b", days=7)

    assert {rec.actions[0].target_id for rec in buyer_a} == {"300x250"}
    assert {rec.actions[0].target_id for rec in buyer_b} == {"728x90"}
    _assert_scoped_queries(calls)


@pytest.mark.asyncio
async def test_creative_analyzer_isolates_mixed_seats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fake_query_one(sql, params):
        calls.append((sql, params))
        return {"total_impressions": 10_000, "total_clicks": 1_000}

    async def fake_query(sql, params):
        calls.append((sql, params))
        if "SUM(clicks), 0) = 0" in sql:
            return []
        creative_id = "creative-a" if params[0] == "buyer-a" else "creative-b"
        return [
            {
                "id": creative_id,
                "impressions": 2_000,
                "clicks": 1,
                "spend_micros": 20_000_000,
            }
        ]

    monkeypatch.setattr(creative_analyzer, "db_query_one", fake_query_one)
    monkeypatch.setattr(creative_analyzer, "db_query", fake_query)
    analyzer = creative_analyzer.CreativeAnalyzer()

    buyer_a = await analyzer.analyze(buyer_id="buyer-a", days=7)
    buyer_b = await analyzer.analyze(buyer_id="buyer-b", days=7)

    assert buyer_a[0].affected_creatives == ["creative-a"]
    assert buyer_b[0].affected_creatives == ["creative-b"]
    _assert_scoped_queries(calls)


@pytest.mark.asyncio
async def test_geo_analyzer_isolates_mixed_seats_and_has_no_creative_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fake_query_one(sql, params):
        calls.append((sql, params))
        return {"total_impressions": 10_000, "total_clicks": 1_000}

    async def fake_query(sql, params):
        calls.append((sql, params))
        geo = "ZA" if params[0] == "buyer-a" else "DE"
        return [
            {
                "geo": geo,
                "impressions": 2_000,
                "clicks": 1,
                "spend_micros": 20_000_000,
            }
        ]

    monkeypatch.setattr(geo_analyzer, "db_query_one", fake_query_one)
    monkeypatch.setattr(geo_analyzer, "db_query", fake_query)
    analyzer = geo_analyzer.GeoAnalyzer()

    buyer_a = await analyzer.analyze(buyer_id="buyer-a", days=7)
    buyer_b = await analyzer.analyze(buyer_id="buyer-b", days=7)

    assert buyer_a[0].actions[0].target_id == "ZA"
    assert buyer_b[0].actions[0].target_id == "DE"
    assert buyer_a[0].affected_creatives == []
    assert buyer_b[0].affected_creatives == []
    _assert_scoped_queries(calls)


@pytest.mark.asyncio
async def test_fraud_analyzer_isolates_mixed_seats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fake_query(sql, params):
        calls.append((sql, params))
        if "rtb_app_size_daily" not in sql:
            return []
        source = "bad-a.example" if params[0] == "buyer-a" else "bad-b.example"
        return [
            {
                "source": source,
                "creative_format": "BANNER",
                "impressions": 10_000,
                "clicks": 1_500,
                "spend_micros": 10_000_000,
            }
        ]

    monkeypatch.setattr(fraud_analyzer, "db_query", fake_query)
    analyzer = fraud_analyzer.FraudAnalyzer()

    buyer_a = await analyzer.analyze(buyer_id="buyer-a", days=7)
    buyer_b = await analyzer.analyze(buyer_id="buyer-b", days=7)

    assert buyer_a[0].actions[0].target_id == "bad-a.example"
    assert buyer_b[0].actions[0].target_id == "bad-b.example"
    _assert_scoped_queries(calls)


@pytest.mark.asyncio
async def test_config_analyzer_isolates_mixed_seats_and_has_no_creative_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fake_query_one(sql, params):
        calls.append((sql, params))
        return {
            "total_queries": 100,
            "total_impressions": 100,
            "total_spend_micros": 0,
        }

    async def fake_query(sql, params):
        calls.append((sql, params))
        if "rtb_platform_daily" in sql:
            return []
        fmt = "BANNER_A" if params[0] == "buyer-a" else "VIDEO_B"
        return [
            {
                "format": fmt,
                "queries": 20_000,
                "impressions": 100,
                "creative_count": 1,
            }
        ]

    monkeypatch.setattr(config_analyzer, "db_query_one", fake_query_one)
    monkeypatch.setattr(config_analyzer, "db_query", fake_query)
    analyzer = config_analyzer.ConfigAnalyzer()

    buyer_a = await analyzer.analyze(buyer_id="buyer-a", days=7)
    buyer_b = await analyzer.analyze(buyer_id="buyer-b", days=7)

    assert buyer_a[0].actions[0].target_id == "BANNER_A"
    assert buyer_b[0].actions[0].target_id == "VIDEO_B"
    assert buyer_a[0].affected_creatives == []
    assert buyer_b[0].affected_creatives == []
    _assert_scoped_queries(calls)


@pytest.mark.asyncio
async def test_engine_ids_and_persistence_are_buyer_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyzer_calls: list[str] = []
    saved: list[tuple[str, str]] = []

    async def available(*, buyer_id: str, days: int) -> None:
        return None

    class FakeAnalyzer:
        async def analyze(self, *, buyer_id: str, days: int):
            analyzer_calls.append(buyer_id)
            return [
                Recommendation(
                    id="temporary",
                    type=RecommendationType.GEO_EXCLUSION,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    title="Exclude wasteful geo",
                    description="Scoped test recommendation",
                    evidence=[],
                    impact=Impact(1, 100, 2, 5, 60),
                    actions=[Action("exclude", "geo", "ZA", "South Africa")],
                )
            ]

    async def save(*, buyer_id: str, rec: Recommendation) -> None:
        saved.append((buyer_id, rec.id))

    monkeypatch.setattr(
        recommendation_engine, "ensure_recommendation_data_available", available
    )
    engine = recommendation_engine.RecommendationEngine()
    engine._analyzers = [FakeAnalyzer()]
    monkeypatch.setattr(engine, "save_recommendation", save)

    buyer_a = await engine.generate_recommendations(buyer_id="buyer-a")
    buyer_b = await engine.generate_recommendations(buyer_id="buyer-b")

    assert analyzer_calls == ["buyer-a", "buyer-b"]
    assert buyer_a[0].id != buyer_b[0].id
    assert saved == [
        ("buyer-a", buyer_a[0].id),
        ("buyer-b", buyer_b[0].id),
    ]


@pytest.mark.asyncio
async def test_resolve_update_matches_buyer_and_recommendation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def execute(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return 1

    monkeypatch.setattr(recommendation_engine, "pg_execute", execute)

    resolved = (
        await recommendation_engine.RecommendationEngine().resolve_recommendation(
            buyer_id="buyer-a",
            rec_id="shared-id",
            notes="done",
        )
    )

    assert resolved is True
    assert "WHERE buyer_account_id = %s" in captured["sql"]
    assert "AND id = %s" in captured["sql"]
    assert captured["params"][-2:] == ("buyer-a", "shared-id")


@pytest.mark.asyncio
async def test_recommendation_data_guard_fails_closed_for_empty_buyer_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def query_one(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return {"row_count": 0}

    monkeypatch.setattr(recommendation_data, "db_query_one", query_one)

    with pytest.raises(recommendation_data.RecommendationDataUnavailable):
        await recommendation_data.ensure_recommendation_data_available(
            buyer_id="buyer-a",
            days=7,
        )

    assert "buyer_account_id = ?" in captured["sql"]
    assert captured["params"] == ("buyer-a", "-7 days")
