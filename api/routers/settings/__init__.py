"""RTB Settings routers package.

This package organizes the settings-related routes into focused modules:
- models.py: Shared Pydantic models
- endpoints.py: RTB endpoints sync and management (TODO)
- pretargeting.py: Pretargeting config management (TODO)
- snapshots.py: Config snapshots and comparisons (TODO)
- changes.py: Pending changes queue (TODO)
- actions.py: Apply, suspend, activate, rollback (TODO)

Currently, all routes are still in the legacy settings.py file.
The models have been extracted to models.py for reuse.

Migration plan:
1. Extract endpoints routes (~200 lines)
2. Extract pretargeting routes (~300 lines)
3. Extract snapshots routes (~200 lines)
4. Extract changes routes (~350 lines)
5. Extract actions routes (~350 lines)
"""

# Re-export models for easy importing
from .models import (
    # Endpoints
    RTBEndpointItem,
    RTBEndpointsResponse,
    SyncEndpointsResponse,
    # Pretargeting
    PretargetingConfigResponse,
    SyncPretargetingResponse,
    SetPretargetingNameRequest,
    PretargetingHistoryResponse,
    # Snapshots
    SnapshotCreate,
    SnapshotResponse,
    ComparisonCreate,
    ComparisonResponse,
    # Changes
    PendingChangeCreate,
    PendingChangeResponse,
    ConfigDetailResponse,
    # Actions
    ApplyChangeRequest,
    ApplyChangeResponse,
    ApplyAllResponse,
    SuspendActivateResponse,
    RollbackRequest,
    RollbackResponse,
)

# Import the legacy router for backward compatibility
# TODO: Replace with individual sub-routers as migration completes
from ..settings_legacy import router

__all__ = [
    "router",
    # Models
    "RTBEndpointItem",
    "RTBEndpointsResponse",
    "SyncEndpointsResponse",
    "PretargetingConfigResponse",
    "SyncPretargetingResponse",
    "SetPretargetingNameRequest",
    "PretargetingHistoryResponse",
    "SnapshotCreate",
    "SnapshotResponse",
    "ComparisonCreate",
    "ComparisonResponse",
    "PendingChangeCreate",
    "PendingChangeResponse",
    "ConfigDetailResponse",
    "ApplyChangeRequest",
    "ApplyChangeResponse",
    "ApplyAllResponse",
    "SuspendActivateResponse",
    "RollbackRequest",
    "RollbackResponse",
]
