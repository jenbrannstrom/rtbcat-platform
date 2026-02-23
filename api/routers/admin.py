"""Admin API for user management.

This module provides administrative endpoints for managing users,
permissions, and viewing audit logs. All endpoints require admin role.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.dependencies import require_admin, get_current_user
from services.auth_service import User
from services.admin_service import AdminService

# Singleton AdminService instance
_admin_service: Optional[AdminService] = None


def get_admin_service() -> AdminService:
    """Get or create the AdminService instance."""
    global _admin_service
    if _admin_service is None:
        _admin_service = AdminService()
    return _admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])

# ==================== Request/Response Models ====================

class CreateUserRequest(BaseModel):
    """Request to create a new user (local password or OAuth pre-create)."""
    email: str = Field(..., description="User email address")
    display_name: Optional[str] = Field(None, description="User display name")
    role: str = Field("user", description="User role (admin or user)")
    default_language: Optional[str] = Field("en", description="Default UI language code")
    auth_method: Optional[str] = Field(
        None,
        description="User auth method: local-password or oauth-precreate (defaults to oauth-precreate for legacy clients)",
    )
    password: Optional[str] = Field(
        None,
        description="Required when auth_method=local-password",
    )


class CreateUserResponse(BaseModel):
    """Response after creating a user."""
    status: str
    user_id: str
    email: str
    message: str


class UserResponse(BaseModel):
    """User details response."""
    id: str
    email: str
    display_name: Optional[str]
    role: str
    is_active: bool
    created_at: Optional[str]
    last_login_at: Optional[str]
    default_language: Optional[str]


class UpdateUserRequest(BaseModel):
    """Request to update a user."""
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    default_language: Optional[str] = None


class PermissionRequest(BaseModel):
    """Request to grant/update permission."""
    service_account_id: str
    permission_level: str = Field("read", description="Permission level (read, write, admin)")


class PermissionResponse(BaseModel):
    """Permission details response."""
    id: str
    user_id: str
    service_account_id: str
    permission_level: str
    granted_by: Optional[str]
    granted_at: Optional[str]


class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: str
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    created_at: Optional[str]


class SystemSettingResponse(BaseModel):
    """System setting response."""
    key: str
    value: str
    description: Optional[str]


class UpdateSettingRequest(BaseModel):
    """Request to update a system setting."""
    value: str


# ==================== Helper Functions ====================

def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ==================== User Management Endpoints ====================

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    active_only: bool = Query(False, description="Only show active users"),
    role: Optional[str] = Query(None, description="Filter by role"),
    admin: User = Depends(require_admin),
):
    """List all users.

    Requires admin role.
    """
    admin_svc = get_admin_service()
    users = await admin_svc.list_users(active_only=active_only, role=role)

    return [
        UserResponse(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
            default_language=u.default_language,
        )
        for u in users
    ]


@router.post("/users", response_model=CreateUserResponse)
async def create_user(
    request: Request,
    user_request: CreateUserRequest,
    admin: User = Depends(require_admin),
):
    """Create a new user (local password or OAuth pre-register).

    Requires admin role.
    - local-password: creates user and stores password hash immediately
    - oauth-precreate: pre-creates user for external auth login
    """
    admin_svc = get_admin_service()
    result = await admin_svc.create_user(
        admin=admin,
        email=user_request.email,
        display_name=user_request.display_name,
        role=user_request.role,
        default_language=user_request.default_language,
        auth_method=user_request.auth_method,
        password=user_request.password,
        client_ip=_get_client_ip(request),
    )
    return CreateUserResponse(**result)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Get a specific user's details.

    Requires admin role.
    """
    admin_svc = get_admin_service()
    user = await admin_svc.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        default_language=user.default_language,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: str,
    user_update: UpdateUserRequest,
    admin: User = Depends(require_admin),
):
    """Update a user's details.

    Requires admin role. Can update display_name, role, and is_active.
    """
    admin_svc = get_admin_service()
    updated_user = await admin_svc.update_user(
        admin=admin,
        user_id=user_id,
        display_name=user_update.display_name,
        role=user_update.role,
        is_active=user_update.is_active,
        default_language=user_update.default_language,
        client_ip=_get_client_ip(request),
    )

    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        display_name=updated_user.display_name,
        role=updated_user.role,
        is_active=updated_user.is_active,
        created_at=updated_user.created_at,
        last_login_at=updated_user.last_login_at,
        default_language=updated_user.default_language,
    )


