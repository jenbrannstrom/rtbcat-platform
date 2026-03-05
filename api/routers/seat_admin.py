"""Seat-scoped admin API for local-admin user management.

Local-admins (users with access_level='admin' for a buyer seat) can manage
user access for their seat(s) only. Sudo users can also use these endpoints.

This is separate from the global /admin/* routes to avoid weakening those.
"""

import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.dependencies import (
    get_current_user,
    get_auth_service,
    is_sudo,
    require_buyer_admin_access,
)
from api.request_trust import get_client_ip
from services.auth_service import User
from services.admin_service import AdminService

# Singleton AdminService instance
_admin_service: Optional[AdminService] = None


def _get_admin_service() -> AdminService:
    global _admin_service
    if _admin_service is None:
        _admin_service = AdminService()
    return _admin_service


router = APIRouter(prefix="/seat-admin", tags=["Seat Admin"])


# ==================== Request/Response Models ====================


class SeatUserPermission(BaseModel):
    """A user's permission for a buyer seat."""
    user_id: str
    email: str
    display_name: Optional[str] = None
    access_level: str  # "read" or "admin"
    granted_by: Optional[str] = None
    granted_at: Optional[str] = None


class GrantSeatPermissionRequest(BaseModel):
    """Request to grant/update a user's seat access."""
    access_level: str = Field("read", description="Access level: 'read' or 'admin'")


class GrantSeatPermissionResponse(BaseModel):
    """Response after granting seat permission."""
    status: str
    user_id: str
    buyer_id: str
    access_level: str


# ==================== Endpoints ====================


@router.get("/seats/{buyer_id}/users", response_model=List[SeatUserPermission])
async def list_seat_users(
    buyer_id: str,
    user: User = Depends(get_current_user),
) -> List[SeatUserPermission]:
    """List users with access to a specific buyer seat.

    Caller must be sudo or local-admin for this buyer seat.
    """
    await require_buyer_admin_access(buyer_id, user)

    auth_svc = get_auth_service()
    # Get all permissions for this buyer_id across all users
    # We need a new repo method for this, or query via the permissions repo
    perms_repo = auth_svc._perms
    from storage.postgres_database import pg_query
    rows = await pg_query(
        """
        SELECT ubsp.user_id, u.email, u.display_name,
               ubsp.access_level, ubsp.granted_by, ubsp.granted_at
        FROM user_buyer_seat_permissions ubsp
        JOIN users u ON u.id = ubsp.user_id
        WHERE ubsp.buyer_id = %s AND u.is_active = true
        ORDER BY u.email
        """,
        (buyer_id,),
    )
    return [
        SeatUserPermission(
            user_id=row["user_id"],
            email=row["email"],
            display_name=row.get("display_name"),
            access_level=row["access_level"],
            granted_by=row.get("granted_by"),
            granted_at=str(row["granted_at"]) if row.get("granted_at") else None,
        )
        for row in rows
    ]


@router.post(
    "/seats/{buyer_id}/users/{user_id}/permission",
    response_model=GrantSeatPermissionResponse,
)
async def grant_seat_permission(
    buyer_id: str,
    user_id: str,
    body: GrantSeatPermissionRequest,
    request: Request,
    caller: User = Depends(get_current_user),
) -> GrantSeatPermissionResponse:
    """Grant or update a user's access to a buyer seat.

    Caller must be sudo or local-admin for this buyer seat.
    Local-admins cannot grant global roles or sudo access.
    """
    await require_buyer_admin_access(buyer_id, caller)

    if body.access_level not in ("read", "admin"):
        raise HTTPException(status_code=400, detail="access_level must be 'read' or 'admin'")

    # Verify target user exists
    auth_svc = get_auth_service()
    target_user = await auth_svc.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    admin_svc = _get_admin_service()
    client_ip = get_client_ip(request)

    await admin_svc.grant_buyer_seat_permission(
        admin=caller,
        user_id=user_id,
        buyer_id=buyer_id,
        access_level=body.access_level,
        client_ip=client_ip,
    )

    return GrantSeatPermissionResponse(
        status="success",
        user_id=user_id,
        buyer_id=buyer_id,
        access_level=body.access_level,
    )


@router.delete("/seats/{buyer_id}/users/{user_id}/permission")
async def revoke_seat_permission(
    buyer_id: str,
    user_id: str,
    request: Request,
    caller: User = Depends(get_current_user),
) -> dict[str, str]:
    """Revoke a user's access to a buyer seat.

    Caller must be sudo or local-admin for this buyer seat.
    Local-admins cannot revoke sudo access.
    """
    await require_buyer_admin_access(buyer_id, caller)

    # Prevent local-admin from revoking a sudo user's access
    auth_svc = get_auth_service()
    target_user = await auth_svc.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.role == "sudo" and not is_sudo(caller):
        raise HTTPException(
            status_code=403,
            detail="Cannot revoke seat access from a sudo user. Contact a system administrator.",
        )

    admin_svc = _get_admin_service()
    client_ip = get_client_ip(request)

    revoked = await admin_svc.revoke_buyer_seat_permission(
        admin=caller,
        user_id=user_id,
        buyer_id=buyer_id,
        client_ip=client_ip,
    )

    if not revoked:
        raise HTTPException(status_code=404, detail="Permission not found")

    return {"status": "success", "message": f"Revoked {user_id} access to buyer {buyer_id}"}
