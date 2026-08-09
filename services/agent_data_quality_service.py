"""Canonical-vs-allocated spend reconciliation for the Agent API.

RTBcat has two precomputed spend lanes at different grains:

- ``rtb_buyer_spend_daily`` — canonical buyer-grain spend (the number that
  matches the buyer's billing reality).
- ``config_creative_daily`` — creative x pretargeting-config grain, used for
  creative rankings. Its per-buyer sums can exceed canonical spend (a
  creative served under multiple configs contributes multiple rows), so
  creative-level dollar figures are only trustworthy when this service says
  the two lanes reconcile.

This service does not fix the underlying ETL gaps; it makes them visible and
machine-readable so no client discovers an overcount by diffing unrelated
endpoints (docs/MCP_READONLY_SERVER_PLAN.md, defect D6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException

from api.schemas.agent_provenance import AllocationReconciliation, build_provenance
from storage.postgres_database import pg_query_with_timeout

MAX_RANGE_DAYS = 90
DEFAULT_TOLERANCE_PCT = 1.0


def _int(value: object) -> int:
    return 0 if value is None else int(value)


def _date_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


@dataclass
class AgentDataQualityRepository:
    """SQL access for the two spend lanes, buyer-scoped and time-boxed."""

    statement_timeout_ms: int = 5000

    async def get_buyer(self, buyer_id: str) -> dict[str, Any] | None:
        rows = await pg_query_with_timeout(
            """
            SELECT buyer_id, bidder_id, display_name, active, currency_code
            FROM buyer_seats
            WHERE buyer_id = %s
            """,
            (buyer_id,),
            statement_timeout_ms=self.statement_timeout_ms,
        )
        return rows[0] if rows else None

    async def get_canonical_daily(
        self, buyer_id: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        return await pg_query_with_timeout(
            """
            SELECT metric_date,
                   COALESCE(SUM(spend_micros), 0)::bigint AS spend_micros,
                   COALESCE(SUM(impressions), 0)::bigint AS impressions
            FROM rtb_buyer_spend_daily
            WHERE buyer_account_id = %s
              AND metric_date BETWEEN %s AND %s
            GROUP BY metric_date
            ORDER BY metric_date
            """,
            (buyer_id, start_date, end_date),
            statement_timeout_ms=self.statement_timeout_ms,
        )

    async def get_allocated_daily(
        self, buyer_id: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        return await pg_query_with_timeout(
            """
            SELECT metric_date,
                   COALESCE(SUM(spend_micros), 0)::bigint AS spend_micros,
                   COALESCE(SUM(impressions), 0)::bigint AS impressions,
                   COUNT(DISTINCT creative_id)::int AS distinct_creatives
            FROM config_creative_daily
            WHERE buyer_account_id = %s
              AND metric_date BETWEEN %s AND %s
            GROUP BY metric_date
            ORDER BY metric_date
            """,
            (buyer_id, start_date, end_date),
            statement_timeout_ms=self.statement_timeout_ms,
        )


class AgentDataQualityService:
    """Compare canonical buyer spend with creative-allocated spend."""

    def __init__(self, repo: AgentDataQualityRepository | None = None) -> None:
        self._repo = repo or AgentDataQualityRepository()

    async def get_data_quality(
        self,
        *,
        buyer_id: str,
        start_date: date,
        end_date: date,
        tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    ) -> dict[str, Any]:
        if end_date < start_date:
            raise HTTPException(
                status_code=400, detail="end_date must be on or after start_date."
            )
        requested_days = (end_date - start_date).days + 1
        if requested_days > MAX_RANGE_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"Date range is limited to {MAX_RANGE_DAYS} days per request.",
            )
        if not 0 <= tolerance_pct <= 100:
            raise HTTPException(
                status_code=400, detail="tolerance_pct must be between 0 and 100."
            )

        buyer = await self._repo.get_buyer(buyer_id)
        if not buyer:
            raise HTTPException(status_code=404, detail="Buyer seat not found.")

        canonical_rows = await self._repo.get_canonical_daily(buyer_id, start_date, end_date)
        allocated_rows = await self._repo.get_allocated_daily(buyer_id, start_date, end_date)
        canonical_by_date = {_date_str(row["metric_date"]): row for row in canonical_rows}
        allocated_by_date = {_date_str(row["metric_date"]): row for row in allocated_rows}

        days: list[dict[str, Any]] = []
        current = start_date
        while current <= end_date:
            key = current.isoformat()
            canonical = canonical_by_date.get(key)
            allocated = allocated_by_date.get(key)
            canonical_micros = _int(canonical["spend_micros"]) if canonical else 0
            allocated_micros = _int(allocated["spend_micros"]) if allocated else 0
            days.append(
                {
                    "metric_date": key,
                    "canonical_spend_micros": canonical_micros,
                    "allocated_spend_micros": allocated_micros,
                    "difference_micros": allocated_micros - canonical_micros,
                    "canonical_present": canonical is not None,
                    "allocated_present": allocated is not None,
                    "distinct_creatives": _int(allocated["distinct_creatives"]) if allocated else 0,
                    "day_status": self._status(
                        canonical_micros, allocated_micros, tolerance_pct
                    ),
                }
            )
            current = date.fromordinal(current.toordinal() + 1)

        canonical_total = sum(day["canonical_spend_micros"] for day in days)
        allocated_total = sum(day["allocated_spend_micros"] for day in days)
        difference = allocated_total - canonical_total
        status = self._status(canonical_total, allocated_total, tolerance_pct)
        difference_pct = (
            round(difference / canonical_total * 100, 4) if canonical_total else None
        )

        missing_canonical_dates = [d["metric_date"] for d in days if not d["canonical_present"]]
        latest_complete_date: str | None = None
        for day in days:
            if not day["canonical_present"]:
                break
            latest_complete_date = day["metric_date"]
        present_dates = [d["metric_date"] for d in days if d["canonical_present"]]

        allocation = AllocationReconciliation(
            allocation_status=status,
            canonical_spend_micros=canonical_total,
            allocated_spend_micros=allocated_total,
            difference_micros=difference,
            difference_pct=difference_pct,
            tolerance_pct=tolerance_pct,
        )

        warnings: list[str] = []
        if status == "non_reconciling":
            warnings.append(
                "Creative-allocated spend does not reconcile with canonical buyer "
                "spend for this window. Use creative figures as relative ranking "
                "signals only, not dollar allocations."
            )
        if missing_canonical_dates:
            warnings.append(
                f"Canonical spend rows are missing for {len(missing_canonical_dates)} "
                "of the requested dates; totals understate the true window."
            )

        return {
            "api_version": "agent.v1",
            "buyer": {
                "buyer_id": str(buyer["buyer_id"]),
                "bidder_id": buyer.get("bidder_id"),
                "display_name": buyer.get("display_name"),
                "active": bool(buyer.get("active", True)),
            },
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": requested_days,
            },
            "canonical": {
                "table": "rtb_buyer_spend_daily",
                "total_spend_micros": canonical_total,
                "missing_dates": missing_canonical_dates,
                "latest_complete_date": latest_complete_date,
            },
            "allocated": {
                "table": "config_creative_daily",
                "total_spend_micros": allocated_total,
                "days_with_rows": sum(1 for d in days if d["allocated_present"]),
                "max_distinct_creatives_per_day": max(
                    (d["distinct_creatives"] for d in days), default=0
                ),
            },
            "allocation": allocation.model_dump(),
            "days": days,
            "warnings": warnings,
            "provenance": build_provenance(
                metric_source="rtb_buyer_spend_daily",
                is_canonical=True,
                buyer_scope=str(buyer["buyer_id"]),
                latest_complete_date=latest_complete_date,
                latest_source_date=max(present_dates) if present_dates else None,
                missing_source_dates=missing_canonical_dates,
                allocation=allocation,
            ),
        }

    @staticmethod
    def _status(
        canonical_micros: int, allocated_micros: int, tolerance_pct: float
    ) -> str:
        """Reconciled when the lanes agree within tolerance of canonical spend."""
        if canonical_micros == 0 and allocated_micros == 0:
            return "reconciled"
        if canonical_micros == 0:
            return "non_reconciling"
        tolerance_micros = abs(canonical_micros) * tolerance_pct / 100
        if abs(allocated_micros - canonical_micros) <= tolerance_micros:
            return "reconciled"
        return "non_reconciling"
