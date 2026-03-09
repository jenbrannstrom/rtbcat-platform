"""Cache behavior tests for SnapshotsService list paths."""

from __future__ import annotations

import pytest

from services.snapshots_service import SnapshotsService


class _StubSnapshotsRepo:
    def __init__(self) -> None:
        self.list_calls = 0
        self.create_calls = 0
        self.last_create_payload: dict[str, object] | None = None
        self.rows: list[dict[str, object]] = [
            {
                "id": 1,
                "billing_id": "billing-1",
                "snapshot_name": "Baseline",
                "snapshot_type": "manual",
                "state": "ACTIVE",
            }
        ]

    async def list_snapshots(
        self,
        billing_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        self.list_calls += 1
        rows = self.rows
        if billing_id:
            rows = [row for row in rows if row["billing_id"] == billing_id]
        return [dict(row) for row in rows[:limit]]

    async def create_snapshot(
        self,
        billing_id: str,
        snapshot_name: str | None,
        snapshot_type: str,
        config_data: dict[str, object],
        performance_data: dict[str, object],
        publisher_targeting_mode: str | None,
        publisher_targeting_values: list[str] | None,
        notes: str | None,
    ) -> int:
        self.create_calls += 1
        self.last_create_payload = {
            "billing_id": billing_id,
            "snapshot_name": snapshot_name,
            "snapshot_type": snapshot_type,
            "config_data": dict(config_data),
            "performance_data": dict(performance_data),
            "publisher_targeting_mode": publisher_targeting_mode,
            "publisher_targeting_values": list(publisher_targeting_values or []),
            "notes": notes,
        }
        snapshot_id = len(self.rows) + 1
        self.rows.insert(
            0,
            {
                "id": snapshot_id,
                "billing_id": billing_id,
                "snapshot_name": snapshot_name or "Auto",
                "snapshot_type": snapshot_type,
                "state": "ACTIVE",
            },
        )
        return snapshot_id

    async def get_snapshot(self, snapshot_id: int) -> dict[str, object] | None:
        for row in self.rows:
            if int(row["id"]) == snapshot_id:
                return dict(row)
        return None


class _StubPretargetingRepo:
    async def get_config_by_billing_id(self, billing_id: str) -> dict[str, object] | None:
        if billing_id != "billing-1":
            return None
        return {
            "included_formats": [],
            "included_platforms": [],
            "included_sizes": [],
            "included_geos": [],
            "excluded_geos": [],
            "state": "ACTIVE",
            "raw_config": {},
        }


class _StubPerformanceRepo:
    async def get_performance_aggregates(self, billing_id: str) -> dict[str, object]:
        return {
            "days_tracked": 1,
            "total_impressions": 10,
            "total_clicks": 1,
            "total_spend_usd": 1.2,
        }


class _StubComparisonsRepo:
    def __init__(self) -> None:
        self.list_calls = 0
        self.create_calls = 0
        self.rows: list[dict[str, object]] = [
            {
                "id": 1,
                "billing_id": "billing-1",
                "status": "in_progress",
            }
        ]

    async def create_comparison(
        self,
        billing_id: str,
        comparison_name: str | None,
        before_snapshot_id: int,
        before_start_date: str | None,
        before_end_date: str | None,
    ) -> int:
        self.create_calls += 1
        comparison_id = len(self.rows) + 1
        self.rows.insert(
            0,
            {
                "id": comparison_id,
                "billing_id": billing_id,
                "status": "in_progress",
            },
        )
        return comparison_id

    async def get_comparison(self, comparison_id: int) -> dict[str, object] | None:
        for row in self.rows:
            if int(row["id"]) == comparison_id:
                return dict(row)
        return None

    async def list_comparisons(
        self,
        billing_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        self.list_calls += 1
        rows = self.rows
        if billing_id:
            rows = [row for row in rows if row["billing_id"] == billing_id]
        if status:
            rows = [row for row in rows if row["status"] == status]
        return [dict(row) for row in rows[:limit]]


def _service() -> tuple[SnapshotsService, _StubSnapshotsRepo, _StubComparisonsRepo]:
    snapshots_repo = _StubSnapshotsRepo()
    comparisons_repo = _StubComparisonsRepo()
    service = SnapshotsService(
        snapshots_repo=snapshots_repo,
        pretargeting_repo=_StubPretargetingRepo(),
        performance_repo=_StubPerformanceRepo(),
        comparisons_repo=comparisons_repo,
    )
    return service, snapshots_repo, comparisons_repo


@pytest.mark.asyncio
async def test_list_snapshots_uses_ttl_cache() -> None:
    SnapshotsService.clear_caches()
    service, snapshots_repo, _ = _service()

    first = await service.list_snapshots(billing_id="billing-1", limit=10)
    first[0]["snapshot_name"] = "mutated-locally"
    second = await service.list_snapshots(billing_id="billing-1", limit=10)

    assert snapshots_repo.list_calls == 1
    assert second[0]["snapshot_name"] == "Baseline"


@pytest.mark.asyncio
async def test_create_snapshot_invalidates_snapshot_list_cache() -> None:
    SnapshotsService.clear_caches()
    service, snapshots_repo, _ = _service()

    await service.list_snapshots(billing_id="billing-1", limit=10)
    assert snapshots_repo.list_calls == 1

    await service.create_snapshot(
        billing_id="billing-1",
        snapshot_name="After tweak",
        snapshot_type="manual",
        notes=None,
    )
    await service.list_snapshots(billing_id="billing-1", limit=10)

    assert snapshots_repo.create_calls == 1
    assert snapshots_repo.list_calls == 2


class _LegacyPretargetingRepo:
    async def get_config_by_billing_id(self, billing_id: str) -> dict[str, object] | None:
        if billing_id != "billing-1":
            return None
        return {
            "included_formats": "{HTML,VIDEO}",
            "included_platforms": '["PHONE"]',
            "included_sizes": "{300x250,320x50}",
            "included_geos": "{US,CA}",
            "excluded_geos": "{}",
            "state": "ACTIVE",
            "raw_config": '{"publisherTargeting":{"targetingMode":"EXCLUSIVE","values":"{123,456}"}}',
        }


@pytest.mark.asyncio
async def test_create_snapshot_normalizes_legacy_list_payloads() -> None:
    SnapshotsService.clear_caches()
    snapshots_repo = _StubSnapshotsRepo()
    service = SnapshotsService(
        snapshots_repo=snapshots_repo,
        pretargeting_repo=_LegacyPretargetingRepo(),
        performance_repo=_StubPerformanceRepo(),
        comparisons_repo=_StubComparisonsRepo(),
    )

    await service.create_snapshot(
        billing_id="billing-1",
        snapshot_name="Legacy snapshot",
        snapshot_type="manual",
        notes=None,
    )

    assert snapshots_repo.last_create_payload is not None
    config_data = snapshots_repo.last_create_payload["config_data"]
    assert config_data["included_formats"] == ["HTML", "VIDEO"]
    assert config_data["included_platforms"] == ["PHONE"]
    assert config_data["included_sizes"] == ["300x250", "320x50"]
    assert config_data["included_geos"] == ["US", "CA"]
    assert config_data["excluded_geos"] == []
    assert snapshots_repo.last_create_payload["publisher_targeting_values"] == ["123", "456"]


@pytest.mark.asyncio
async def test_list_comparisons_uses_ttl_cache() -> None:
    SnapshotsService.clear_caches()
    service, _, comparisons_repo = _service()

    first = await service.list_comparisons(
        billing_id="billing-1",
        status="in_progress",
        limit=10,
    )
    first[0]["status"] = "mutated-locally"
    second = await service.list_comparisons(
        billing_id="billing-1",
        status="in_progress",
        limit=10,
    )

    assert comparisons_repo.list_calls == 1
    assert second[0]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_create_comparison_invalidates_comparison_list_cache() -> None:
    SnapshotsService.clear_caches()
    service, _, comparisons_repo = _service()

    await service.list_comparisons(billing_id="billing-1", status="in_progress", limit=10)
    assert comparisons_repo.list_calls == 1

    await service.create_comparison(
        billing_id="billing-1",
        comparison_name="Compare",
        before_snapshot_id=1,
        before_start_date=None,
        before_end_date=None,
    )
    await service.list_comparisons(billing_id="billing-1", status="in_progress", limit=10)

    assert comparisons_repo.create_calls == 1
    assert comparisons_repo.list_calls == 2
