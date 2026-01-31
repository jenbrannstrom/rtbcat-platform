"""Common utilities and models shared across analytics routers.

Contains helper functions and Pydantic models used by multiple analytics endpoints.
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from services.analytics_service import AnalyticsService

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
    """Get list of billing_ids from pretargeting_configs table for current account.

    This ensures we only query data for billing IDs that belong to the
    currently configured account, preventing cross-account data mixing.

    The function first identifies the current bidder_id (account), then
    returns only billing_ids associated with that account.

    Billing IDs are normalized (trimmed) to match CSV import format.
    """
    service = _get_analytics_service()
    return await service.get_valid_billing_ids()


async def get_valid_billing_ids_for_buyer(buyer_id: Optional[str] = None) -> list[str]:
    """Get list of billing_ids for a specific buyer seat.

    If buyer_id is provided, returns billing_ids for that specific buyer seat.
    This allows filtering data by selected buyer in multi-account scenarios.

    Args:
        buyer_id: The buyer seat ID to filter by. If None, returns all billing_ids.

    Returns:
        List of billing_id strings for the specified buyer (or all if not specified).
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