@router.delete("/users/{user_id}")
async def deactivate_user(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Deactivate a user (soft delete).

    Requires admin role. The user account is deactivated, not deleted.
    This also invalidates all their sessions.
    """
    admin_svc = get_admin_service()
    return await admin_svc.deactivate_user(
        admin=admin,
        user_id=user_id,
        client_ip=_get_client_ip(request),
    )


# ==================== Permission Management Endpoints ====================

@router.get("/users/{user_id}/permissions", response_model=List[PermissionResponse])
async def get_user_permissions(
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Get a user's service account permissions.

    Requires admin role.
    """
    admin_svc = get_admin_service()
    user = await admin_svc.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permissions = await admin_svc.get_user_permissions(user_id)

    return [
        PermissionResponse(
            id=p.id,
            user_id=p.user_id,
            service_account_id=p.service_account_id,
            permission_level=p.permission_level,
            granted_by=p.granted_by,
            granted_at=p.granted_at,
        )
        for p in permissions
    ]


@router.post("/users/{user_id}/permissions", response_model=PermissionResponse)
async def grant_permission(
    request: Request,
    user_id: str,
    perm_request: PermissionRequest,
    admin: User = Depends(require_admin),
):
    """Grant a user access to a service account.

    Requires admin role. If permission already exists, it will be updated.
    """
    admin_svc = get_admin_service()
    user = await admin_svc.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permission = await admin_svc.grant_permission(
        admin=admin,
        user_id=user_id,
        service_account_id=perm_request.service_account_id,
        permission_level=perm_request.permission_level,
        client_ip=_get_client_ip(request),
    )

    return PermissionResponse(
        id=permission.id,
        user_id=permission.user_id,
        service_account_id=permission.service_account_id,
        permission_level=permission.permission_level,
        granted_by=permission.granted_by,
        granted_at=permission.granted_at,
    )


@router.delete("/users/{user_id}/permissions/{service_account_id}")
async def revoke_permission(
    request: Request,
    user_id: str,
    service_account_id: str,
    admin: User = Depends(require_admin),
):
    """Revoke a user's access to a service account.

    Requires admin role.
    """
    admin_svc = get_admin_service()
    user = await admin_svc.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await admin_svc.revoke_permission(
        admin=admin,
        user_id=user_id,
        service_account_id=service_account_id,
        client_ip=_get_client_ip(request),
    )
    return {"status": "success", "message": "Permission revoked"}


# ==================== Audit Log Endpoints ====================

@router.get("/audit-log", response_model=List[AuditLogResponse])
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    admin: User = Depends(require_admin),
):
    """Query audit log entries.

    Requires admin role. Supports filtering by user, action, resource type,
    and time range.
    """
    admin_svc = get_admin_service()
    logs = await admin_svc.get_audit_logs(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        since_days=days,
        limit=limit,
        offset=offset,
    )

    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]


# ==================== System Settings Endpoints ====================

@router.get("/settings", response_model=dict)
async def get_settings(
    admin: User = Depends(require_admin),
):
    """Get all system settings.

    Requires admin role.
    """
    admin_svc = get_admin_service()
    return await admin_svc.get_settings()


@router.put("/settings/{key}")
async def update_setting(
    request: Request,
    key: str,
    setting_update: UpdateSettingRequest,
    admin: User = Depends(require_admin),
):
    """Update a system setting.

    Requires admin role.
    """
    admin_svc = get_admin_service()
    return await admin_svc.update_setting(
        admin=admin,
        key=key,
        value=setting_update.value,
        client_ip=_get_client_ip(request),
    )


# ==================== User Stats Endpoint ====================

@router.get("/stats")
async def get_admin_stats(
    admin: User = Depends(require_admin),
):
    """Get admin dashboard stats.

    Requires admin role. Returns counts of users, sessions, etc.
    """
    admin_svc = get_admin_service()
    return await admin_svc.get_admin_stats()


# ==================== Diagnostic Endpoint ====================

@router.get("/diagnostics")
async def get_diagnostics(
    admin: User = Depends(require_admin),
):
    """Get diagnostic information for debugging data issues.

    Requires admin role. Returns:
    - All buyer seats (including inactive)
    - Campaign-creative mapping status
    - Thumbnail generation status
    - Import history by account

    Use this to investigate Phase 3B issues:
    - Issue 1: Campaigns tab empty (creative_id mismatch)
    - Issue 2: Missing third account (is_active check)
    - Issue 3: Thumbnail placeholders
    - Issue 5: CSV import account mismatch
    """
    admin_svc = get_admin_service()
    return await admin_svc.get_diagnostics()


@router.post("/diagnostics/fix-inactive-seats")
async def fix_inactive_seats(
    admin: User = Depends(require_admin),
):
    """Activate all inactive buyer seats.

    Use this to fix Issue 2: Missing third account showing only 2 of 3 accounts.
    Sets active=1 for all buyer_seats entries.
    """
    admin_svc = get_admin_service()
    return await admin_svc.activate_inactive_seats()
