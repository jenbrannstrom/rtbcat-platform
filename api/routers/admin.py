"""Admin API for user management.

This module provides administrative endpoints for managing users,
permissions, and viewing audit logs. All endpoints require admin role.
"""

import json
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.dependencies import require_admin, get_current_user, _get_user_repo
from api.auth_v2 import hash_password, generate_password
from storage.repositories.user_repository import User

router = APIRouter(prefix="/admin", tags=["Admin"])


# ==================== Request/Response Models ====================

class CreateUserRequest(BaseModel):
    """Request to create a new user."""
    email: str = Field(..., description="User email address")
    display_name: Optional[str] = Field(None, description="User display name")
    role: str = Field("user", description="User role (admin or user)")
    password: Optional[str] = Field(None, description="Password (auto-generated if not provided)")


class CreateUserResponse(BaseModel):
    """Response after creating a user."""
    status: str
    user_id: str
    email: str
    password: str  # Return generated password (only shown once!)
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


class UpdateUserRequest(BaseModel):
    """Request to update a user."""
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


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
    repo = _get_user_repo()
    users = await repo.get_users(active_only=active_only, role=role)

    return [
        UserResponse(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]


@router.post("/users", response_model=CreateUserResponse)
async def create_user(
    request: Request,
    user_request: CreateUserRequest,
    admin: User = Depends(require_admin),
):
    """Create a new user.

    Requires admin role. Password is auto-generated if not provided.
    The generated password is returned in the response and should be
    shared securely with the user (it's only shown once).
    """
    repo = _get_user_repo()

    # Check if email already exists
    existing = await repo.get_user_by_email(user_request.email.lower().strip())
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")

    # Validate role
    if user_request.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")

    # Generate password if not provided
    password = user_request.password or generate_password()
    password_hash = hash_password(password)

    # Create user
    user_id = str(uuid.uuid4())
    user = await repo.create_user(
        user_id=user_id,
        email=user_request.email.lower().strip(),
        password_hash=password_hash,
        display_name=user_request.display_name,
        role=user_request.role,
    )

    # Log the action
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="create_user",
        user_id=admin.id,
        resource_type="user",
        resource_id=user_id,
        details=json.dumps({
            "email": user.email,
            "role": user.role,
            "created_by": admin.email,
        }),
        ip_address=_get_client_ip(request),
    )

    return CreateUserResponse(
        status="success",
        user_id=user_id,
        email=user.email,
        password=password,  # Only shown once!
        message="User created successfully. Share the password securely.",
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Get a specific user's details.

    Requires admin role.
    """
    repo = _get_user_repo()
    user = await repo.get_user_by_id(user_id)

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
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: str,
    user_update: UpdateUserRequest,
    admin: User = Depends(require_admin),
):
    """Update a user's details.

    Requires admin role. Can update display_name, role, is_active, and password.
    """
    repo = _get_user_repo()
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Don't allow deactivating self
    if user_update.is_active is False and user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    # Don't allow removing own admin role
    if user_update.role == "user" and user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin role")

    # Hash password if provided
    password_hash = None
    if user_update.password:
        password_hash = hash_password(user_update.password)

    # Update user
    await repo.update_user(
        user_id=user_id,
        display_name=user_update.display_name,
        role=user_update.role,
        is_active=user_update.is_active,
        password_hash=password_hash,
    )

    # Log the action
    changes = {}
    if user_update.display_name is not None:
        changes["display_name"] = user_update.display_name
    if user_update.role is not None:
        changes["role"] = user_update.role
    if user_update.is_active is not None:
        changes["is_active"] = user_update.is_active
    if user_update.password:
        changes["password"] = "changed"

    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="update_user",
        user_id=admin.id,
        resource_type="user",
        resource_id=user_id,
        details=json.dumps(changes),
        ip_address=_get_client_ip(request),
    )

    # Get updated user
    updated_user = await repo.get_user_by_id(user_id)

    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        display_name=updated_user.display_name,
        role=updated_user.role,
        is_active=updated_user.is_active,
        created_at=updated_user.created_at,
        last_login_at=updated_user.last_login_at,
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
    repo = _get_user_repo()
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    # Deactivate user
    await repo.update_user(user_id=user_id, is_active=False)

    # Delete all their sessions
    sessions_deleted = await repo.delete_user_sessions(user_id)

    # Log the action
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="deactivate_user",
        user_id=admin.id,
        resource_type="user",
        resource_id=user_id,
        details=json.dumps({
            "email": user.email,
            "sessions_deleted": sessions_deleted,
        }),
        ip_address=_get_client_ip(request),
    )

    return {
        "status": "success",
        "message": "User deactivated",
        "sessions_deleted": sessions_deleted,
    }


# ==================== Permission Management Endpoints ====================

@router.get("/users/{user_id}/permissions", response_model=List[PermissionResponse])
async def get_user_permissions(
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Get a user's service account permissions.

    Requires admin role.
    """
    repo = _get_user_repo()
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permissions = await repo.get_user_permissions(user_id)

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
    repo = _get_user_repo()
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate permission level
    if perm_request.permission_level not in ("read", "write", "admin"):
        raise HTTPException(
            status_code=400,
            detail="Permission level must be 'read', 'write', or 'admin'",
        )

    # Grant permission
    permission_id = str(uuid.uuid4())
    permission = await repo.grant_permission(
        permission_id=permission_id,
        user_id=user_id,
        service_account_id=perm_request.service_account_id,
        permission_level=perm_request.permission_level,
        granted_by=admin.id,
    )

    # Log the action
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="grant_permission",
        user_id=admin.id,
        resource_type="permission",
        resource_id=permission_id,
        details=json.dumps({
            "target_user": user_id,
            "service_account_id": perm_request.service_account_id,
            "permission_level": perm_request.permission_level,
        }),
        ip_address=_get_client_ip(request),
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
    repo = _get_user_repo()
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Revoke permission
    revoked = await repo.revoke_permission(user_id, service_account_id)

    if not revoked:
        raise HTTPException(status_code=404, detail="Permission not found")

    # Log the action
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="revoke_permission",
        user_id=admin.id,
        resource_type="permission",
        details=json.dumps({
            "target_user": user_id,
            "service_account_id": service_account_id,
        }),
        ip_address=_get_client_ip(request),
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
    repo = _get_user_repo()
    logs = await repo.get_audit_logs(
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
    repo = _get_user_repo()
    settings = await repo.get_all_settings()
    return settings


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
    repo = _get_user_repo()

    # Validate certain settings
    if key == "audit_retention_days":
        try:
            days = int(setting_update.value)
            if days not in (0, 30, 60, 90, 120):
                raise ValueError("Invalid retention period")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Audit retention must be 0 (unlimited), 30, 60, 90, or 120 days",
            )

    if key == "multi_user_enabled":
        if setting_update.value not in ("0", "1"):
            raise HTTPException(
                status_code=400,
                detail="multi_user_enabled must be '0' or '1'",
            )

    # Update setting
    await repo.set_setting(key, setting_update.value, updated_by=admin.id)

    # Log the action
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="update_setting",
        user_id=admin.id,
        resource_type="setting",
        resource_id=key,
        details=json.dumps({"value": setting_update.value}),
        ip_address=_get_client_ip(request),
    )

    return {"status": "success", "key": key, "value": setting_update.value}


