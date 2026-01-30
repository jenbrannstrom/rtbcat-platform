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
from storage.repositories.user_repository import User

router = APIRouter(prefix="/admin", tags=["Admin"])

ALLOWED_DEFAULT_LANGUAGES = {
    "en",
    "pl",
    "zh",
    "ru",
    "uk",
    "es",
    "da",
    "fr",
    "nl",
    "he",
    "ar",
}


# ==================== Request/Response Models ====================

class CreateUserRequest(BaseModel):
    """Request to create a new user (OAuth2 - no password needed)."""
    email: str = Field(..., description="User email address")
    display_name: Optional[str] = Field(None, description="User display name")
    role: str = Field("user", description="User role (admin or user)")
    default_language: Optional[str] = Field("en", description="Default UI language code")


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


def _validate_default_language(value: Optional[str]) -> Optional[str]:
    """Validate and normalize a default language code."""
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Default language cannot be empty")
    if normalized not in ALLOWED_DEFAULT_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported default language: {normalized}",
        )
    return normalized


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
    """Create a new user (pre-register for OAuth2 login).

    Requires admin role. Users authenticate via Google OAuth2,
    so no password is needed. This pre-creates the user record
    with assigned role before they first log in.
    """
    repo = _get_user_repo()

    # Check if email already exists
    existing = await repo.get_user_by_email(user_request.email.lower().strip())
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")

    # Validate role
    if user_request.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")

    default_language = _validate_default_language(user_request.default_language or "en")

    # Create user (no password - OAuth2 only)
    user_id = str(uuid.uuid4())
    user = await repo.create_user(
        user_id=user_id,
        email=user_request.email.lower().strip(),
        display_name=user_request.display_name,
        role=user_request.role,
        default_language=default_language or "en",
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
        message="User created. They can now log in via Google OAuth2.",
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

    # Update user
    default_language = _validate_default_language(user_update.default_language)
    await repo.update_user(
        user_id=user_id,
        display_name=user_update.display_name,
        role=user_update.role,
        is_active=user_update.is_active,
        default_language=default_language,
    )

    # Log the action
    changes = {}
    if user_update.display_name is not None:
        changes["display_name"] = user_update.display_name
    if user_update.role is not None:
        changes["role"] = user_update.role
    if user_update.is_active is not None:
        changes["is_active"] = user_update.is_active
    if user_update.default_language is not None:
        changes["default_language"] = default_language

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

    from storage.serving_database import db_query

    expected_report_kinds = [
        "catscan-quality",
        "catscan-bidsinauction",
        "catscan-pipeline-geo",
        "catscan-pipeline",
        "catscan-bid-filtering",
    ]

    report_health = {
        "expected_per_seat": len(expected_report_kinds),
        "seats": [],
    }

    seats_rows = await db_query(
        "SELECT DISTINCT buyer_id FROM buyer_seats WHERE active = 1 ORDER BY buyer_id"
    )
    seats = [row["buyer_id"] for row in seats_rows]

    for seat_id in seats:
        latest_rows = await db_query(
            "SELECT MAX(report_date) as latest FROM gmail_import_runs WHERE buyer_account_id = ?",
            (seat_id,),
        )
        latest_date = latest_rows[0]["latest"] if latest_rows else None
        if not latest_date:
            report_health["seats"].append({
                "buyer_id": seat_id,
                "latest_date": None,
                "received": 0,
                "missing": expected_report_kinds,
                "failed": [],
            })
            continue

        report_rows = await db_query(
            "SELECT report_kind, success FROM gmail_import_runs WHERE buyer_account_id = ? AND report_date = ?",
            (seat_id, latest_date),
        )
        received_kinds = set()
        failed_kinds = set()
        for row in report_rows:
            if row["success"]:
                received_kinds.add(row["report_kind"])
            else:
                failed_kinds.add(row["report_kind"])

        missing_kinds = [kind for kind in expected_report_kinds if kind not in received_kinds]
        report_health["seats"].append({
            "buyer_id": seat_id,
            "latest_date": latest_date,
            "received": len(received_kinds),
            "missing": missing_kinds,
            "failed": sorted(failed_kinds),
        })

    return {
        "total_users": len(users),
        "active_users": len(active_users),
        "admin_users": len(admin_users),
        "multi_user_enabled": await repo.is_multi_user_enabled(),
        "report_health": report_health,
    }


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
    from storage.serving_database import db_query

    diagnostics = {}

    # 1. All buyer seats (including inactive)
    seats_rows = await db_query("""
        SELECT bs.buyer_id, bs.bidder_id, bs.display_name, bs.active,
               COALESCE(c.cnt, 0) as creative_count,
               bs.last_synced, bs.service_account_id
        FROM buyer_seats bs
        LEFT JOIN (
            SELECT account_id, COUNT(*) as cnt FROM creatives GROUP BY account_id
        ) c ON c.account_id = bs.buyer_id
        ORDER BY bs.display_name, bs.buyer_id
    """)
    diagnostics["buyer_seats"] = [
        {
            "buyer_id": row["buyer_id"],
            "bidder_id": row["bidder_id"],
            "display_name": row["display_name"],
            "active": bool(row["active"]),
            "creative_count": row["creative_count"],
            "last_synced": row["last_synced"],
            "service_account_id": row["service_account_id"],
        }
        for row in seats_rows
    ]

    # 2. Campaigns with creative_id counts
    campaigns_rows = await db_query("SELECT id, name, creative_ids FROM campaigns LIMIT 20")
    campaigns_data = []
    for row in campaigns_rows:
        creative_ids_raw = row["creative_ids"] or "[]"
        try:
            creative_ids = json.loads(creative_ids_raw) if isinstance(creative_ids_raw, str) else creative_ids_raw
        except Exception:
            creative_ids = []
        campaigns_data.append({
            "id": row["id"],
            "name": row["name"],
            "creative_ids_count": len(creative_ids) if creative_ids else 0,
            "sample_ids": creative_ids[:5] if creative_ids else [],
        })
    diagnostics["campaigns_status"] = {
        "campaigns": campaigns_data,
        "total_campaigns": len(campaigns_data),
    }

    # 3. Thumbnail status summary
    thumbnail_rows = await db_query("""
        SELECT
            format,
            COUNT(*) as total,
            SUM(CASE WHEN thumbnail_url IS NOT NULL AND thumbnail_url != '' THEN 1 ELSE 0 END) as with_thumbnail
        FROM creatives
        GROUP BY format
    """)
    thumbnail_data = {}
    for row in thumbnail_rows:
        fmt = row["format"] or "UNKNOWN"
        thumbnail_data[fmt] = {
            "total": row["total"],
            "with_thumbnail": row["with_thumbnail"],
            "missing_thumbnail": row["total"] - row["with_thumbnail"],
        }
    diagnostics["thumbnail_status"] = thumbnail_data

    # 4. Import history by account
    import_rows = await db_query("""
        SELECT
            buyer_id,
            COUNT(*) as import_count,
            MAX(imported_at) as last_import,
            SUM(rows_imported) as total_records
        FROM import_history
        GROUP BY buyer_id
        ORDER BY last_import DESC
    """)
    diagnostics["import_history"] = [
        {
            "buyer_id": row["buyer_id"],
            "import_count": row["import_count"],
            "last_import": str(row["last_import"]) if row["last_import"] else None,
            "total_records": row["total_records"],
        }
        for row in import_rows
    ]

    # 5. Creative ID type check
    id_rows = await db_query("SELECT id, pg_typeof(id)::text as type, account_id FROM creatives LIMIT 5")
    diagnostics["creative_id_samples"] = [
        {"id": row["id"], "type": row["type"], "account_id": row["account_id"]}
        for row in id_rows
    ]

    return diagnostics


@router.post("/diagnostics/fix-inactive-seats")
async def fix_inactive_seats(
    admin: User = Depends(require_admin),
):
    """Activate all inactive buyer seats.

    Use this to fix Issue 2: Missing third account showing only 2 of 3 accounts.
    Sets active=1 for all buyer_seats entries.
    """
    from storage.serving_database import db_query, db_execute

    # Count inactive before
    count_rows = await db_query("SELECT COUNT(*) as cnt FROM buyer_seats WHERE active = 0")
    inactive_count = count_rows[0]["cnt"] if count_rows else 0

    # Activate all
    await db_execute("UPDATE buyer_seats SET active = 1 WHERE active = 0")

    return {
        "status": "success",
        "message": f"Activated {inactive_count} buyer seat(s)",
        "seats_activated": inactive_count,
    }
