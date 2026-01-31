"""Pretargeting apply/suspend/activate/rollback routes."""

import logging

from fastapi import APIRouter, HTTPException, Query

from services.actions_service import ActionsService

from .models import (
    ApplyAllResponse,
    ApplyChangeRequest,
    ApplyChangeResponse,
    RollbackRequest,
    RollbackResponse,
    SuspendActivateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])


@router.post("/settings/pretargeting/{billing_id}/apply", response_model=ApplyChangeResponse)
async def apply_pending_change(
    billing_id: str,
    request: ApplyChangeRequest,
):
    """
    Apply a single pending change to Google Authorized Buyers.

    WARNING: This modifies your live pretargeting configuration!
    Use dry_run=True (default) to preview changes first.

    Supports:
    - add_size / remove_size
    - add_geo / remove_geo
    - add_format / remove_format
    - add_publisher / remove_publisher
    - set_publisher_mode
    """
    try:
        service = ActionsService()
        result = await service.apply_pending_change(
            billing_id=billing_id,
            change_id=request.change_id,
            dry_run=request.dry_run,
        )
        return ApplyChangeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to apply change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply change: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/apply-all", response_model=ApplyAllResponse)
async def apply_all_pending_changes(
    billing_id: str,
    dry_run: bool = Query(True, description="Preview changes without applying"),
):
    """
    Apply all pending changes for a billing_id to Google.

    WARNING: This modifies your live pretargeting configuration!
    Use dry_run=True (default) to preview changes first.
    """
    try:
        service = ActionsService()
        result = await service.apply_all_pending_changes(
            billing_id=billing_id,
            dry_run=dry_run,
        )
        return ApplyAllResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to apply all changes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply all changes: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/suspend", response_model=SuspendActivateResponse)
async def suspend_pretargeting_config(
    billing_id: str,
):
    """
    Suspend a pretargeting configuration.

    This immediately stops QPS from being consumed by this config.
    Creates an auto-snapshot before suspending for easy rollback.

    WARNING: This affects live bidding!
    """
    try:
        service = ActionsService()
        result = await service.suspend_config(billing_id=billing_id)
        return SuspendActivateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to suspend config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to suspend config: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/activate", response_model=SuspendActivateResponse)
async def activate_pretargeting_config(
    billing_id: str,
):
    """
    Activate a suspended pretargeting configuration.

    This resumes QPS consumption for this config.

    WARNING: This affects live bidding!
    """
    try:
        service = ActionsService()
        result = await service.activate_config(billing_id=billing_id)
        return SuspendActivateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to activate config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to activate config: {str(e)}")


@router.post("/settings/pretargeting/{billing_id}/rollback", response_model=RollbackResponse)
async def rollback_to_snapshot(
    billing_id: str,
    request: RollbackRequest,
):
    """
    Rollback a pretargeting config to a previous snapshot state.

    This restores the config to its state at the time of the snapshot.
    Use dry_run=True (default) to preview what would change.

    WARNING: This modifies your live pretargeting configuration!
    """
    try:
        service = ActionsService()
        result = await service.rollback_to_snapshot(
            billing_id=billing_id,
            snapshot_id=request.snapshot_id,
            dry_run=request.dry_run,
        )
        return RollbackResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to rollback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")
