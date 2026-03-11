"""Lazy settings router package exports.

Importing a single settings submodule should not require the full Authorized
Buyers client stack. Build the aggregate router only when the application asks
for it.
"""

from __future__ import annotations

from importlib import import_module

from fastapi import APIRouter, Depends

from api.dependencies import require_seat_admin_or_sudo


_SETTINGS_SUBMODULES = (
    "endpoints",
    "pretargeting",
    "snapshots",
    "changes",
    "actions",
    "optimizer",
)

_MODEL_EXPORTS = {
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
    "DiscardAllPendingChangesResponse",
    "SuspendActivateResponse",
    "RollbackRequest",
    "RollbackResponse",
}

__all__ = ["router", *_MODEL_EXPORTS]


def _build_router() -> APIRouter:
    router = APIRouter(
        tags=["RTB Settings"],
        dependencies=[Depends(require_seat_admin_or_sudo)],
    )
    for module_name in _SETTINGS_SUBMODULES:
        module = import_module(f"{__name__}.{module_name}")
        router.include_router(module.router)
    return router


def __getattr__(name: str):
    if name == "router":
        value = _build_router()
        globals()[name] = value
        return value
    if name in _MODEL_EXPORTS:
        module = import_module(f"{__name__}.models")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
