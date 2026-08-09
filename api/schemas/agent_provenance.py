"""Metric-provenance envelope for Agent API responses.

Every Agent API metrics response carries a ``provenance`` block so consumers
never have to guess which table produced a number, how fresh it is, or
whether a figure is canonical buyer spend or a creative-level allocation
(see docs/MCP_READONLY_SERVER_PLAN.md, section 4 decision 6).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AllocationStatus = Literal["reconciled", "non_reconciling", "not_applicable"]


class AllocationReconciliation(BaseModel):
    """Canonical-vs-allocated spend comparison for one buyer and window."""

    allocation_status: AllocationStatus
    canonical_spend_micros: int | None = None
    allocated_spend_micros: int | None = None
    difference_micros: int | None = None
    difference_pct: float | None = Field(
        None,
        description="Difference as a percentage of canonical spend; null when canonical is 0.",
    )
    tolerance_pct: float | None = Field(
        None,
        description="Tolerance applied when deciding reconciled vs non_reconciling.",
    )


class MetricProvenance(BaseModel):
    """Which source produced a metrics payload, and how trustworthy it is."""

    metric_source: str = Field(..., description="Primary precomputed table behind the numbers.")
    is_canonical: bool = Field(
        ...,
        description=(
            "True when figures come from the canonical buyer-grain spend lane "
            "(rtb_buyer_spend_daily); false for allocated creative-grain lanes."
        ),
    )
    buyer_scope: str
    latest_complete_date: str | None = Field(
        None,
        description="Latest date D such that every requested date <= D has source rows.",
    )
    latest_source_date: str | None = Field(
        None,
        description="Most recent requested date with any source rows (freshness signal).",
    )
    missing_source_dates: list[str] = Field(default_factory=list)
    allocation: AllocationReconciliation


NOT_APPLICABLE_ALLOCATION = AllocationReconciliation(allocation_status="not_applicable")


def build_provenance(
    *,
    metric_source: str,
    is_canonical: bool,
    buyer_scope: str,
    latest_complete_date: str | None,
    latest_source_date: str | None,
    missing_source_dates: list[str],
    allocation: AllocationReconciliation | None = None,
) -> dict[str, Any]:
    """Build a validated provenance block as a plain dict for JSON payloads."""
    return MetricProvenance(
        metric_source=metric_source,
        is_canonical=is_canonical,
        buyer_scope=buyer_scope,
        latest_complete_date=latest_complete_date,
        latest_source_date=latest_source_date,
        missing_source_dates=missing_source_dates,
        allocation=allocation or NOT_APPLICABLE_ALLOCATION,
    ).model_dump()
