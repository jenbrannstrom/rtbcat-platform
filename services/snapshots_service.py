"""Business logic for pretargeting snapshots and comparisons."""

from __future__ import annotations

import json
from typing import Any

from storage.postgres_repositories.comparisons_repo import ComparisonsRepository
from storage.postgres_repositories.performance_repo import PerformanceRepository
from storage.postgres_repositories.pretargeting_repo import PretargetingRepository
from storage.postgres_repositories.snapshots_repo import SnapshotsRepository


class SnapshotsService:
    """Service layer for snapshot and comparison workflows."""

    def __init__(
        self,
        snapshots_repo: SnapshotsRepository | None = None,
        pretargeting_repo: PretargetingRepository | None = None,
        performance_repo: PerformanceRepository | None = None,
        comparisons_repo: ComparisonsRepository | None = None,
    ) -> None:
        self._snapshots = snapshots_repo or SnapshotsRepository()
        self._pretargeting = pretargeting_repo or PretargetingRepository()
        self._performance = performance_repo or PerformanceRepository()
        self._comparisons = comparisons_repo or ComparisonsRepository()

    async def create_snapshot(
        self,
        billing_id: str,
        snapshot_name: str | None,
        snapshot_type: str | None,
        notes: str | None,
    ) -> dict[str, Any]:
        if not billing_id:
            raise ValueError("billing_id is required")

        config = await self._pretargeting.get_config_by_billing_id(billing_id)
        if not config:
            raise ValueError(f"Config not found for billing_id: {billing_id}")

        perf = await self._performance.get_performance_aggregates(billing_id)
        days = perf.get("days_tracked", 0) or 0
        imps = perf.get("total_impressions", 0) or 0
        clicks = perf.get("total_clicks", 0) or 0
        spend = perf.get("total_spend_usd", 0) or 0

        avg_daily_imps = imps / days if days > 0 else None
        avg_daily_spend = spend / days if days > 0 else None
        ctr = (clicks / imps * 100) if imps > 0 else None
        cpm = (spend / imps * 1000) if imps > 0 else None

        raw_config = json.loads(config["raw_config"]) if config.get("raw_config") else {}
        publisher_targeting = raw_config.get("publisherTargeting") or {}
        publisher_mode = publisher_targeting.get("targetingMode")
        publisher_values = publisher_targeting.get("values") or []

        config_data = {
            "included_formats": config.get("included_formats"),
            "included_platforms": config.get("included_platforms"),
            "included_sizes": config.get("included_sizes"),
            "included_geos": config.get("included_geos"),
            "excluded_geos": config.get("excluded_geos"),
            "state": config.get("state"),
        }
        performance_data = {
            "total_impressions": imps,
            "total_clicks": clicks,
            "total_spend_usd": spend,
            "days_tracked": days,
            "avg_daily_impressions": avg_daily_imps,
            "avg_daily_spend_usd": avg_daily_spend,
            "ctr_pct": ctr,
            "cpm_usd": cpm,
        }

        snapshot_id = await self._snapshots.create_snapshot(
            billing_id=billing_id,
            snapshot_name=snapshot_name,
            snapshot_type=snapshot_type or "manual",
            config_data=config_data,
            performance_data=performance_data,
            publisher_targeting_mode=publisher_mode,
            publisher_targeting_values=json.dumps(publisher_values) if publisher_values else None,
            notes=notes,
        )

        snapshot = await self._snapshots.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError("Failed to create snapshot")
        return snapshot

    async def list_snapshots(
        self,
        billing_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self._snapshots.list_snapshots(
            billing_id=billing_id,
            limit=limit,
        )

    async def create_comparison(
        self,
        billing_id: str,
        comparison_name: str | None,
        before_snapshot_id: int,
        before_start_date: str | None,
        before_end_date: str | None,
    ) -> dict[str, Any]:
        if not billing_id:
            raise ValueError("billing_id is required")
        if before_snapshot_id <= 0:
            raise ValueError("before_snapshot_id must be positive")

        before_snapshot = await self._snapshots.get_snapshot(before_snapshot_id)
        if not before_snapshot:
            raise ValueError("Before snapshot not found")

        comparison_id = await self._comparisons.create_comparison(
            billing_id=billing_id,
            comparison_name=comparison_name,
            before_snapshot_id=before_snapshot_id,
            before_start_date=before_start_date,
            before_end_date=before_end_date,
        )
        comparison = await self._comparisons.get_comparison(comparison_id)
        if not comparison:
            raise ValueError("Failed to create comparison")
        return comparison

    async def list_comparisons(
        self,
        billing_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self._comparisons.list_comparisons(
            billing_id=billing_id,
            status=status,
            limit=limit,
        )
