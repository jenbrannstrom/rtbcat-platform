"""Business logic for authentication, authorization, and audit logging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from storage.postgres_repositories.auth_repo import AuthRepository
from storage.postgres_repositories.permissions_repo import PermissionsRepository
from storage.postgres_repositories.audit_repo import AuditRepository


@dataclass
class User:
    """User record for authentication."""

    id: str
    email: str
    display_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_login_at: Optional[str] = None
    default_language: Optional[str] = None


@dataclass
class UserSession:
    """User session for cookie-based authentication."""

    id: str
    user_id: str
    created_at: str
    expires_at: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class UserPermission:
    """User permission for service account access."""

    id: str
    user_id: str
    service_account_id: str
    permission_level: str = "read"
    granted_by: Optional[str] = None
    granted_at: Optional[str] = None


@dataclass
class AuditLogEntry:
    """Audit log entry for tracking user actions."""

    id: str
    action: str
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[str] = None


class AuthService:
    """Service layer for authentication, authorization, and audit logging."""

    def __init__(
        self,
        auth_repo: AuthRepository | None = None,
        permissions_repo: PermissionsRepository | None = None,
        audit_repo: AuditRepository | None = None,
    ) -> None:
        self._auth = auth_repo or AuthRepository()
        self._perms = permissions_repo or PermissionsRepository()
        self._audit = audit_repo or AuditRepository()

    # ==================== User Methods ====================

    async def create_user(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        role: str = "user",
        default_language: str = "en",
    ) -> User:
        """Create a new user."""
        row = await self._auth.create_user(
            user_id=user_id,
            email=email,
            display_name=display_name,
            role=role,
            default_language=default_language,
        )
        return self._row_to_user(row)

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        row = await self._auth.get_user_by_id(user_id)
        return self._row_to_user(row) if row else None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address."""
        row = await self._auth.get_user_by_email(email)
        return self._row_to_user(row) if row else None

    async def get_users(
        self,
        active_only: bool = False,
        role: Optional[str] = None,
    ) -> list[User]:
        """Get all users, optionally filtered."""
        rows = await self._auth.get_users(active_only=active_only, role=role)
        return [self._row_to_user(r) for r in rows]

    async def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        default_language: Optional[str] = None,
    ) -> bool:
        """Update a user's fields."""
        return await self._auth.update_user(
            user_id=user_id,
            display_name=display_name,
            role=role,
            is_active=is_active,
            default_language=default_language,
        )

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        await self._auth.update_last_login(user_id)

    async def count_users(self) -> int:
        """Count total number of users."""
        return await self._auth.count_users()

    async def get_user_password_hash(self, user_id: str) -> Optional[str]:
        """Get a user's password hash, if set."""
        return await self._auth.get_user_password_hash(user_id)

    async def set_user_password_hash(self, user_id: str, password_hash: str) -> None:
        """Create or update a user's password hash."""
        await self._auth.set_user_password_hash(user_id, password_hash)

    # ==================== Session Methods ====================

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        duration_days: int = 30,
    ) -> UserSession:
        """Create a new session for a user."""
        row = await self._auth.create_session(
            session_id=session_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            duration_days=duration_days,
        )
        return self._row_to_session(row)

    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID."""
        row = await self._auth.get_session(session_id)
        return self._row_to_session(row) if row else None

    async def validate_session(self, session_id: str) -> Optional[User]:
        """Validate a session and return the associated user if valid."""
        row = await self._auth.validate_session(session_id)
        return self._row_to_user(row) if row else None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session (logout)."""
        return await self._auth.delete_session(session_id)

    async def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user."""
        return await self._auth.delete_user_sessions(user_id)

    async def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions."""
        return await self._auth.cleanup_expired_sessions()

    # ==================== Permission Methods ====================

    async def grant_permission(
        self,
        permission_id: str,
        user_id: str,
        service_account_id: str,
        permission_level: str = "read",
        granted_by: Optional[str] = None,
    ) -> UserPermission:
        """Grant a user access to a service account."""
        row = await self._perms.grant_permission(
            permission_id=permission_id,
            user_id=user_id,
            service_account_id=service_account_id,
            permission_level=permission_level,
            granted_by=granted_by,
        )
        return self._row_to_permission(row)

    async def revoke_permission(
        self,
        user_id: str,
        service_account_id: str,
    ) -> bool:
        """Revoke a user's access to a service account."""
        return await self._perms.revoke_permission(user_id, service_account_id)

    async def get_user_permissions(self, user_id: str) -> list[UserPermission]:
        """Get all permissions for a user."""
        rows = await self._perms.get_user_permissions(user_id)
        return [self._row_to_permission(r) for r in rows]

    async def get_user_service_account_ids(
        self,
        user_id: str,
        min_permission_level: str = "read",
    ) -> list[str]:
        """Get service account IDs the user can access."""
        return await self._perms.get_user_service_account_ids(user_id, min_permission_level)

    async def check_user_permission(
        self,
        user_id: str,
        service_account_id: str,
        required_level: str = "read",
    ) -> bool:
        """Check if a user has the required permission for a service account."""
        return await self._perms.check_user_permission(user_id, service_account_id, required_level)

    # ==================== Audit Log Methods ====================

    async def log_audit(
        self,
        audit_id: str,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLogEntry:
        """Create an audit log entry."""
        row = await self._audit.log_audit(
            audit_id=audit_id,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        return self._row_to_audit_entry(row)

    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        since_days: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """Get audit log entries with optional filters."""
        rows = await self._audit.get_audit_logs(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            since_days=since_days,
            limit=limit,
            offset=offset,
        )
        return [self._row_to_audit_entry(r) for r in rows]

    async def cleanup_old_audit_logs(self, retention_days: int) -> int:
        """Delete audit logs older than retention period."""
        return await self._audit.cleanup_old_audit_logs(retention_days)

    # ==================== Settings Methods ====================

    async def get_setting(self, key: str) -> Optional[str]:
        """Get a system setting value."""
        return await self._audit.get_setting(key)

    async def set_setting(
        self,
        key: str,
        value: str,
        updated_by: Optional[str] = None,
    ) -> None:
        """Set a system setting value."""
        await self._audit.set_setting(key, value, updated_by)

    async def get_all_settings(self) -> dict[str, str]:
        """Get all system settings."""
        return await self._audit.get_all_settings()

    async def is_multi_user_enabled(self) -> bool:
        """Check if multi-user mode is enabled."""
        return await self._audit.is_multi_user_enabled()

    # ==================== Row Conversion Helpers ====================

    @staticmethod
    def _row_to_user(row: dict[str, Any]) -> User:
        """Convert a database row to a User dataclass."""
        return User(
            id=row["id"],
            email=row["email"],
            display_name=row.get("display_name"),
            role=row.get("role", "user"),
            is_active=row.get("is_active", True),
            created_at=str(row["created_at"]) if row.get("created_at") else None,
            updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
            last_login_at=str(row["last_login_at"]) if row.get("last_login_at") else None,
            default_language=row.get("default_language"),
        )

    @staticmethod
    def _row_to_session(row: dict[str, Any]) -> UserSession:
        """Convert a database row to a UserSession dataclass."""
        return UserSession(
            id=row["id"],
            user_id=row["user_id"],
            created_at=str(row["created_at"]),
            expires_at=str(row["expires_at"]),
            ip_address=row.get("ip_address"),
            user_agent=row.get("user_agent"),
        )

    @staticmethod
    def _row_to_permission(row: dict[str, Any]) -> UserPermission:
        """Convert a database row to a UserPermission dataclass."""
        return UserPermission(
            id=row["id"],
            user_id=row["user_id"],
            service_account_id=row["service_account_id"],
            permission_level=row.get("permission_level", "read"),
            granted_by=row.get("granted_by"),
            granted_at=str(row["granted_at"]) if row.get("granted_at") else None,
        )

    @staticmethod
    def _row_to_audit_entry(row: dict[str, Any]) -> AuditLogEntry:
        """Convert a database row to an AuditLogEntry dataclass."""
        return AuditLogEntry(
            id=row["id"],
            action=row["action"],
            user_id=row.get("user_id"),
            resource_type=row.get("resource_type"),
            resource_id=row.get("resource_id"),
            details=row.get("details"),
            ip_address=row.get("ip_address"),
            created_at=str(row["created_at"]) if row.get("created_at") else None,
        )
