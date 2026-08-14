"""Precomputed creative-performance batches for the Agent API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException

from api.schemas.agent_provenance import (
    AllocationReconciliation,
    build_provenance,
)
from services.agent_data_quality_service import AgentDataQualityService
from storage.postgres_database import pg_query_with_timeout

MAX_PERFORMANCE_RANGE_DAYS = 90


def _int(value: object) -> int:
    return 0 if value is None else int(value)


def _date_str(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _requested_dates(start_date: date, end_date: date) -> list[str]:
    return [
        date.fromordinal(ordinal).isoformat()
        for ordinal in range(start_date.toordinal(), end_date.toordinal() + 1)
    ]


@dataclass
class AgentCreativePerformanceRepository:
    """Statement-bounded access to creative ownership and precompute lanes."""

    statement_timeout_ms: int = 5000

    async def get_creative_buyers(
        self,
        creative_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not creative_ids:
            return []
        return await pg_query_with_timeout(
            """
            SELECT id AS creative_id, buyer_id
            FROM creatives
            WHERE id = ANY(%s)
            """,
            (creative_ids,),
            statement_timeout_ms=self.statement_timeout_ms,
        )

    async def get_summaries(
        self,
        *,
        creative_ids: list[str],
        buyer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        if not creative_ids:
            return []
        return await pg_query_with_timeout(
            """
            WITH config_summary AS (
                SELECT creative_id,
                       COALESCE(SUM(impressions), 0)::bigint AS total_impressions,
                       COALESCE(SUM(spend_micros), 0)::bigint AS total_spend_micros,
                       COUNT(DISTINCT metric_date)::int AS days_with_data,
                       ARRAY_AGG(DISTINCT metric_date ORDER BY metric_date) AS source_dates,
                       'config_creative_daily'::text AS metric_source
                FROM config_creative_daily
                WHERE creative_id = ANY(%s)
                  AND buyer_account_id = %s
                  AND metric_date BETWEEN %s AND %s
                GROUP BY creative_id
            ), performance_summary AS (
                SELECT creative_id,
                       COALESCE(SUM(impressions), 0)::bigint AS total_impressions,
                       COALESCE(SUM(spend_micros), 0)::bigint AS total_spend_micros,
                       COUNT(DISTINCT metric_date)::int AS days_with_data,
                       ARRAY_AGG(DISTINCT metric_date ORDER BY metric_date) AS source_dates,
                       'performance_metrics'::text AS metric_source
                FROM performance_metrics
                WHERE creative_id = ANY(%s)
                  AND metric_date BETWEEN %s AND %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM config_summary configured
                      WHERE configured.creative_id = performance_metrics.creative_id
                  )
                GROUP BY creative_id
            )
            SELECT * FROM config_summary
            UNION ALL
            SELECT * FROM performance_summary
            ORDER BY creative_id
            """,
            (
                creative_ids,
                buyer_id,
                start_date,
                end_date,
                creative_ids,
                start_date,
                end_date,
            ),
            statement_timeout_ms=self.statement_timeout_ms,
        )


class AgentCreativePerformanceService:
    """Build an honest performance row for every requested creative."""

    def __init__(
        self,
        repo: AgentCreativePerformanceRepository | None = None,
        quality_service: AgentDataQualityService | None = None,
    ) -> None:
        self._repo = repo or AgentCreativePerformanceRepository()
        self._quality = quality_service or AgentDataQualityService()

    async def get_batch(
        self,
        *,
        buyer_id: str,
        creative_ids: list[str],
        start_date: date,
        end_date: date,
        tolerance_pct: float = 1.0,
    ) -> dict[str, Any]:
        if end_date < start_date:
            raise HTTPException(
                status_code=400, detail="end_date must be on or after start_date."
            )
        requested_days = (end_date - start_date).days + 1
        if requested_days > MAX_PERFORMANCE_RANGE_DAYS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Date range is limited to {MAX_PERFORMANCE_RANGE_DAYS} "
                    "days per request."
                ),
            )
        unique_ids = list(dict.fromkeys(creative_ids))
        owners = await self._repo.get_creative_buyers(unique_ids)
        owners_by_id = {
            str(row["creative_id"]): row.get("buyer_id")
            for row in owners
        }
        if any(owners_by_id.get(creative_id) != buyer_id for creative_id in unique_ids):
            raise HTTPException(
                status_code=403,
                detail="One or more creatives are outside the requested buyer scope.",
            )

        rows = await self._repo.get_summaries(
            creative_ids=unique_ids,
            buyer_id=buyer_id,
            start_date=start_date,
            end_date=end_date,
        )
        summaries = {str(row["creative_id"]): row for row in rows}
        quality = await self._quality.get_data_quality(
            buyer_id=buyer_id,
            start_date=start_date,
            end_date=end_date,
            tolerance_pct=tolerance_pct,
        )
        allocation = AllocationReconciliation(**quality["allocation"])
        requested_dates = _requested_dates(start_date, end_date)
        performance = [
            self._performance_row(
                creative_id=creative_id,
                row=summaries.get(creative_id),
                buyer_id=buyer_id,
                requested_dates=requested_dates,
                allocation=allocation,
            )
            for creative_id in unique_ids
        ]
        return {
            "api_version": "agent.v1",
            "buyer_id": buyer_id,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": requested_days,
            },
            "source_tables": [
                "config_creative_daily",
                "performance_metrics",
            ],
            "performance": performance,
            "count": len(performance),
        }

    def _performance_row(
        self,
        *,
        creative_id: str,
        row: dict[str, Any] | None,
        buyer_id: str,
        requested_dates: list[str],
        allocation: AllocationReconciliation,
    ) -> dict[str, Any]:
        source_dates = {
            _date_str(value) for value in ((row or {}).get("source_dates") or [])
        }
        missing_dates = [value for value in requested_dates if value not in source_dates]
        latest_complete_date: str | None = None
        for value in requested_dates:
            if value not in source_dates:
                break
            latest_complete_date = value

        impressions = _int((row or {}).get("total_impressions"))
        spend_micros = _int((row or {}).get("total_spend_micros"))
        metric_source = (
            str(row["metric_source"])
            if row
            and row.get("metric_source")
            in {"config_creative_daily", "performance_metrics"}
            else "unavailable"
        )
        avg_cpm_micros = (
            int(spend_micros / impressions * 1000)
            if impressions > 0 and spend_micros > 0
            else None
        )
        return {
            "creative_id": creative_id,
            "total_impressions": impressions,
            "total_clicks": None,
            "total_spend_micros": spend_micros,
            "avg_cpm_micros": avg_cpm_micros,
            "days_with_data": _int((row or {}).get("days_with_data")),
            "has_data": impressions > 0 or spend_micros > 0,
            "metric_source": metric_source,
            "clicks_available": False,
            "provenance": build_provenance(
                metric_source=metric_source,
                is_canonical=False,
                buyer_scope=buyer_id,
                latest_complete_date=latest_complete_date,
                latest_source_date=max(source_dates) if source_dates else None,
                missing_source_dates=missing_dates,
                allocation=allocation,
            ),
        }
