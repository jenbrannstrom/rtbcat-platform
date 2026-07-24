"""Query-shape guards for read-only migration shadow compatibility."""

from __future__ import annotations

import pytest

from storage.postgres_repositories.rtb_bidstream_repo import (
    RtbBidstreamRepository,
)


@pytest.mark.asyncio
async def test_publisher_breakdown_tolerates_pre_spend_schema(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def stub_query(sql: str, params: tuple = ()) -> list[dict]:
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(
        "storage.postgres_repositories.rtb_bidstream_repo.pg_query",
        stub_query,
    )

    rows = await RtbBidstreamRepository().get_publisher_breakdown(
        days=90,
        buyer_id="buyer-1",
        limit=100,
    )

    assert rows == []
    sql = str(captured["sql"])
    assert "to_jsonb(rtb_publisher_daily)->>'spend_micros'" in sql
    assert " as spend_micros" in sql
    assert captured["params"] == (90, "buyer-1", 100)
