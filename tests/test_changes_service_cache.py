"""Cache behavior tests for ChangesService list_pending_changes path."""

from __future__ import annotations

import pytest

from services.changes_service import ChangesService


class _StubChangesRepo:
    def __init__(self) -> None:
        self.list_calls = 0
        self.create_calls = 0
        self.cancel_calls = 0
        self.cancel_for_billing_calls = 0
        self.mark_applied_calls = 0
        self.rows: list[dict[str, object]] = [
            {"id": 1, "billing_id": "billing-1", "status": "pending"}
        ]

    async def create_pending_change(
        self,
        config_id: int,
        billing_id: str,
        change_type: str,
        field_name: str,
        value: str,
        reason: str | None,
        estimated_qps_impact: float | None,
        created_by: str | None,
    ) -> int:
        self.create_calls += 1
        return 42

    async def list_pending_changes(
        self,
        billing_id: str | None,
        status: str,
        limit: int,
    ) -> list[dict[str, object]]:
        self.list_calls += 1
        rows = [row for row in self.rows if row["status"] == status]
        if billing_id:
            rows = [row for row in rows if row["billing_id"] == billing_id]
        return [dict(row) for row in rows[:limit]]

    async def get_pending_change(self, change_id: int) -> dict[str, object] | None:
        return {"id": change_id}

    async def cancel_pending_change(self, change_id: int) -> int:
        self.cancel_calls += 1
        return 1

    async def cancel_pending_changes_for_billing(self, billing_id: str) -> int:
        _ = billing_id
        self.cancel_for_billing_calls += 1
        return 1

    async def mark_pending_change_applied(
        self,
        change_id: int,
        applied_by: str | None,
    ) -> int:
        self.mark_applied_calls += 1
        return 1


@pytest.mark.asyncio
async def test_list_pending_changes_uses_ttl_cache() -> None:
    ChangesService.clear_list_pending_changes_cache()
    repo = _StubChangesRepo()
    service = ChangesService(repo=repo)

    first = await service.list_pending_changes(
        billing_id="billing-1",
        status="pending",
        limit=100,
    )
    first[0]["status"] = "mutated-locally"
    second = await service.list_pending_changes(
        billing_id="billing-1",
        status="pending",
        limit=100,
    )

    assert repo.list_calls == 1
    assert second[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_create_pending_change_invalidates_list_cache() -> None:
    ChangesService.clear_list_pending_changes_cache()
    repo = _StubChangesRepo()
    service = ChangesService(repo=repo)

    await service.list_pending_changes(billing_id="billing-1", status="pending", limit=100)
    assert repo.list_calls == 1

    repo.rows = [{"id": 2, "billing_id": "billing-1", "status": "pending"}]
    await service.create_pending_change(
        config_id=1,
        billing_id="billing-1",
        change_type="add_geo",
        field_name="geo",
        value="US",
        reason=None,
        estimated_qps_impact=None,
        created_by="ui",
    )
    refreshed = await service.list_pending_changes(
        billing_id="billing-1",
        status="pending",
        limit=100,
    )

    assert repo.create_calls == 1
    assert repo.list_calls == 2
    assert refreshed[0]["id"] == 2


@pytest.mark.asyncio
async def test_cancel_or_mark_applied_invalidates_list_cache() -> None:
    ChangesService.clear_list_pending_changes_cache()
    repo = _StubChangesRepo()
    service = ChangesService(repo=repo)

    await service.list_pending_changes(billing_id="billing-1", status="pending", limit=100)
    assert repo.list_calls == 1

    await service.cancel_pending_change(1)
    await service.list_pending_changes(billing_id="billing-1", status="pending", limit=100)
    assert repo.cancel_calls == 1
    assert repo.list_calls == 2

    await service.mark_pending_change_applied(1, applied_by="user-1")
    await service.list_pending_changes(billing_id="billing-1", status="pending", limit=100)
    assert repo.mark_applied_calls == 1
    assert repo.list_calls == 3


@pytest.mark.asyncio
async def test_cancel_pending_changes_for_billing_invalidates_list_cache() -> None:
    ChangesService.clear_list_pending_changes_cache()
    repo = _StubChangesRepo()
    service = ChangesService(repo=repo)

    await service.list_pending_changes(billing_id="billing-1", status="pending", limit=100)
    assert repo.list_calls == 1

    repo.rows = []
    await service.cancel_pending_changes_for_billing("billing-1")
    refreshed = await service.list_pending_changes(
        billing_id="billing-1",
        status="pending",
        limit=100,
    )

    assert repo.cancel_for_billing_calls == 1
    assert repo.list_calls == 2
    assert refreshed == []
