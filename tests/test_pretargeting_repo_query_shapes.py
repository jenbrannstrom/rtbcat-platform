"""Query-shape guards for pretargeting repository hot paths."""

from __future__ import annotations

import pytest

from storage.postgres_repositories.pretargeting_repo import PretargetingRepository


@pytest.mark.asyncio
async def test_list_configs_uses_distinct_on_for_bidder_scope(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.pretargeting_repo.pg_query", _stub_query)
    repo = PretargetingRepository()
    rows = await repo.list_configs(bidder_id="4444444444")

    assert rows == []
    sql = str(captured["sql"])
    sql_upper = sql.upper()
    assert "DISTINCT ON" in sql_upper
    assert "ROW_NUMBER()" not in sql_upper
    assert "PC.*" not in sql_upper
    assert "AS MAXIMUM_QPS" in sql_upper
    assert "AS DEDUPE_KEY" in sql_upper
    assert "ORDER BY DEDUPED.DEDUPE_KEY" in sql_upper
    assert captured["params"] == ("4444444444",)


@pytest.mark.asyncio
async def test_list_configs_uses_distinct_on_for_global_scope(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.pretargeting_repo.pg_query", _stub_query)
    repo = PretargetingRepository()
    rows = await repo.list_configs()

    assert rows == []
    sql = str(captured["sql"]).upper()
    assert "DISTINCT ON" in sql
    assert "ROW_NUMBER()" not in sql
    assert "PC.*" not in sql
    assert "AS MAXIMUM_QPS" in sql
    assert captured["params"] == ()


@pytest.mark.asyncio
async def test_list_configs_for_buyer_uses_single_joined_query(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.pretargeting_repo.pg_query", _stub_query)
    repo = PretargetingRepository()
    rows = await repo.list_configs_for_buyer("buyer-1")

    assert rows == []
    sql_upper = str(captured["sql"]).upper()
    assert "JOIN (" in sql_upper
    assert "SELECT DISTINCT BIDDER_ID" in sql_upper
    assert "FROM BUYER_SEATS" in sql_upper
    assert ") BS ON BS.BIDDER_ID = PC.BIDDER_ID" in sql_upper
    assert "WHERE BUYER_ID = %S" in sql_upper
    assert "DISTINCT ON" in sql_upper
    assert captured["params"] == ("buyer-1",)


@pytest.mark.asyncio
async def test_list_configs_applies_limit_when_requested(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.pretargeting_repo.pg_query", _stub_query)
    repo = PretargetingRepository()
    rows = await repo.list_configs(bidder_id="4444444444", limit=250)

    assert rows == []
    sql_upper = str(captured["sql"]).upper()
    assert "LIMIT %S" in sql_upper
    assert captured["params"] == ("4444444444", 250)


@pytest.mark.asyncio
async def test_list_configs_summary_shape_omits_large_targeting_arrays(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.pretargeting_repo.pg_query", _stub_query)
    repo = PretargetingRepository()
    rows = await repo.list_configs(bidder_id="4444444444", limit=100, summary_only=True)

    assert rows == []
    sql_upper = str(captured["sql"]).upper()
    assert "NULL::JSONB AS INCLUDED_FORMATS" in sql_upper
    assert "NULL::JSONB AS INCLUDED_PLATFORMS" in sql_upper
    assert "PC.INCLUDED_FORMATS" not in sql_upper
    assert "PC.INCLUDED_PLATFORMS" not in sql_upper
    assert captured["params"] == ("4444444444", 100)


@pytest.mark.asyncio
async def test_list_history_billing_filter_uses_exists_not_join(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.pretargeting_repo.pg_query", _stub_query)
    repo = PretargetingRepository()
    rows = await repo.list_history(billing_id="777777777777", days=14, limit=50)

    assert rows == []
    sql_upper = str(captured["sql"]).upper()
    assert "EXISTS (" in sql_upper
    assert "LEFT JOIN PRETARGETING_CONFIGS" not in sql_upper
    assert "ORDER BY PH.CHANGED_AT DESC, PH.ID DESC" in sql_upper
    assert captured["params"] == (14, "777777777777", 50)


@pytest.mark.asyncio
async def test_list_history_without_billing_skips_exists(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.pretargeting_repo.pg_query", _stub_query)
    repo = PretargetingRepository()
    rows = await repo.list_history(config_id="cfg-1", days=7, limit=20)

    assert rows == []
    sql_upper = str(captured["sql"]).upper()
    assert "EXISTS (" not in sql_upper
    assert captured["params"] == (7, "cfg-1", 20)
