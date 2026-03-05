"""Query-shape guards for pending-changes repository paths."""

from __future__ import annotations

import pytest

from storage.postgres_repositories.changes_repo import ChangesRepository


@pytest.mark.asyncio
async def test_list_pending_changes_billing_scope_prefers_composite_filter(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.changes_repo.pg_query", _stub_query)
    repo = ChangesRepository()
    rows = await repo.list_pending_changes(billing_id="777777777777", status="pending", limit=25)

    assert rows == []
    sql_lower = str(captured["sql"]).lower()
    assert "where billing_id = %s and status = %s" in sql_lower
    assert "order by created_at desc, id desc" in sql_lower
    assert captured["params"] == ("777777777777", "pending", 25)


@pytest.mark.asyncio
async def test_list_pending_changes_global_scope_filters_by_status(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.changes_repo.pg_query", _stub_query)
    repo = ChangesRepository()
    rows = await repo.list_pending_changes(billing_id=None, status="pending", limit=10)

    assert rows == []
    sql_lower = str(captured["sql"]).lower()
    assert "where status = %s" in sql_lower
    assert "where billing_id = %s and status = %s" not in sql_lower
    assert "order by created_at desc, id desc" in sql_lower
    assert captured["params"] == ("pending", 10)
