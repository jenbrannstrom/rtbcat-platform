"""Pydantic models for RTB Settings routers."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Endpoints Models
# =============================================================================

class RTBEndpointItem(BaseModel):
    """Individual RTB endpoint data."""
    endpoint_id: str
    url: str
    maximum_qps: Optional[int] = None
    trading_location: Optional[str] = None
    bid_protocol: Optional[str] = None


class RTBEndpointsResponse(BaseModel):
    """Response model for RTB endpoints with aggregated data."""
    bidder_id: str
    account_name: Optional[str] = None
    endpoints: list[RTBEndpointItem]
    total_qps_allocated: int
    qps_current: Optional[float] = None
    synced_at: Optional[str] = None


class SyncEndpointsResponse(BaseModel):
    """Response model for sync endpoints operation."""
    status: str
    endpoints_synced: int
    bidder_id: str


class UpdateEndpointQpsRequest(BaseModel):
    """Request to update allocated QPS for a single endpoint."""
    maximum_qps: int = Field(..., ge=0, description="New QPS limit")
    buyer_id: Optional[str] = Field(None, description="Buyer/seat ID to resolve bidder")
    service_account_id: Optional[str] = Field(None, description="Service account ID (fallback)")


# =============================================================================
# Pretargeting Config Models
# =============================================================================

class PretargetingConfigResponse(BaseModel):
    """Response model for a pretargeting config."""
    config_id: str
    bidder_id: str
    billing_id: Optional[str] = None
    display_name: Optional[str] = None
    user_name: Optional[str] = None
    state: str = "ACTIVE"
    included_formats: Optional[list[str]] = None
    included_platforms: Optional[list[str]] = None
    included_sizes: Optional[list[str]] = None
    included_geos: Optional[list[str]] = None
    excluded_geos: Optional[list[str]] = None
    included_operating_systems: Optional[list[str]] = None
    maximum_qps: Optional[int] = None
    synced_at: Optional[str] = None


class SyncPretargetingResponse(BaseModel):
    """Response model for sync pretargeting configs operation."""
    status: str
    configs_synced: int
    bidder_id: str


class SetPretargetingNameRequest(BaseModel):
    """Request body for setting a custom pretargeting config name."""
    user_name: str = Field(..., description="Custom name for this pretargeting config")


class PretargetingHistoryResponse(BaseModel):
    """Response model for pretargeting history entry."""
    id: int
    config_id: str
    bidder_id: str
    change_type: str
    field_changed: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: str
    changed_by: Optional[str] = None
    change_source: str
    rollback_context: Optional[dict[str, Any]] = None
    commit_context: Optional[dict[str, Any]] = None


# =============================================================================
# Snapshot Models
# =============================================================================

class SnapshotCreate(BaseModel):
    """Request to create a pretargeting config snapshot."""
    billing_id: str = Field(
        ...,
        description="Pretargeting config ID (billing_id)",
    )
    snapshot_name: Optional[str] = Field(None, description="Snapshot name")
    notes: Optional[str] = Field(None, description="Optional snapshot notes")
    snapshot_type: Optional[str] = Field(None, description="manual, auto, before_change")
    created_by: Optional[str] = Field(None, description="User who created the snapshot")


class SnapshotResponse(BaseModel):
    """Response model for a pretargeting config snapshot."""
    id: int
    billing_id: str
    snapshot_name: Optional[str] = None
    snapshot_type: Optional[str] = None
    state: Optional[str] = None
    included_formats: Optional[str] = None
    included_platforms: Optional[str] = None
    included_sizes: Optional[str] = None
    included_geos: Optional[str] = None
    excluded_geos: Optional[str] = None
    total_impressions: Optional[int] = None
    total_clicks: Optional[int] = None
    total_spend_usd: Optional[float] = None
    days_tracked: Optional[int] = None
    avg_daily_impressions: Optional[float] = None
    avg_daily_spend_usd: Optional[float] = None
    ctr_pct: Optional[float] = None
    cpm_usd: Optional[float] = None
    created_at: datetime
    notes: Optional[str] = None


class ComparisonCreate(BaseModel):
    """Request to create a snapshot comparison."""
    billing_id: str = Field(
        ...,
        description="Pretargeting config ID (billing_id) to compare",
    )
    comparison_name: Optional[str] = Field(None, description="Comparison name")
    before_snapshot_id: int = Field(..., description="Snapshot ID to compare against")
    before_start_date: Optional[str] = Field(None, description="Comparison start date (before)")
    before_end_date: Optional[str] = Field(None, description="Comparison end date (before)")


class ComparisonResponse(BaseModel):
    """Response model for a snapshot comparison."""
    id: int
    billing_id: str
    comparison_name: Optional[str] = None
    before_snapshot_id: int
    after_snapshot_id: Optional[int] = None
    before_start_date: Optional[str] = None
    before_end_date: Optional[str] = None
    after_start_date: Optional[str] = None
    after_end_date: Optional[str] = None
    impressions_delta: Optional[int] = None
    impressions_delta_pct: Optional[float] = None
    spend_delta_usd: Optional[float] = None
    spend_delta_pct: Optional[float] = None
    ctr_delta_pct: Optional[float] = None
    cpm_delta_pct: Optional[float] = None
    status: Optional[str] = None
    conclusion: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    sizes_removed: int = 0


# =============================================================================
# Pending Changes Models
# =============================================================================

class PendingChangeCreate(BaseModel):
    """Request to create a pending change."""
    billing_id: str
    change_type: str  # 'add_geo', 'remove_geo', 'add_size', 'remove_size', etc.
    field_name: str  # 'included_geos', 'excluded_geos', 'publisher_targeting', etc.
    value: str  # Single value to add/remove/update
    reason: Optional[str] = None
    estimated_qps_impact: Optional[int] = None
    created_by: Optional[str] = None


class PendingChangeResponse(BaseModel):
    """Response model for a pending change."""
    id: int
    billing_id: str
    config_id: Optional[str] = None
    change_type: str
    field_name: str
    value: str
    reason: Optional[str] = None
    estimated_qps_impact: Optional[int] = None
    status: str  # 'pending', 'applied', 'cancelled'
    created_at: datetime
    created_by: Optional[str] = None
    applied_at: Optional[datetime] = None


class ConfigDetailResponse(BaseModel):
    """Detailed response for a specific pretargeting config."""
    billing_id: str
    config_id: str
    bidder_id: str
    display_name: Optional[str] = None
    user_name: Optional[str] = None
    state: str
    # Full targeting details
    included_formats: list[str] = []
    included_platforms: list[str] = []
    included_sizes: list[str] = []
    included_geos: list[str] = []
    excluded_geos: list[str] = []
    maximum_qps: Optional[int] = None
    publisher_targeting_mode: Optional[str] = None
    publisher_targeting_values: list[str] = []
    # Pending changes summary
    pending_changes_count: int = 0
    pending_changes: list[PendingChangeResponse] = []
    effective_sizes: list[str] = []
    effective_geos: list[str] = []
    effective_formats: list[str] = []
    effective_maximum_qps: Optional[int] = None
    effective_publisher_targeting_mode: Optional[str] = None
    effective_publisher_targeting_values: list[str] = []
    # Recent history
    recent_history: list[PretargetingHistoryResponse] = []
    # Metadata
    synced_at: Optional[str] = None
    last_modified: Optional[str] = None


# =============================================================================
# Action Models
# =============================================================================

class ApplyChangeRequest(BaseModel):
    """Request to apply a pending change."""
    change_id: int
    dry_run: bool = True  # If true, preview without applying


class ApplyChangeResponse(BaseModel):
    """Response for applying a change."""
    status: str
    change_id: int
    dry_run: bool
    message: str
    updated_config: Optional[PretargetingConfigResponse] = None


class ApplyAllResponse(BaseModel):
    """Response for applying all pending changes."""
    status: str
    dry_run: bool
    changes_applied: int
    changes_failed: int
    message: str


class SuspendActivateResponse(BaseModel):
    """Response for suspend/activate operations."""
    status: str
    billing_id: str
    new_state: str
    message: str


class RollbackRequest(BaseModel):
    """Request to rollback to a snapshot."""
    snapshot_id: int
    dry_run: bool = True
    reason: Optional[str] = None
    proposal_id: Optional[str] = None


class RollbackResponse(BaseModel):
    """Response for rollback operation."""
    status: str
    dry_run: bool
    snapshot_id: int
    changes_made: list[str]
    message: str
    history_id: Optional[int] = None
