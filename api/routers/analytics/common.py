"""Common utilities and models shared across analytics routers.

Contains helper functions and Pydantic models used by multiple analytics endpoints.
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from storage.database import db_query, db_query_one

logger = logging.getLogger(__name__)


# =============================================================================
# Shared Helper Functions
# =============================================================================

async def get_current_bidder_id() -> Optional[str]:
    """Get the current bidder_id from the most recently synced pretargeting config.

    Returns the bidder_id that was most recently synced, which represents
    the currently active account.
    """
    try:
        row = await db_query_one("""
            SELECT bidder_id FROM pretargeting_configs
            WHERE bidder_id IS NOT NULL
            ORDER BY synced_at DESC
            LIMIT 1
        """)
        return row["bidder_id"] if row else None
    except Exception:
        return None


async def get_valid_billing_ids() -> list[str]:
    """Get list of billing_ids from pretargeting_configs table for current account.

    This ensures we only query data for billing IDs that belong to the
    currently configured account, preventing cross-account data mixing.

    The function first identifies the current bidder_id (account), then
    returns only billing_ids associated with that account.
    """
    try:
        # Get the current bidder_id (most recently synced account)
        current_bidder = await get_current_bidder_id()

        if current_bidder:
            # Filter by the current account's bidder_id
            rows = await db_query(
                "SELECT DISTINCT billing_id FROM pretargeting_configs WHERE billing_id IS NOT NULL AND bidder_id = ?",
                (current_bidder,)
            )
        else:
            # Fallback: return all billing_ids if no bidder_id found
            rows = await db_query(
                "SELECT DISTINCT billing_id FROM pretargeting_configs WHERE billing_id IS NOT NULL"
            )

        return [row["billing_id"] for row in rows]
    except Exception:
        return []


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
