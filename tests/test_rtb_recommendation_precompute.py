"""Contracts for buyer-safe recommendation precompute inputs."""

from __future__ import annotations

import pytest

from services import rtb_precompute


@pytest.mark.asyncio
async def test_rtb_refresh_builds_buyer_platform_precompute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bigquery_sql: list[str] = []
    postgres_sql: list[str] = []

    def fake_run_query(client, *, sql, params, **kwargs):
        bigquery_sql.append(sql)
        return []

    class FakeConnection:
        def execute(self, sql, params=()):
            postgres_sql.append(sql)

    async def fake_transaction(callback):
        return callback(FakeConnection())

    monkeypatch.setattr(rtb_precompute, "get_bigquery_client", lambda: object())
    monkeypatch.setattr(
        rtb_precompute,
        "build_table_ref",
        lambda client, *, table_env, default_table: default_table,
    )
    monkeypatch.setattr(rtb_precompute, "run_query", fake_run_query)
    monkeypatch.setattr(rtb_precompute, "execute_many", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        rtb_precompute,
        "record_refresh_log_postgres",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        rtb_precompute,
        "record_refresh_run_postgres",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(rtb_precompute, "pg_transaction_async", fake_transaction)

    result = await rtb_precompute.refresh_rtb_summaries(
        "2026-08-01",
        "2026-08-01",
        buyer_account_id="buyer-a",
    )

    platform_query = next(sql for sql in bigquery_sql if "platform" in sql.lower())
    assert "report_type = 'buyer_spend'" in platform_query
    assert "buyer_account_id = @buyer_account_id" in platform_query
    assert any(
        "CREATE TABLE IF NOT EXISTS rtb_platform_daily" in sql for sql in postgres_sql
    )
    assert any("DELETE FROM rtb_platform_daily" in sql for sql in postgres_sql)
    assert result["buyer_account_id"] == "buyer-a"
