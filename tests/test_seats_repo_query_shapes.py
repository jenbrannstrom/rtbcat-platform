"""Query-shape guards for SeatsRepository hot paths."""

from __future__ import annotations

import pytest

from storage.postgres_repositories.seats_repo import SeatsRepository


@pytest.mark.asyncio
async def test_get_buyer_seats_by_ids_uses_allow_list_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _stub_query(sql: str, params: tuple = ()):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("storage.postgres_repositories.seats_repo.pg_query", _stub_query)
    repo = SeatsRepository()
    rows = await repo.get_buyer_seats_by_ids(
        buyer_ids=["buyer-1", "buyer-2"],
        bidder_id="bidder-1",
        active_only=True,
    )

    assert rows == []
    sql_upper = str(captured["sql"]).upper()
    assert "FROM BUYER_SEATS" in sql_upper
    assert "BUYER_ID = ANY(%S)" in sql_upper
    assert "BIDDER_ID = %S" in sql_upper
    assert "ACTIVE = TRUE" in sql_upper
    assert captured["params"] == (["buyer-1", "buyer-2"], "bidder-1")


@pytest.mark.asyncio
async def test_get_buyer_seats_by_ids_short_circuits_for_empty_allow_list(
) -> None:
    repo = SeatsRepository()
    rows = await repo.get_buyer_seats_by_ids(
        buyer_ids=[],
        bidder_id="bidder-1",
        active_only=True,
    )

    assert rows == []
