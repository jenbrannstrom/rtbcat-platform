"""Service layer for precompute health checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from storage.postgres_repositories.precompute_repo import PrecomputeRepository

logger = logging.getLogger(__name__)


@dataclass
class CacheHealth:
    """Health status for a precompute cache."""

    cache_name: str
    refreshed_at: Optional[str]
    is_stale: bool
    is_missing: bool


@dataclass
class PrecomputeHealthStatus:
    """Overall precompute health status."""

    ok: bool
    max_age_hours: int
    checked_at: str
    stale_caches: list[str]
    missing_caches: list[str]
    cache_refresh_times: dict[str, str]
    latest_source_metric_date: Optional[str]
    serving_metric_dates: dict[str, Optional[str]]
    serving_lag_days: dict[str, Optional[int]]
    max_date_drift_days: Optional[int]
    date_parity_ok: bool


def _parse_metric_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


class PrecomputeService:
    """Orchestrates precompute health checks."""

    REQUIRED_CACHES = ["home_summaries", "config_breakdowns", "rtb_summaries"]
    RAW_FACT_TABLE = "rtb_daily"
    # Tuple format: (legacy_name, canonical_name).
    # Health output remains keyed by legacy names for compatibility while reads
    # prefer canonical aliases when available.
    SERVING_TABLE_ALIASES: list[tuple[str, str]] = [
        ("home_seat_daily", "seat_daily"),
        ("home_geo_daily", "seat_geo_daily"),
        ("config_size_daily", "pretarg_size_daily"),
        ("config_geo_daily", "pretarg_geo_daily"),
        ("config_publisher_daily", "pretarg_publisher_daily"),
        ("config_creative_daily", "pretarg_creative_daily"),
    ]

    def __init__(self, repo: PrecomputeRepository | None = None) -> None:
        self._repo = repo or PrecomputeRepository()

    async def get_health_status(self, max_age_hours: int) -> PrecomputeHealthStatus:
        """Check health of all precompute caches.

        Args:
            max_age_hours: Maximum acceptable age for cache data.

        Returns:
            PrecomputeHealthStatus with detailed cache status.
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        try:
            rows = await self._repo.get_cache_refresh_times()
        except Exception as e:
            logger.error(f"Failed to fetch cache refresh times: {e}")
            rows = []

        refresh_map = {
            row["cache_name"]: row["refreshed_at"]
            for row in rows
            if row.get("refreshed_at")
        }

        stale_caches: list[str] = []
        missing_caches: list[str] = []
        cache_refresh_times: dict[str, str] = {}

        for cache_name in self.REQUIRED_CACHES:
            refreshed_at = refresh_map.get(cache_name)
            if not refreshed_at:
                missing_caches.append(cache_name)
                continue

            try:
                refreshed_dt = datetime.fromisoformat(refreshed_at)
            except ValueError:
                missing_caches.append(cache_name)
                continue

            cache_refresh_times[cache_name] = refreshed_at
            if refreshed_dt < cutoff:
                stale_caches.append(cache_name)

        latest_source_metric_date: Optional[str] = None
        serving_metric_dates: dict[str, Optional[str]] = {}
        serving_lag_days: dict[str, Optional[int]] = {}
        max_date_drift_days: Optional[int] = None
        date_parity_ok = True

        try:
            lookup_tables = [self.RAW_FACT_TABLE]
            for legacy_name, canonical_name in self.SERVING_TABLE_ALIASES:
                lookup_tables.append(canonical_name)
                if canonical_name != legacy_name:
                    lookup_tables.append(legacy_name)

            table_dates = await self._repo.get_latest_metric_dates(
                lookup_tables
            )
            latest_source_metric_date = table_dates.get(self.RAW_FACT_TABLE)
            source_metric_date = _parse_metric_date(latest_source_metric_date)

            if source_metric_date is None:
                date_parity_ok = False

            for legacy_name, canonical_name in self.SERVING_TABLE_ALIASES:
                canonical_metric_iso = table_dates.get(canonical_name)
                legacy_metric_iso = table_dates.get(legacy_name)
                table_metric_iso = canonical_metric_iso or legacy_metric_iso
                serving_metric_dates[legacy_name] = table_metric_iso
                table_metric_date = _parse_metric_date(table_metric_iso)

                if source_metric_date is None or table_metric_date is None:
                    serving_lag_days[legacy_name] = None
                    date_parity_ok = False
                    continue

                lag_days = abs((source_metric_date - table_metric_date).days)
                serving_lag_days[legacy_name] = lag_days
                max_date_drift_days = (
                    lag_days
                    if max_date_drift_days is None
                    else max(max_date_drift_days, lag_days)
                )
                if lag_days > 1:
                    date_parity_ok = False
        except Exception as e:
            logger.error(f"Failed to compute precompute date parity: {e}")
            date_parity_ok = False

        ok = not stale_caches and not missing_caches and date_parity_ok

        if not ok:
            logger.warning(
                "Precompute health check failed: stale=%s missing=%s parity_ok=%s max_drift=%s",
                stale_caches,
                missing_caches,
                date_parity_ok,
                max_date_drift_days,
            )

        return PrecomputeHealthStatus(
            ok=ok,
            max_age_hours=max_age_hours,
            checked_at=datetime.utcnow().isoformat(),
            stale_caches=stale_caches,
            missing_caches=missing_caches,
            cache_refresh_times=cache_refresh_times,
            latest_source_metric_date=latest_source_metric_date,
            serving_metric_dates=serving_metric_dates,
            serving_lag_days=serving_lag_days,
            max_date_drift_days=max_date_drift_days,
            date_parity_ok=date_parity_ok,
        )
