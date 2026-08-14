"""Stable response contracts for Agent API creative reads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from api.schemas.agent_provenance import MetricProvenance


class AgentCreativeMetricEvidence(BaseModel):
    """Precomputed evidence used to rank one creative."""

    spend_micros: int
    impressions: int
    spend_rank: int
    provenance: MetricProvenance


class AgentCreativeListRow(BaseModel):
    """Compact creative evidence suitable for an outside agent."""

    creative_id: str
    buyer_id: str
    name: str
    format: str
    approval_status: str | None = None
    destination_url: str | None = None
    resolved_destination_url: str | None = None
    preview_reference: str
    activity_status: Literal["active", "inactive"]
    metrics: AgentCreativeMetricEvidence


class AgentCreativeListResponse(BaseModel):
    """Cursor page ordered by spend descending, then creative ID ascending.

    The next cursor is an opaque URL-safe base64 encoding of compact JSON
    [spend_micros, creative_id]. The pair resumes the stable
    spend-descending/creative-ID-ascending ordering without an offset.
    """

    api_version: Literal["agent.v1"]
    buyer_id: str
    period: dict[str, str | int]
    source_table: Literal["config_creative_daily"]
    creatives: list[AgentCreativeListRow]
    next_cursor: str | None = None
    has_more: bool
