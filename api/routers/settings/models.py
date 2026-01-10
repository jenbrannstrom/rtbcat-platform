"""Pydantic models for RTB Settings routers."""

from typing import Optional
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
    qps_current: Optional[int] = None
    synced_at: Optional[str] = None


class SyncEndpointsResponse(BaseModel):
    """Response model for sync endpoints operation."""
    status: str
    endpoints_synced: int
    bidder_id: str


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


# =============================================================================
# Snapshot Models
# =============================================================================

class SnapshotCreate(BaseModel):
    """Request to create a pretargeting config snapshot."""
    billing_id: str = Field(..., description="Billing ID of the pretargeting config")
    description: Optional[str] = Field(None, description="Optional description")
    created_by: Optional[str] = Field(None, description="User who created the snapshot")


class SnapshotResponse(BaseModel):
    """Response model for a pretargeting config snapshot."""
    id: int
    billing_id: str
    config_id: str
    bidder_id: str
    snapshot_data: dict
    description: Optional[str] = None
    created_at: str
    created_by: Optional[str] = None
    # Summary fields
    included_formats: Optional[list[str]] = None
    included_geos_count: int = 0
    excluded_geos_count: int = 0
    included_sizes_count: int = 0


class ComparisonCreate(BaseModel):
    """Request to create a config comparison."""
    billing_id: str = Field(..., description="Billing ID to compare")
    snapshot_id: int = Field(..., description="Snapshot ID to compare against")
    description: Optional[str] = Field(None, description="Optional description")


class ComparisonResponse(BaseModel):
    """Response model for a pretargeting config comparison."""
    id: int
    billing_id: str
    snapshot_id: int
    snapshot_description: Optional[str] = None
    comparison_data: dict
    created_at: str
    # Summary of differences
    has_differences: bool = False
    fields_changed: list[str] = []
    geos_added: int = 0
    geos_removed: int = 0
    sizes_added: int = 0
    sizes_removed: int = 0


# =============================================================================
# Pending Changes Models
# =============================================================================

class PendingChangeCreate(BaseModel):
    """Request to create a pending change."""
    billing_id: str
    change_type: str  # 'add_geo', 'remove_geo', 'add_size', 'remove_size', etc.
    field: str  # 'included_geos', 'excluded_geos', 'included_sizes', etc.
    values: list[str]  # List of values to add/remove
    reason: Optional[str] = None
    created_by: Optional[str] = None


class PendingChangeResponse(BaseModel):
    """Response model for a pending change."""
    id: int
    billing_id: str
    config_id: Optional[str] = None
    change_type: str
    field: str
    values: list[str]
    reason: Optional[str] = None
    status: str  # 'pending', 'applied', 'cancelled'
    created_at: str
    created_by: Optional[str] = None
    applied_at: Optional[str] = None


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
    # Pending changes summary
    pending_changes_count: int = 0
    pending_changes: list[PendingChangeResponse] = []
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
    apply_to_api: bool = True  # If true, push to Google API


class ApplyChangeResponse(BaseModel):
    """Response for applying a change."""
    status: str
    change_id: int
    applied_to_api: bool
    message: str
    api_response: Optional[dict] = None


class ApplyAllResponse(BaseModel):
    """Response for applying all pending changes."""
    status: str
    changes_applied: int
    changes_failed: int
    details: list[dict]


class SuspendActivateResponse(BaseModel):
    """Response for suspend/activate operations."""
    status: str
    billing_id: str
    new_state: str
    message: str


class RollbackRequest(BaseModel):
    """Request to rollback to a snapshot."""
    snapshot_id: int
    apply_to_api: bool = True


class RollbackResponse(BaseModel):
    """Response for rollback operation."""
    status: str
    billing_id: str
    snapshot_id: int
    changes_made: list[str]
    applied_to_api: bool
