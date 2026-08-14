"""Stable Agent API contracts for creative performance batches."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from api.schemas.agent_provenance import MetricProvenance

MetricSource = Literal[
    "config_creative_daily",
    "performance_metrics",
    "unavailable",
]


class AgentCreativePerformanceBatchRequest(BaseModel):
    """One buyer and explicit metric window for up to 100 creatives."""

    buyer_id: str = Field(..., min_length=1)
    creative_ids: list[str] = Field(..., min_length=1, max_length=100)
    start_date: date
    end_date: date
    tolerance_pct: float = Field(1.0, ge=0, le=100)


class AgentCreativePerformanceEvidence(BaseModel):
    """Precomputed metrics for one requested creative."""

    creative_id: str
    total_impressions: int
    total_clicks: None = None
    total_spend_micros: int
    avg_cpm_micros: int | None = None
    days_with_data: int
    has_data: bool
    metric_source: MetricSource
    clicks_available: Literal[False]
    provenance: MetricProvenance


class AgentCreativePerformanceBatchResponse(BaseModel):
    """Ordered batch results, including unavailable precompute entries."""

    api_version: Literal["agent.v1"]
    buyer_id: str
    period: dict[str, str | int]
    source_tables: list[
        Literal["config_creative_daily", "performance_metrics"]
    ]
    performance: list[AgentCreativePerformanceEvidence]
    count: int
