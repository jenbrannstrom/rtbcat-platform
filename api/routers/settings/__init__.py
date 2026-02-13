"""RTB Settings routers package.

This package organizes the settings-related routes into focused modules:
- models.py: Shared Pydantic models
- endpoints.py: RTB endpoints sync and management
- pretargeting.py: Pretargeting config management
- snapshots.py: Config snapshots and comparisons
- changes.py: Pending changes queue
- actions.py: Apply, suspend, activate, rollback

All settings routes have been extracted into focused subrouters.
The models have been extracted to models.py for reuse.

Migration plan:
1. Extract endpoints routes (~200 lines) - completed
2. Extract pretargeting routes (~300 lines) - completed
3. Extract snapshots routes (~200 lines) - completed
4. Extract changes routes (~350 lines) - completed
5. Extract actions routes (~350 lines) - completed
"""

# Re-export models for easy importing
from fastapi import APIRouter, Depends
from api.dependencies import require_admin

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

from .endpoints import router as endpoints_router
from .pretargeting import router as pretargeting_router
from .snapshots import router as snapshots_router
from .changes import router as changes_router
from .actions import router as actions_router

router = APIRouter(
    tags=["RTB Settings"],
    dependencies=[Depends(require_admin)],
)
router.include_router(endpoints_router)
router.include_router(pretargeting_router)
router.include_router(snapshots_router)
router.include_router(changes_router)
router.include_router(actions_router)

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