# ==================== User Stats Endpoint ====================

@router.get("/stats")
async def get_admin_stats(
    admin: User = Depends(require_admin),
):
    """Get admin dashboard stats.

    Requires admin role. Returns counts of users, sessions, etc.
    """
    repo = _get_user_repo()

    users = await repo.get_users()
    active_users = [u for u in users if u.is_active]
    admin_users = [u for u in users if u.role == "admin"]

    return {
        "total_users": len(users),
        "active_users": len(active_users),
        "admin_users": len(admin_users),
        "multi_user_enabled": await repo.is_multi_user_enabled(),
    }


# ==================== Password Reset Endpoint ====================

@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Reset a user's password.

    Requires admin role. Generates a new random password.
    The new password is returned and should be shared securely.
    """
    repo = _get_user_repo()
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate new password
    new_password = generate_password()
    password_hash = hash_password(new_password)

    # Update password
    await repo.update_user(user_id=user_id, password_hash=password_hash)

    # Log the action
    await repo.log_audit(
        audit_id=str(uuid.uuid4()),
        action="reset_password",
        user_id=admin.id,
        resource_type="user",
        resource_id=user_id,
        details=json.dumps({"email": user.email}),
        ip_address=_get_client_ip(request),
    )

    return {
        "status": "success",
        "user_id": user_id,
        "email": user.email,
        "new_password": new_password,  # Only shown once!
        "message": "Password reset. Share the new password securely.",
    }
