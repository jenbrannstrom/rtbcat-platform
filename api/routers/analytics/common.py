"""Common utilities and models shared across analytics routers.

Contains helper functions and Pydantic models used by multiple analytics endpoints.
"""

import logging
from typing import Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from services.analytics_service import AnalyticsService
from storage.postgres_repositories.analytics_repo import AnalyticsRepository

logger = logging.getLogger(__name__)

# Singleton service instance for helper functions
_analytics_service: Optional[AnalyticsService] = None


def _get_analytics_service() -> AnalyticsService:
    """Get or create the analytics service singleton."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service


async def get_precompute_status(
    table_name: str,
    days: int,
    filters: Optional[list[str]] = None,
    params: Optional[list] = None,
) -> dict:
    """Check if a precompute table exists and has rows for the requested range."""
    service = _get_analytics_service()
    status = await service.get_precompute_status(table_name, days, filters, params)
    return {
        "table": status.table,
        "exists": status.exists,
        "has_rows": status.has_rows,
        "row_count": status.row_count,
    }


# =============================================================================
# Shared Helper Functions
# =============================================================================

async def get_current_bidder_id() -> Optional[str]:
    """Get the current bidder_id from the most recently synced pretargeting config.

    Returns the bidder_id that was most recently synced, which represents
    the currently active account.
    """
    service = _get_analytics_service()
    return await service.get_current_bidder_id()


async def get_valid_billing_ids() -> list[str]:
    """Get list of pretargeting config IDs (`billing_id`) for current account.

    This ensures we only query data for pretargeting configs that belong to the
    currently configured account, preventing cross-account data mixing.

    The function first identifies the current bidder_id (account), then
    returns only `billing_id` values associated with that account.

    Billing IDs are normalized (trimmed) to match CSV import format.
    """
    service = _get_analytics_service()
    return await service.get_valid_billing_ids()


async def get_valid_billing_ids_for_buyer(buyer_id: Optional[str] = None) -> list[str]:
    """Get list of pretargeting config IDs (`billing_id`) for a buyer seat.

    If buyer_id is provided, returns `billing_id` values for that specific buyer seat.
    This allows filtering data by selected buyer in multi-account scenarios.

    Args:
        buyer_id: The buyer seat ID to filter by. If None, returns all `billing_id` values.

    Returns:
        List of `billing_id` strings for the specified buyer (or all if not specified).
        Billing IDs are normalized (trimmed) to match CSV import format.
    """
    service = _get_analytics_service()
    return await service.get_valid_billing_ids_for_buyer(buyer_id)


def _group_signals_by_type(signals) -> dict[str, int]:
    """Group signals by type and count."""
    counts = {}
    for s in signals:
        counts[s.signal_type] = counts.get(s.signal_type, 0) + 1
    return counts


def validate_identifier_integrity(
    *,
    buyer_id: Optional[str] = None,
    billing_id: Optional[str] = None,
) -> None:
    """Reject obvious buyer/billing identifier mixups at the API boundary.

    Buyer seat IDs (`buyer_id`) and pretargeting config IDs (`billing_id`) are
    distinct namespaces and must not be substituted for each other.
    """
    normalized_buyer = (buyer_id or "").strip()
    normalized_billing = (billing_id or "").strip()
    if normalized_buyer and normalized_billing and normalized_buyer == normalized_billing:
        raise HTTPException(
            status_code=400,
            detail=(
                "buyer_id and billing_id are different identifier types; "
                "do not pass a buyer/seat ID as billing_id."
            ),
        )


async def validate_billing_id_ownership(
    billing_id: Optional[str],
    buyer_id: Optional[str],
) -> None:
    """Reject billing_id that doesn't belong to the resolved buyer.

    Only validates when BOTH billing_id and buyer_id are provided.
    When buyer_id is None (admin with no filter), skip check.

    Uses direct repo calls that propagate DB errors (unlike
    get_valid_billing_ids_for_buyer which swallows exceptions).
    """
    if not billing_id or not buyer_id:
        return
    repo = AnalyticsRepository()
    bidder_id = await repo.get_bidder_id_for_buyer(buyer_id)
    if not bidder_id:
        raise HTTPException(
            status_code=404,
            detail="Pretargeting config not found.",
        )
    valid_ids = await repo.get_billing_ids_for_bidder(bidder_id)
    if billing_id.strip() not in valid_ids:
        raise HTTPException(
            status_code=404,
            detail="Pretargeting config not found.",
        )


# =============================================================================
# Pydantic Models
# =============================================================================

class SizeGapResponse(BaseModel):
    """Response model for a size gap in waste analysis."""
    canonical_size: str
    request_count: int
    creative_count: int
    estimated_qps: float
    estimated_waste_pct: float
    recommendation: str
    recommendation_detail: str
    potential_savings_usd: Optional[float] = None
    closest_iab_size: Optional[str] = None


class SizeCoverageResponse(BaseModel):
    """Response model for size coverage data."""
    canonical_size: str
    creative_count: int
    request_count: int
    coverage_status: str
    formats: dict = Field(default_factory=dict)


class WasteReportResponse(BaseModel):
    """Response model for waste analysis report."""
    buyer_id: Optional[str]
    total_requests: int
    total_waste_requests: int
    waste_percentage: float
    size_gaps: list[SizeGapResponse]
    size_coverage: list[SizeCoverageResponse]
    potential_savings_qps: float
    potential_savings_usd: Optional[float]
    qps_basis: Literal["avg_daily"] = "avg_daily"
    analysis_period_days: int
    generated_at: str
    recommendations_summary: dict = Field(default_factory=dict)


class WasteSignalResponse(BaseModel):
    """Response model for a waste signal."""
    id: int
    creative_id: str
    signal_type: str
    confidence: str
    evidence: dict
    observation: str
    recommendation: str
    detected_at: str
    resolved_at: Optional[str] = None


class ProblemFormatResponse(BaseModel):
    """Response model for problem format detection."""
    creative_id: str
    problem_type: str
    evidence: dict
    severity: str
    recommendation: str


class ImportTrafficResponse(BaseModel):
    """Response model for traffic import operation."""
    status: str
    records_imported: int
    message: str
