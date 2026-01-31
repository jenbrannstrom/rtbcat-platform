"""Business logic for performance metrics import and aggregation."""

from __future__ import annotations

from typing import Any, Optional

from storage.postgres_repositories.performance_repo import PerformanceRepository
from storage.postgres_repositories.uploads_repo import UploadsRepository


class PerformanceService:
    """Service layer for performance metrics operations."""

    def __init__(
        self,
        performance_repo: PerformanceRepository | None = None,
        uploads_repo: UploadsRepository | None = None,
    ) -> None:
        self._perf = performance_repo or PerformanceRepository()
        self._uploads = uploads_repo or UploadsRepository()

    async def upsert_metric(
        self,
        creative_id: str,
        metric_date: str,
        impressions: int,
        clicks: int,
        spend_micros: int,
        reached_queries: int = 0,
        campaign_id: Optional[str] = None,
        geography: Optional[str] = None,
        device_type: Optional[str] = None,
        placement: Optional[str] = None,
    ) -> None:
        """Upsert a single performance metric."""
        await self._perf.upsert_performance_metric(
            creative_id=creative_id,
            metric_date=metric_date,
            impressions=impressions,
            clicks=clicks,
            spend_micros=spend_micros,
            reached_queries=reached_queries,
            campaign_id=campaign_id,
            geography=geography,
            device_type=device_type,
            placement=placement,
        )

    async def get_aggregates_for_billing_id(self, billing_id: str) -> dict[str, Any]:
        """Get performance aggregates for a billing ID."""
        return await self._perf.get_performance_aggregates(billing_id)

    async def record_import(
        self,
        batch_id: str,
        filename: Optional[str],
        rows_read: int,
        rows_imported: int,
        rows_skipped: int,
        rows_duplicate: int,
        date_range_start: Optional[str],
        date_range_end: Optional[str],
        columns_found: list[str],
        status: str,
        error_message: Optional[str],
        file_size_bytes: int,
    ) -> None:
        """Record an import in history and update daily summary."""
        columns_str = ",".join(columns_found) if columns_found else None

        await self._uploads.record_import_history(
            batch_id=batch_id,
            filename=filename,
            rows_read=rows_read,
            rows_imported=rows_imported,
            rows_skipped=rows_skipped,
            rows_duplicate=rows_duplicate,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            columns_found=columns_str,
            columns_missing=None,
            total_reached=0,
            total_impressions=0,
            total_spend_usd=0,
            status=status,
            error_message=error_message,
            file_size_bytes=file_size_bytes,
        )

    async def finalize_import(
        self,
        batch_id: str,
        filename: Optional[str],
        rows_read: int,
        rows_imported: int,
        rows_skipped: int,
        rows_duplicate: int,
        date_range_start: Optional[str],
        date_range_end: Optional[str],
        total_reached: int,
        total_impressions: int,
        total_spend_usd: float,
        file_size_bytes: int,
    ) -> None:
        """Finalize a chunked import - record history and update daily summary."""
        await self._uploads.record_import_history(
            batch_id=batch_id,
            filename=filename,
            rows_read=rows_read,
            rows_imported=rows_imported,
            rows_skipped=rows_skipped,
            rows_duplicate=rows_duplicate,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            columns_found=None,
            columns_missing=None,
            total_reached=total_reached,
            total_impressions=total_impressions,
            total_spend_usd=total_spend_usd,
            status="complete",
            error_message=None,
            file_size_bytes=file_size_bytes,
        )

        # Update daily summary
        upload_date = await self._uploads.get_current_date()
        if upload_date:
            await self._uploads.update_daily_upload_summary(
                upload_date=upload_date,
                rows_imported=rows_imported,
                file_size_bytes=file_size_bytes,
                success=True,
            )

    async def get_creative_buyer_ids(
        self, creative_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Get creative IDs and their buyer_ids for access validation."""
        return await self._perf.get_creative_buyer_ids(creative_ids)

    @staticmethod
    def parse_spend(spend_value: Any) -> tuple[int, float]:
        """Parse spend value into micros and USD. Returns (spend_micros, spend_usd)."""
        if not spend_value:
            return 0, 0.0

        if isinstance(spend_value, str):
            spend = float(spend_value.replace("$", "").replace(",", ""))
        else:
            spend = float(spend_value)

        spend_micros = int(spend * 1_000_000)
        return spend_micros, spend
