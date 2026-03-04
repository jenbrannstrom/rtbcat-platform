"""Pretargeting pending changes routes (local-only)."""

import asyncio
import json
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import require_seat_admin_or_sudo
from services.auth_service import User
from services.changes_service import ChangesService
from services.pretargeting_service import PretargetingService

from .models import ConfigDetailResponse, PendingChangeCreate, PendingChangeResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RTB Settings"])

MajorChangeType = Literal["targeting", "publisher", "qps", "mixed"]


def _major_change_type_for_change(change_type: str) -> MajorChangeType:
    publisher_change_types = {"add_publisher", "remove_publisher", "set_publisher_mode"}
    if change_type == "set_maximum_qps":
        return "qps"
    if change_type in publisher_change_types:
        return "publisher"
    return "targeting"


def _resolve_active_major_change_type(
    pending_changes: list[dict],
    has_pending_publisher_changes: bool,
) -> MajorChangeType | None:
    detected: set[MajorChangeType] = {
        _major_change_type_for_change(str(change.get("change_type") or ""))
        for change in pending_changes
    }
    if has_pending_publisher_changes:
        detected.add("publisher")
    if not detected:
        return None
    if len(detected) == 1:
        return next(iter(detected))
    return "mixed"


def _parse_json_field(value: Any) -> Any:
    """Parse JSON field - handles both JSONB (already parsed) and TEXT (needs parsing)."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value  # Already parsed by psycopg (JSONB column)
    return json.loads(value)  # TEXT column, needs parsing


@router.post("/settings/pretargeting/pending-change", response_model=PendingChangeResponse)
async def create_pending_change(
    request: PendingChangeCreate,
    _user: User = Depends(require_seat_admin_or_sudo),
) -> PendingChangeResponse:
    """
    Create a pending change to a pretargeting configuration.

    IMPORTANT: This does NOT modify the Google Authorized Buyers account.
    Changes are staged locally and can be reviewed before manual application.

    Use this to:
    - Block sizes that are wasting QPS
    - Add/remove geographic targeting
    - Add/remove format targeting

    The change will be recorded in the pending_changes table and can be:
    - Reviewed in the UI
    - Applied manually by the user in Google Authorized Buyers
    - Cancelled if no longer needed
    """
    # Validate change_type
    valid_change_types = [
        'add_size', 'remove_size',
        'add_geo', 'remove_geo',
        'add_format', 'remove_format',
        'add_excluded_geo', 'remove_excluded_geo',
        'add_publisher', 'remove_publisher',
        'set_publisher_mode',
        'set_maximum_qps',
        'change_state',
    ]
    if request.change_type not in valid_change_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid change_type. Must be one of: {', '.join(valid_change_types)}"
        )
    if request.change_type == "set_publisher_mode" and request.value not in {"INCLUSIVE", "EXCLUSIVE"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid publisher mode. Must be INCLUSIVE or EXCLUSIVE."
        )
    if request.change_type == "set_maximum_qps":
        try:
            qps_limit = int(request.value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="QPS limit must be an integer.") from None
        if qps_limit < 0:
            raise HTTPException(status_code=400, detail="QPS limit must be >= 0.")

    try:
        change_service = ChangesService()
        pretargeting_service = PretargetingService()

        config = await pretargeting_service.get_config(request.billing_id)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Pretargeting config not found for ID (billing_id): {request.billing_id}"
            )

        config_id = config["config_id"]
        bidder_id = config.get("bidder_id")

        pending_changes = await change_service.list_pending_changes(
            billing_id=request.billing_id,
            status="pending",
            limit=500,
        )
        pending_publisher_changes = await pretargeting_service.list_pending_publisher_changes(
            request.billing_id
        )
        active_major_type = _resolve_active_major_change_type(
            pending_changes=pending_changes,
            has_pending_publisher_changes=bool(pending_publisher_changes),
        )
        requested_major_type = _major_change_type_for_change(request.change_type)
        if active_major_type == "mixed":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Pending changes already span multiple major change types. "
                    "Commit or clear current pending changes before staging more."
                ),
            )
        if active_major_type and active_major_type != requested_major_type:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Only one major change type can be staged per commit "
                    f"(current={active_major_type}, requested={requested_major_type}). "
                    "Commit or clear pending changes first."
                ),
            )

        change_id = await change_service.create_pending_change(
            billing_id=request.billing_id,
            config_id=config_id,
            change_type=request.change_type,
            field_name=request.field_name,
            value=request.value,
            reason=request.reason,
            estimated_qps_impact=request.estimated_qps_impact,
            created_by="ui",
        )

        if bidder_id:
            await pretargeting_service.add_history(
                config_id=config_id,
                bidder_id=bidder_id,
                change_type="pending_change",
                field_changed=request.field_name,
                old_value=None,
                new_value=f"{request.change_type}:{request.value}",
                changed_by="ui",
                change_source="user",
            )

        row = await change_service.get_pending_change(change_id)

        return PendingChangeResponse(
            id=row["id"],
            billing_id=row["billing_id"],
            config_id=row["config_id"],
            change_type=row["change_type"],
            field_name=row["field_name"],
            value=row["value"],
            reason=row["reason"],
            estimated_qps_impact=row["estimated_qps_impact"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            status=row["status"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create pending change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create pending change: {str(e)}")


@router.get("/settings/pretargeting/pending-changes", response_model=list[PendingChangeResponse])
async def list_pending_changes(
    billing_id: Optional[str] = Query(
        None,
        description="Filter by pretargeting config ID (billing_id)",
    ),
    status: str = Query("pending", description="Filter by status (pending, applied, cancelled)"),
    limit: int = Query(100, ge=1, le=500),
) -> list[PendingChangeResponse]:
    """List pending changes to pretargeting configurations."""
    try:
        change_service = ChangesService()
        rows = await change_service.list_pending_changes(
            billing_id=billing_id, status=status, limit=limit
        )

        return [
            PendingChangeResponse(
                id=row["id"],
                billing_id=row["billing_id"],
                config_id=row["config_id"],
                change_type=row["change_type"],
                field_name=row["field_name"],
                value=row["value"],
                reason=row["reason"],
                estimated_qps_impact=row["estimated_qps_impact"],
                created_at=row["created_at"],
                created_by=row["created_by"],
                status=row["status"],
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Failed to list pending changes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list pending changes: {str(e)}")


@router.delete("/settings/pretargeting/pending-change/{change_id}")
async def cancel_pending_change(
    change_id: int,
    _user: User = Depends(require_seat_admin_or_sudo),
) -> dict[str, str | int]:
    """Cancel a pending change (mark as cancelled, not deleted)."""
    try:
        change_service = ChangesService()
        change = await change_service.get_pending_change(change_id)

        if not change:
            raise HTTPException(status_code=404, detail="Pending change not found")

        if change["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Change cannot be cancelled - current status: {change['status']}"
            )

        await change_service.cancel_pending_change(change_id)

        return {"status": "cancelled", "id": change_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel pending change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel pending change: {str(e)}")


@router.post("/settings/pretargeting/pending-change/{change_id}/mark-applied")
async def mark_change_applied(
    change_id: int,
    _user: User = Depends(require_seat_admin_or_sudo),
) -> dict[str, str | int]:
    """
    Mark a pending change as applied (user has manually applied it in Google UI).

    This is for tracking purposes only - it does NOT make any API calls.
    """
    try:
        change_service = ChangesService()
        change = await change_service.get_pending_change(change_id)

        if not change:
            raise HTTPException(status_code=404, detail="Pending change not found")

        if change["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Change is not pending - current status: {change['status']}"
            )

        await change_service.mark_pending_change_applied(change_id)

        return {"status": "applied", "id": change_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark change as applied: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark change as applied: {str(e)}")


@router.get("/settings/pretargeting/{billing_id}/detail", response_model=ConfigDetailResponse)
async def get_pretargeting_config_detail(
    billing_id: str,
) -> ConfigDetailResponse:
    """
    Get detailed pretargeting config including current state and pending changes.

    Returns:
    - Current config values (from last Google sync)
    - List of pending changes
    - Effective values (what the config would look like after pending changes)
    """
    try:
        pretargeting_service = PretargetingService()
        change_service = ChangesService()
        config, pending_rows = await asyncio.gather(
            pretargeting_service.get_config(billing_id),
            change_service.list_pending_changes(
                billing_id=billing_id,
                status="pending",
                limit=500,
            ),
        )

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Pretargeting config not found for ID (billing_id): {billing_id}"
            )

        # Service returns newest-first; reverse for deterministic oldest-first UI sequence.
        # Reverse to get ASC order (service returns DESC)
        pending_rows = list(reversed(pending_rows))

        # Parse current values (handles both JSONB and TEXT columns)
        included_sizes = _parse_json_field(config.get("included_sizes")) or []
        included_geos = _parse_json_field(config.get("included_geos")) or []
        excluded_geos = _parse_json_field(config.get("excluded_geos")) or []
        included_formats = _parse_json_field(config.get("included_formats")) or []
        included_platforms = _parse_json_field(config.get("included_platforms")) or []
        raw_config = _parse_json_field(config.get("raw_config")) or {}
        publisher_targeting = raw_config.get("publisherTargeting") or {}
        publisher_mode = publisher_targeting.get("targetingMode")
        publisher_values = publisher_targeting.get("values") or []
        maximum_qps = raw_config.get("maximumQps")
        if maximum_qps is not None:
            try:
                maximum_qps = int(maximum_qps)
            except (TypeError, ValueError):
                maximum_qps = None

        # Build pending changes list
        pending_changes = [
            PendingChangeResponse(
                id=row["id"],
                billing_id=row["billing_id"],
                config_id=row["config_id"],
                change_type=row["change_type"],
                field_name=row["field_name"],
                value=row["value"],
                reason=row["reason"],
                estimated_qps_impact=row["estimated_qps_impact"],
                created_at=row["created_at"],
                created_by=row["created_by"],
                status=row["status"],
            )
            for row in pending_rows
        ]

        # Compute effective values (current + pending applied)
        effective_sizes = set(included_sizes)
        effective_geos = set(included_geos)
        effective_formats = set(included_formats)
        effective_maximum_qps = maximum_qps
        effective_publisher_mode = publisher_mode
        effective_publishers = set(publisher_values)

        for change in pending_changes:
            if change.change_type == 'add_size':
                effective_sizes.add(change.value)
            elif change.change_type == 'remove_size':
                effective_sizes.discard(change.value)
            elif change.change_type == 'add_geo':
                effective_geos.add(change.value)
            elif change.change_type == 'remove_geo':
                effective_geos.discard(change.value)
            elif change.change_type == 'add_format':
                effective_formats.add(change.value)
            elif change.change_type == 'remove_format':
                effective_formats.discard(change.value)
            elif change.change_type == 'set_maximum_qps':
                try:
                    effective_maximum_qps = int(change.value)
                except (TypeError, ValueError):
                    continue
            elif change.change_type == 'set_publisher_mode':
                effective_publisher_mode = change.value
                effective_publishers = set()
            elif change.change_type == 'add_publisher':
                effective_publishers.add(change.value)
            elif change.change_type == 'remove_publisher':
                effective_publishers.discard(change.value)

        return ConfigDetailResponse(
            config_id=config["config_id"],
            billing_id=billing_id,
            bidder_id=config["bidder_id"],
            display_name=config["display_name"],
            user_name=config["user_name"],
            state=config["state"] or "ACTIVE",
            included_formats=included_formats,
            included_platforms=included_platforms,
            included_sizes=included_sizes,
            included_geos=included_geos,
            excluded_geos=excluded_geos,
            maximum_qps=maximum_qps,
            publisher_targeting_mode=publisher_mode,
            publisher_targeting_values=publisher_values,
            synced_at=str(config["synced_at"]) if config["synced_at"] else None,
            pending_changes=pending_changes,
            pending_changes_count=len(pending_changes),
            effective_sizes=sorted(list(effective_sizes)),
            effective_geos=sorted(list(effective_geos)),
            effective_formats=sorted(list(effective_formats)),
            effective_maximum_qps=effective_maximum_qps,
            effective_publisher_targeting_mode=effective_publisher_mode,
            effective_publisher_targeting_values=sorted(list(effective_publishers)),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config detail: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get config detail: {str(e)}")


# =============================================================================
