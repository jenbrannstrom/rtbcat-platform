"""QPS optimization schema models."""

from typing import Optional
from pydantic import BaseModel


class QPSImportResult(BaseModel):
    """Result of QPS data import."""
    success: bool
    rows_imported: int
    rows_skipped: int
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    sizes_found: int
    billing_ids_found: list[str]
    total_reached_queries: int
    total_spend_usd: float
    errors: list[str] = []


class QPSSummaryResponse(BaseModel):
    """Response for QPS data summary."""
    total_rows: int
    unique_dates: int
    unique_billing_ids: int
    unique_sizes: int
    date_range: dict
    total_reached_queries: int
    total_impressions: int
    total_spend_usd: float


class QPSReportResponse(BaseModel):
    """Response for QPS report (plain text)."""
    report: str
    generated_at: str
    analysis_days: int
