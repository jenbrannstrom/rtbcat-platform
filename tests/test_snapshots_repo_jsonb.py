"""Repository tests for JSONB parameter adaptation in snapshot writes."""

from __future__ import annotations

import pytest
from psycopg.types.json import Jsonb

from storage.postgres_repositories.snapshots_repo import SnapshotsRepository


async def _fake_pg_query_one(_sql: str, params: tuple):
    _fake_pg_query_one.last_params = params
    return {"id": 42}


@pytest.mark.asyncio
async def test_create_snapshot_wraps_list_fields_as_jsonb(monkeypatch):
    monkeypatch.setattr(
        "storage.postgres_repositories.snapshots_repo.pg_query_one",
        _fake_pg_query_one,
    )

    repo = SnapshotsRepository()
    snapshot_id = await repo.create_snapshot(
        billing_id="billing-1",
        snapshot_name="Before change",
        snapshot_type="before_change",
        config_data={
            "included_formats": ["HTML", "VIDEO"],
            "included_platforms": ["PHONE"],
            "included_sizes": ["300x250"],
            "included_geos": ["US"],
            "excluded_geos": [],
            "state": "ACTIVE",
        },
        performance_data={},
        publisher_targeting_mode="EXCLUSIVE",
        publisher_targeting_values=["123"],
        notes=None,
    )

    assert snapshot_id == 42
    params = _fake_pg_query_one.last_params
    assert isinstance(params[3], Jsonb)
    assert params[3].obj == ["HTML", "VIDEO"]
    assert isinstance(params[4], Jsonb)
    assert params[4].obj == ["PHONE"]
    assert isinstance(params[5], Jsonb)
    assert params[5].obj == ["300x250"]
    assert isinstance(params[6], Jsonb)
    assert params[6].obj == ["US"]
    assert isinstance(params[7], Jsonb)
    assert params[7].obj == []
    assert isinstance(params[10], Jsonb)
    assert params[10].obj == ["123"]


@pytest.mark.asyncio
async def test_create_snapshot_normalizes_legacy_string_lists(monkeypatch):
    monkeypatch.setattr(
        "storage.postgres_repositories.snapshots_repo.pg_query_one",
        _fake_pg_query_one,
    )

    repo = SnapshotsRepository()
    await repo.create_snapshot(
        billing_id="billing-1",
        snapshot_name="Legacy",
        snapshot_type="manual",
        config_data={
            "included_formats": "{HTML,VIDEO}",
            "included_platforms": '["PHONE"]',
            "included_sizes": "{300x250,320x50}",
            "included_geos": "{US,CA}",
            "excluded_geos": "{}",
            "state": "ACTIVE",
        },
        performance_data={},
        publisher_targeting_mode="EXCLUSIVE",
        publisher_targeting_values="{123,456}",
        notes=None,
    )

    params = _fake_pg_query_one.last_params
    assert params[3].obj == ["HTML", "VIDEO"]
    assert params[4].obj == ["PHONE"]
    assert params[5].obj == ["300x250", "320x50"]
    assert params[6].obj == ["US", "CA"]
    assert params[7].obj == []
    assert params[10].obj == ["123", "456"]
