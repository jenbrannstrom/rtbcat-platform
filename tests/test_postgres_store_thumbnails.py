"""PostgresStore thumbnail status tests."""

from __future__ import annotations

import pytest

from storage import postgres_store
from storage.postgres_store import PostgresStore


@pytest.mark.asyncio
async def test_get_thumbnail_status_returns_thumbnail_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_pg_query_one(sql: str, params: tuple[str]):
        captured["sql"] = sql
        captured["params"] = params
        return {
            "creative_id": "creative-1",
            "status": "success",
            "error_reason": None,
            "gcs_path": "https://cdn.example.com/thumb.png",
            "updated_at": "2026-06-06T00:00:00+00:00",
        }

    monkeypatch.setattr(postgres_store, "pg_query_one", _fake_pg_query_one)

    result = await PostgresStore().get_thumbnail_status("creative-1")

    assert "gcs_path" in captured["sql"]
    assert captured["params"] == ("creative-1",)
    assert result == {
        "status": "success",
        "error_reason": None,
        "thumbnail_url": "https://cdn.example.com/thumb.png",
        "updated_at": "2026-06-06T00:00:00+00:00",
    }
