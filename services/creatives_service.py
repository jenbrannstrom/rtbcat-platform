"""Business logic for creative list orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from services.creative_performance_service import CreativePerformanceService
from services.creative_preview_service import CreativePreviewService
from storage.postgres_repositories.creatives_repo import CreativesRepository


@dataclass
class ThumbnailStatus:
    """Thumbnail generation status for a creative."""

    status: Optional[str] = None  # 'success', 'failed', or None
    error_reason: Optional[str] = None
    has_thumbnail: bool = False
    thumbnail_url: Optional[str] = None


@dataclass
class WasteFlags:
    """Waste detection flags for a creative."""

    broken_video: bool = False
    zero_engagement: bool = False


@dataclass
class CreativeListContext:
    """Aggregated context data for creative list responses."""

    thumbnail_statuses: dict[str, ThumbnailStatus]
    waste_flags: dict[str, WasteFlags]
    country_data: dict[str, str]


@dataclass
class NewlyUploadedCreativesResult:
    """Result for newly uploaded creatives query."""

    creatives: list[dict[str, Any]]
    total_count: int
    period_start: datetime
    period_end: datetime


class CreativesService:
    """Service layer for creative list orchestration."""

    def __init__(
        self,
        performance_service: CreativePerformanceService | None = None,
        preview_service: CreativePreviewService | None = None,
        creatives_repo: CreativesRepository | None = None,
    ) -> None:
        self._perf = performance_service or CreativePerformanceService()
        self._preview = preview_service or CreativePreviewService()
        self._repo = creatives_repo or CreativesRepository()
        self._thumbnails_dir = Path.home() / ".catscan" / "thumbnails"

    async def filter_active_creatives(
        self,
        creatives: list[Any],
        days: int,
        limit: int,
    ) -> list[Any]:
        """Filter creatives to only those with activity in timeframe."""
        if not creatives:
            return []

        creative_ids = [c.id for c in creatives]
        active_ids = await self._perf.get_active_creative_ids(creative_ids, days)

        if active_ids:
            return [c for c in creatives if c.id in active_ids][:limit]
        return []

    async def get_thumbnail_statuses(
        self,
        store: Any,
        creative_ids: list[str],
    ) -> dict[str, ThumbnailStatus]:
        """Get thumbnail status for multiple creatives."""
        if not creative_ids:
            return {}

        statuses = await store.get_thumbnail_statuses(creative_ids)

        result = {}
        for cid in creative_ids:
            status_data = statuses.get(cid)
            has_thumbnail = (self._thumbnails_dir / f"{cid}.jpg").exists()

            # Prefer the local file URL when the thumbnail exists on disk,
            # regardless of which DB table recorded the generation.
            # Use /api/ prefix so nginx routes to the API container in production.
            thumb_url = (
                f"/api/thumbnails/{cid}.jpg"
                if has_thumbnail
                else (status_data.get("thumbnail_url") if status_data else None)
            )

            if status_data:
                result[cid] = ThumbnailStatus(
                    status=status_data["status"],
                    error_reason=status_data["error_reason"],
                    has_thumbnail=has_thumbnail,
                    thumbnail_url=thumb_url,
                )
            else:
                result[cid] = ThumbnailStatus(
                    status=None,
                    error_reason=None,
                    has_thumbnail=has_thumbnail,
                    thumbnail_url=thumb_url,
                )

        return result

    async def get_waste_flags(
        self,
        creative_ids: list[str],
        thumbnail_statuses: dict[str, ThumbnailStatus],
        days: int = 7,
    ) -> dict[str, WasteFlags]:
        """Compute waste flags for multiple creatives."""
        status_map = {
            cid: {"status": ts.status} for cid, ts in thumbnail_statuses.items()
        }
        flags = await self._perf.get_waste_flags(creative_ids, status_map, days)
        return {
            cid: WasteFlags(
                broken_video=data["broken_video"],
                zero_engagement=data["zero_engagement"],
            )
            for cid, data in flags.items()
        }

    async def get_primary_countries(
        self,
        creative_ids: list[str],
        days: int = 7,
    ) -> dict[str, str]:
        """Get the primary country (by spend) for each creative."""
        return await self._perf.get_primary_countries(creative_ids, days)

    async def get_list_context(
        self,
        store: Any,
        creative_ids: list[str],
        days: int = 7,
    ) -> CreativeListContext:
        """Get all context data needed for creative list responses.

        Aggregates thumbnail status, waste flags, and country data in one call.
        """
        thumbnail_statuses = await self.get_thumbnail_statuses(store, creative_ids)
        waste_flags = await self.get_waste_flags(creative_ids, thumbnail_statuses, days)
        country_data = await self.get_primary_countries(creative_ids, days)

        return CreativeListContext(
            thumbnail_statuses=thumbnail_statuses,
            waste_flags=waste_flags,
            country_data=country_data,
        )

    def build_preview(
        self,
        creative: Any,
        slim: bool = True,
        html_thumbnail_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build preview data for a creative."""
        return self._preview.build_preview(
            creative,
            slim=slim,
            html_thumbnail_url=html_thumbnail_url,
        )

    async def get_newly_uploaded_creatives(
        self,
        days: int,
        limit: int,
        creative_format: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> NewlyUploadedCreativesResult:
        """Get creatives first seen within the specified time period."""
        period_end = datetime.now()
        period_start = period_end - timedelta(days=days)

        rows = await self._repo.get_newly_uploaded_creatives(
            period_start=period_start,
            period_end=period_end,
            limit=limit,
            creative_format=creative_format,
            buyer_id=buyer_id,
        )
        total_count = await self._repo.get_newly_uploaded_creatives_count(
            period_start=period_start,
            period_end=period_end,
            creative_format=creative_format,
            buyer_id=buyer_id,
        )

        creatives: list[dict[str, Any]] = []
        for row in rows:
            creatives.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "format": row["format"],
                    "approval_status": row["approval_status"],
                    "width": row["width"],
                    "height": row["height"],
                    "canonical_size": row["canonical_size"],
                    "final_url": row["final_url"],
                    "first_seen_at": row["first_seen_at"],
                    "first_import_batch_id": row["first_import_batch_id"],
                    "total_spend_usd": (row["total_spend_micros"] or 0) / 1_000_000,
                    "total_impressions": row["total_impressions"] or 0,
                }
            )

        return NewlyUploadedCreativesResult(
            creatives=creatives,
            total_count=total_count,
            period_start=period_start,
            period_end=period_end,
        )
