"""Data reliability health checks for source and serving layers."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from storage.postgres_database import pg_query_one


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


class DataHealthService:
    """Computes non-sensitive reliability and freshness status."""

    async def get_data_health(self, days: int = 7, buyer_id: Optional[str] = None) -> dict[str, Any]:
        source = await self._get_source_freshness(days=days, buyer_id=buyer_id)
        serving = await self._get_serving_freshness(days=days, buyer_id=buyer_id)
        coverage = await self._get_dimension_coverage(days=days, buyer_id=buyer_id)
        ingestion = await self._get_ingestion_summary(days=days, buyer_id=buyer_id)

        state = self._compute_state(source=source, serving=serving, coverage=coverage)
        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "days": days,
            "buyer_id": buyer_id,
            "state": state,
            "source_freshness": source,
            "serving_freshness": serving,
            "coverage": coverage,
            "ingestion_runs": ingestion,
        }

    async def _get_source_freshness(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        buyer_filter = ""
        params: list[Any] = []
        if buyer_id:
            buyer_filter = " AND buyer_id = %s"
            params.append(buyer_id)

        row_daily = await pg_query_one(
            f"""
            SELECT MAX(metric_date) AS max_metric_date, COUNT(*) AS rows
            FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        row_geo = await pg_query_one(
            f"""
            SELECT MAX(metric_date) AS max_metric_date, COUNT(*) AS rows
            FROM rtb_geo_daily
            WHERE metric_date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        return {
            "rtb_daily": {
                "rows": int((row_daily or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_daily or {}).get("max_metric_date")),
            },
            "rtb_geo_daily": {
                "rows": int((row_geo or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_geo or {}).get("max_metric_date")),
            },
        }

    async def _get_serving_freshness(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        buyer_filter = ""
        params: list[Any] = []
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)

        row_home_geo = await pg_query_one(
            f"""
            SELECT MAX(metric_date) AS max_metric_date, COUNT(*) AS rows
            FROM home_geo_daily
            WHERE metric_date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        row_cfg_geo = await pg_query_one(
            f"""
            SELECT MAX(metric_date) AS max_metric_date, COUNT(*) AS rows
            FROM config_geo_daily
            WHERE metric_date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        row_cfg_pub = await pg_query_one(
            f"""
            SELECT MAX(metric_date) AS max_metric_date, COUNT(*) AS rows
            FROM config_publisher_daily
            WHERE metric_date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        return {
            "home_geo_daily": {
                "rows": int((row_home_geo or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_home_geo or {}).get("max_metric_date")),
            },
            "config_geo_daily": {
                "rows": int((row_cfg_geo or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_cfg_geo or {}).get("max_metric_date")),
            },
            "config_publisher_daily": {
                "rows": int((row_cfg_pub or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_cfg_pub or {}).get("max_metric_date")),
            },
        }

    async def _get_dimension_coverage(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        buyer_filter = ""
        params: list[Any] = []
        if buyer_id:
            buyer_filter = " AND buyer_id = %s"
            params.append(buyer_id)

        row = await pg_query_one(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) AS missing_country_rows,
                SUM(CASE WHEN publisher_id IS NULL OR publisher_id = '' THEN 1 ELSE 0 END) AS missing_publisher_rows,
                SUM(CASE WHEN billing_id IS NULL OR billing_id = '' THEN 1 ELSE 0 END) AS missing_billing_rows
            FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        total = int((row or {}).get("total_rows") or 0)
        if total == 0:
            return {
                "total_rows": 0,
                "country_missing_pct": 100.0,
                "publisher_missing_pct": 100.0,
                "billing_missing_pct": 100.0,
                "availability_state": "unavailable",
            }
        country_missing = int((row or {}).get("missing_country_rows") or 0)
        publisher_missing = int((row or {}).get("missing_publisher_rows") or 0)
        billing_missing = int((row or {}).get("missing_billing_rows") or 0)
        country_pct = round(country_missing * 100.0 / total, 2)
        publisher_pct = round(publisher_missing * 100.0 / total, 2)
        billing_pct = round(billing_missing * 100.0 / total, 2)
        state = "healthy"
        if country_pct > 50 or publisher_pct > 50:
            state = "degraded"
        return {
            "total_rows": total,
            "country_missing_pct": country_pct,
            "publisher_missing_pct": publisher_pct,
            "billing_missing_pct": billing_pct,
            "availability_state": state,
        }

    async def _get_ingestion_summary(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        buyer_filter = ""
        params: list[Any] = []
        if buyer_id:
            buyer_filter = " AND buyer_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT
                COUNT(*) AS total_runs,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_runs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_runs,
                MAX(started_at) AS last_started_at,
                MAX(finished_at) AS last_finished_at
            FROM ingestion_runs
            WHERE started_at >= CURRENT_TIMESTAMP - (%s::int * INTERVAL '1 day'){buyer_filter}
            """,
            tuple([days, *params]),
        )
        return {
            "total_runs": int((row or {}).get("total_runs") or 0),
            "successful_runs": int((row or {}).get("successful_runs") or 0),
            "failed_runs": int((row or {}).get("failed_runs") or 0),
            "last_started_at": _to_iso((row or {}).get("last_started_at")),
            "last_finished_at": _to_iso((row or {}).get("last_finished_at")),
        }

    def _compute_state(self, source: dict[str, Any], serving: dict[str, Any], coverage: dict[str, Any]) -> str:
        source_rows = source["rtb_daily"]["rows"] + source["rtb_geo_daily"]["rows"]
        serving_rows = (
            serving["home_geo_daily"]["rows"]
            + serving["config_geo_daily"]["rows"]
            + serving["config_publisher_daily"]["rows"]
        )
        if source_rows == 0 and serving_rows == 0:
            return "unavailable"
        if coverage["availability_state"] == "degraded":
            return "degraded"
        if serving["config_geo_daily"]["rows"] == 0 and serving["home_geo_daily"]["rows"] > 0:
            return "degraded"
        return "healthy"

