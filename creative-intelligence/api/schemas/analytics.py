"""Analytics and waste analysis schema models."""

from typing import Optional
from pydantic import BaseModel, Field


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


class ImportTrafficResponse(BaseModel):
    """Response model for traffic import operation."""
    status: str
    records_imported: int
    message: str


class WasteSignalResponse(BaseModel):
    """Response model for a waste signal."""
    id: str
    creative_id: str
    signal_type: str
    severity: str
    description: str
    evidence: dict
    detected_at: str
    resolved: bool = False
    resolved_at: Optional[str] = None


class ProblemFormatResponse(BaseModel):
    """Response model for problem format analysis."""
    creative_id: str
    format: str
    size: Optional[str] = None
    problem_type: str
    severity: str
    description: str
    recommendation: str
