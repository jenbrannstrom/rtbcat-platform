"""Repository tests for JSONB adaptation in pretargeting history writes."""

from __future__ import annotations

import pytest
from psycopg.types.json import Jsonb

from storage.postgres_repositories.pretargeting_repo import PretargetingRepository


async def _fake_pg_insert_returning_id(_sql: str, params: tuple):
    _fake_pg_insert_returning_id.last_params = params
    return 99


@pytest.mark.asyncio
async def test_add_history_wraps_raw_config_snapshot_as_jsonb(monkeypatch):
    monkeypatch.setattr(
        "storage.postgres_repositories.pretargeting_repo.pg_insert_returning_id",
        _fake_pg_insert_returning_id,
    )

    repo = PretargetingRepository()
    history_id = await repo.add_history(
        config_id="cfg-1",
        bidder_id="bidder-1",
        change_type="major_commit",
        field_changed="batch",
        old_value=None,
        new_value="targeting:1/1",
        changed_by="system",
        change_source="api",
        raw_config_snapshot={"changes": [{"change_type": "add_format", "value": "HTML"}]},
    )

    assert history_id == 99
    params = _fake_pg_insert_returning_id.last_params
    assert isinstance(params[8], Jsonb)
    assert params[8].obj == {"changes": [{"change_type": "add_format", "value": "HTML"}]}
