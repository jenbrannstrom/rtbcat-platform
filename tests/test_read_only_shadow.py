from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.read_only_shadow import ReadOnlyShadowMiddleware
from storage.postgres_store import PostgresStore


def _client(monkeypatch, *, enabled: bool) -> TestClient:
    if enabled:
        monkeypatch.setenv("CATSCAN_READ_ONLY_SHADOW", "true")
    else:
        monkeypatch.delenv("CATSCAN_READ_ONLY_SHADOW", raising=False)

    app = FastAPI()
    app.add_middleware(ReadOnlyShadowMiddleware)

    @app.get("/read")
    async def read():
        return {"ok": True}

    @app.post("/write")
    async def write():
        return {"mutated": True}

    return TestClient(app)


def test_read_only_shadow_allows_reads_and_labels_response(monkeypatch) -> None:
    client = _client(monkeypatch, enabled=True)

    response = client.get("/read")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["X-CatScan-Shadow"] == "read-only"


def test_read_only_shadow_blocks_state_changing_methods(monkeypatch) -> None:
    client = _client(monkeypatch, enabled=True)

    response = client.post("/write")

    assert response.status_code == 405
    assert response.headers["X-CatScan-Shadow"] == "read-only"
    assert "disabled" in response.json()["detail"]


def test_normal_mode_does_not_block_mutations(monkeypatch) -> None:
    client = _client(monkeypatch, enabled=False)

    response = client.post("/write")

    assert response.status_code == 200
    assert response.json() == {"mutated": True}
    assert "X-CatScan-Shadow" not in response.headers


def test_store_can_initialize_without_running_migrations(monkeypatch) -> None:
    async def unexpected_migration() -> None:
        raise AssertionError("migration should not run")

    monkeypatch.setattr(
        "storage.postgres_store.init_postgres_database",
        unexpected_migration,
    )
    store = PostgresStore()

    asyncio.run(store.initialize(run_migrations=False))

    assert store._initialized is True
