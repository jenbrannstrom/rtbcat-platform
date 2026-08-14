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


class AgentCreativeDestinationCandidate(BaseModel):
    """One stored URL considered by destination resolution."""

    source: str
    url: str
    eligible: bool
    reason: str | None = None


class AgentCreativeDestinationDiagnostics(BaseModel):
    """Why a creative resolves to its reported click destination."""

    resolved_destination_url: str | None = None
    candidate_count: int
    eligible_count: int
    candidates: list[AgentCreativeDestinationCandidate]
    has_any_macro: bool
    has_click_macro: bool
    macro_tokens: list[str]
    click_macro_tokens: list[str]
    has_payload_click_macro: bool
    has_payload_only_click_macro: bool
    payload_click_macro_tokens: list[str]


class AgentCreativeDetailResponse(BaseModel):
    """Buyer-scoped creative detail without raw creative payloads."""

    api_version: Literal["agent.v1"]
    source_table: Literal["creatives"]
    creative_id: str
    buyer_id: str
    name: str
    format: str
    approval_status: str | None = None
    width: int | None = None
    height: int | None = None
    canonical_size: str | None = None
    final_url: str | None = None
    display_url: str | None = None
    advertiser_name: str | None = None
    campaign_id: str | None = None
    app_id: str | None = None
    app_name: str | None = None
    app_store: str | None = None
    disapproval_reasons: list[Any]
    serving_restrictions: list[Any]
    first_seen_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    destination_diagnostics: AgentCreativeDestinationDiagnostics
    assets_reference: str
