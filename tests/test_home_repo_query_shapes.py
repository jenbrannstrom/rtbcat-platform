"""Query-shape guards for home analytics repository hot paths."""

from __future__ import annotations

import pytest

from storage.postgres_repositories.home_repo import HomeAnalyticsRepository


@pytest.mark.asyncio
async def test_get_config_rows_uses_sql_limit_and_window_totals_for_buyer_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.home_repo.pg_query", _stub_query)
    repo = HomeAnalyticsRepository()
    expected_start, expected_end = repo.get_window_bounds(14)
    rows = await repo.get_config_rows(days=14, buyer_id="buyer-1")

    assert rows == []
    sql_upper = str(captured["sql"]).upper()
    assert "WITH GROUPED AS" in sql_upper
    assert "SUM(TOTAL_REACHED) OVER () AS OVERALL_TOTAL_REACHED" in sql_upper
    assert "SUM(TOTAL_IMPRESSIONS) OVER () AS OVERALL_TOTAL_IMPRESSIONS" in sql_upper
    assert "LIMIT 20" in sql_upper
    assert captured["params"] == (expected_start, expected_end, "buyer-1")


@pytest.mark.asyncio
async def test_get_config_rows_uses_sql_limit_and_window_totals_for_global_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.home_repo.pg_query", _stub_query)
    repo = HomeAnalyticsRepository()
    expected_start, expected_end = repo.get_window_bounds(7)
    rows = await repo.get_config_rows(days=7, buyer_id=None)

    assert rows == []
    sql_upper = str(captured["sql"]).upper()
    assert "WITH GROUPED AS" in sql_upper
    assert "LIMIT 20" in sql_upper
    assert captured["params"] == (expected_start, expected_end)
