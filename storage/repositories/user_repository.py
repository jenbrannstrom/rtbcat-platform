"""User repository for authentication and authorization.

This module provides database operations for users, sessions, permissions,
rate limiting, and audit logging.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from .base import BaseRepository


@dataclass
class User:
    """User record for authentication.

    Attributes:
        id: UUID for the user.
        email: Unique email address.
        password_hash: bcrypt password hash.
        display_name: User-friendly display name.
        role: User role ('admin' or 'user').
        is_active: Whether the account is active.
        created_at: Account creation timestamp.
        updated_at: Last update timestamp.
        last_login_at: Last successful login timestamp.
    """

    id: str
    email: str
    password_hash: str
    display_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_login_at: Optional[str] = None


@dataclass
class UserSession:
    """User session for cookie-based authentication.

    Attributes:
        id: Session token (UUID).
        user_id: Foreign key to users table.
        created_at: Session creation timestamp.
        expires_at: Session expiry timestamp.
        ip_address: Client IP address.
        user_agent: Client user agent string.
    """

    id: str
    user_id: str
    created_at: str
    expires_at: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class UserPermission:
    """User permission for service account access.

    Attributes:
        id: Permission record UUID.
        user_id: Foreign key to users table.
        service_account_id: Foreign key to service_accounts table.
        permission_level: Access level ('read', 'write', 'admin').
        granted_by: User ID who granted this permission.
        granted_at: When permission was granted.
    """

    id: str
    user_id: str
    service_account_id: str
    permission_level: str = "read"
    granted_by: Optional[str] = None
    granted_at: Optional[str] = None


@dataclass
class AuditLogEntry:
    """Audit log entry for tracking user actions.

    Attributes:
        id: Audit log entry UUID.
        user_id: User who performed the action.
        action: Action type (e.g., 'login', 'logout', 'create_user').
        resource_type: Type of resource affected.
        resource_id: ID of the resource affected.
        details: Additional details as JSON string.
        ip_address: Client IP address.
        created_at: When the action occurred.
    """

    id: str
    action: str
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[str] = None


class UserRepository(BaseRepository[User]):
    """Repository for user authentication and authorization.

    Manages users, sessions, permissions, rate limiting, and audit logging.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        super().__init__(db_path)

    # ==================== User Methods ====================

    async def create_user(
        self,
        user_id: str,
        email: str,
        password_hash: str,
        display_name: Optional[str] = None,
        role: str = "user",
    ) -> User:
        """Create a new user.

        Args:
            user_id: UUID for the new user.
            email: User's email address.
            password_hash: bcrypt password hash.
            display_name: Optional display name.
            role: User role ('admin' or 'user').

        Returns:
            Created User object.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            now = datetime.utcnow().isoformat()

            def _create():
                conn.execute(
                    """
                    INSERT INTO users (id, email, password_hash, display_name, role, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (user_id, email, password_hash, display_name, role, now),
                )
                conn.commit()

            await loop.run_in_executor(None, _create)

        return User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            is_active=True,
            created_at=now,
        )

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID.

        Args:
            user_id: User UUID.

        Returns:
            User object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT id, email, password_hash, display_name, role,
                           is_active, created_at, updated_at, last_login_at
                    FROM users
                    WHERE id = ?
                    """,
                    (user_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return User(
                    id=row[0],
                    email=row[1],
                    password_hash=row[2],
                    display_name=row[3],
                    role=row[4],
                    is_active=bool(row[5]),
                    created_at=row[6],
                    updated_at=row[7],
                    last_login_at=row[8],
                )
            return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address.

        Args:
            email: User's email address.

        Returns:
            User object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT id, email, password_hash, display_name, role,
                           is_active, created_at, updated_at, last_login_at
                    FROM users
                    WHERE email = ?
                    """,
                    (email,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return User(
                    id=row[0],
                    email=row[1],
                    password_hash=row[2],
                    display_name=row[3],
                    role=row[4],
                    is_active=bool(row[5]),
                    created_at=row[6],
                    updated_at=row[7],
                    last_login_at=row[8],
                )
            return None

    async def get_users(
        self,
        active_only: bool = False,
        role: Optional[str] = None,
    ) -> list[User]:
        """Get all users, optionally filtered.

        Args:
            active_only: If True, only return active users.
            role: Filter by role ('admin' or 'user').

        Returns:
            List of User objects.
        """
        conditions = []
        params: list[Any] = []

        if active_only:
            conditions.append("is_active = 1")
        if role:
            conditions.append("role = ?")
            params.append(role)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT id, email, password_hash, display_name, role,
                           is_active, created_at, updated_at, last_login_at
                    FROM users
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    """,
                    params,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            User(
                id=row[0],
                email=row[1],
                password_hash=row[2],
                display_name=row[3],
                role=row[4],
                is_active=bool(row[5]),
                created_at=row[6],
                updated_at=row[7],
                last_login_at=row[8],
            )
            for row in rows
        ]

    async def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        password_hash: Optional[str] = None,
    ) -> bool:
        """Update a user's fields.

        Args:
            user_id: User UUID.
            display_name: New display name.
            role: New role.
            is_active: New active status.
            password_hash: New password hash.

        Returns:
            True if user was updated, False if not found.
        """
        updates = []
        params: list[Any] = []

        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if password_hash is not None:
            updates.append("password_hash = ?")
            params.append(password_hash)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(user_id)

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _update():
                cursor = conn.execute(
                    f"""
                    UPDATE users
                    SET {', '.join(updates)}
                    WHERE id = ?
                    """,
                    params,
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _update)

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp.

        Args:
            user_id: User UUID.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            now = datetime.utcnow().isoformat()

            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    "UPDATE users SET last_login_at = ? WHERE id = ?",
                    (now, user_id),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def count_users(self) -> int:
        """Count total number of users.

        Returns:
            Total user count.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _count():
                cursor = conn.execute("SELECT COUNT(*) FROM users")
                return cursor.fetchone()[0]

            return await loop.run_in_executor(None, _count)

    # ==================== Session Methods ====================

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        duration_days: int = 30,
    ) -> UserSession:
        """Create a new session for a user.

        Args:
            session_id: UUID for the session token.
            user_id: User UUID.
            ip_address: Client IP address.
            user_agent: Client user agent.
            duration_days: Session duration in days (default 30).

        Returns:
            Created UserSession object.
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(days=duration_days)

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _create():
                conn.execute(
                    """
                    INSERT INTO user_sessions (id, user_id, created_at, expires_at, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        user_id,
                        now.isoformat(),
                        expires_at.isoformat(),
                        ip_address,
                        user_agent,
                    ),
                )
                conn.commit()

            await loop.run_in_executor(None, _create)

        return UserSession(
            id=session_id,
            user_id=user_id,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID.

        Args:
            session_id: Session token.

        Returns:
            UserSession object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT id, user_id, created_at, expires_at, ip_address, user_agent
                    FROM user_sessions
                    WHERE id = ?
                    """,
                    (session_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return UserSession(
                    id=row[0],
                    user_id=row[1],
                    created_at=row[2],
                    expires_at=row[3],
                    ip_address=row[4],
                    user_agent=row[5],
                )
            return None

    async def validate_session(self, session_id: str) -> Optional[User]:
        """Validate a session and return the associated user.

        Checks if the session exists and hasn't expired.

        Args:
            session_id: Session token.

        Returns:
            User object if session is valid, None otherwise.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            now = datetime.utcnow().isoformat()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT u.id, u.email, u.password_hash, u.display_name, u.role,
                           u.is_active, u.created_at, u.updated_at, u.last_login_at
                    FROM user_sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.id = ? AND s.expires_at > ? AND u.is_active = 1
                    """,
                    (session_id, now),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return User(
                    id=row[0],
                    email=row[1],
                    password_hash=row[2],
                    display_name=row[3],
                    role=row[4],
                    is_active=bool(row[5]),
                    created_at=row[6],
                    updated_at=row[7],
                    last_login_at=row[8],
                )
            return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session (logout).

        Args:
            session_id: Session token.

        Returns:
            True if session was deleted, False if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _delete():
                cursor = conn.execute(
                    "DELETE FROM user_sessions WHERE id = ?",
                    (session_id,),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _delete)

    async def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user.

        Args:
            user_id: User UUID.

        Returns:
            Number of sessions deleted.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _delete():
                cursor = conn.execute(
                    "DELETE FROM user_sessions WHERE user_id = ?",
                    (user_id,),
                )
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _delete)

    async def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions.

        Returns:
            Number of sessions deleted.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            now = datetime.utcnow().isoformat()

            def _cleanup():
                cursor = conn.execute(
                    "DELETE FROM user_sessions WHERE expires_at < ?",
                    (now,),
                )
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _cleanup)

    # ==================== Permission Methods ====================

    async def grant_permission(
        self,
        permission_id: str,
        user_id: str,
        service_account_id: str,
        permission_level: str = "read",
        granted_by: Optional[str] = None,
    ) -> UserPermission:
        """Grant a user access to a service account.

        Args:
            permission_id: UUID for the permission.
            user_id: User UUID.
            service_account_id: Service account UUID.
            permission_level: Access level ('read', 'write', 'admin').
            granted_by: User who granted this permission.

        Returns:
            Created UserPermission object.
        """
        now = datetime.utcnow().isoformat()

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _grant():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_service_account_permissions
                    (id, user_id, service_account_id, permission_level, granted_by, granted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        permission_id,
                        user_id,
                        service_account_id,
                        permission_level,
                        granted_by,
                        now,
                    ),
                )
                conn.commit()

            await loop.run_in_executor(None, _grant)

        return UserPermission(
            id=permission_id,
            user_id=user_id,
            service_account_id=service_account_id,
            permission_level=permission_level,
            granted_by=granted_by,
            granted_at=now,
        )

    async def revoke_permission(
        self,
        user_id: str,
        service_account_id: str,
    ) -> bool:
        """Revoke a user's access to a service account.

        Args:
            user_id: User UUID.
            service_account_id: Service account UUID.

        Returns:
            True if permission was revoked, False if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _revoke():
                cursor = conn.execute(
                    """
                    DELETE FROM user_service_account_permissions
                    WHERE user_id = ? AND service_account_id = ?
                    """,
                    (user_id, service_account_id),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _revoke)

    async def get_user_permissions(self, user_id: str) -> list[UserPermission]:
        """Get all permissions for a user.

        Args:
            user_id: User UUID.

        Returns:
            List of UserPermission objects.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT id, user_id, service_account_id, permission_level, granted_by, granted_at
                    FROM user_service_account_permissions
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            UserPermission(
                id=row[0],
                user_id=row[1],
                service_account_id=row[2],
                permission_level=row[3],
                granted_by=row[4],
                granted_at=row[5],
            )
            for row in rows
        ]

    async def get_user_service_account_ids(
        self,
        user_id: str,
        min_permission_level: str = "read",
    ) -> list[str]:
        """Get service account IDs the user can access.

        Args:
            user_id: User UUID.
            min_permission_level: Minimum required permission level.

        Returns:
            List of service account IDs.
        """
        # Permission levels in order
        levels = ["read", "write", "admin"]
        min_index = levels.index(min_permission_level) if min_permission_level in levels else 0

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT service_account_id, permission_level
                    FROM user_service_account_permissions
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        # Filter by permission level
        result = []
        for row in rows:
            sa_id, level = row[0], row[1]
            level_index = levels.index(level) if level in levels else -1
            if level_index >= min_index:
                result.append(sa_id)

        return result

    async def check_user_permission(
        self,
        user_id: str,
        service_account_id: str,
        required_level: str = "read",
    ) -> bool:
        """Check if a user has the required permission for a service account.

        Args:
            user_id: User UUID.
            service_account_id: Service account UUID.
            required_level: Required permission level.

        Returns:
            True if user has required permission.
        """
        levels = ["read", "write", "admin"]
        required_index = levels.index(required_level) if required_level in levels else 0

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT permission_level
                    FROM user_service_account_permissions
                    WHERE user_id = ? AND service_account_id = ?
                    """,
                    (user_id, service_account_id),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                user_level = row[0]
                user_index = levels.index(user_level) if user_level in levels else -1
                return user_index >= required_index
            return False

    # ==================== Rate Limiting Methods ====================

    async def record_login_attempt(
        self,
        email: str,
        ip_address: Optional[str] = None,
        success: bool = False,
    ) -> None:
        """Record a login attempt for rate limiting.

        Args:
            email: Email address used.
            ip_address: Client IP address.
            success: Whether the attempt was successful.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _record():
                conn.execute(
                    """
                    INSERT INTO login_attempts (email, ip_address, success)
                    VALUES (?, ?, ?)
                    """,
                    (email, ip_address, 1 if success else 0),
                )
                conn.commit()

            await loop.run_in_executor(None, _record)

    async def get_failed_login_count(
        self,
        email: str,
        since_minutes: int = 60,
    ) -> int:
        """Get count of failed login attempts for an email.

        Args:
            email: Email address.
            since_minutes: Time window in minutes.

        Returns:
            Number of failed attempts.
        """
        since = (datetime.utcnow() - timedelta(minutes=since_minutes)).isoformat()

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _count():
                cursor = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM login_attempts
                    WHERE email = ? AND success = 0 AND attempted_at > ?
                    """,
                    (email, since),
                )
                return cursor.fetchone()[0]

            return await loop.run_in_executor(None, _count)

    async def is_locked_out(
        self,
        email: str,
        max_attempts: int = 5,
        lockout_minutes: int = 60,
    ) -> bool:
        """Check if an email is locked out due to failed attempts.

        Args:
            email: Email address.
            max_attempts: Maximum allowed attempts.
            lockout_minutes: Lockout window in minutes.

        Returns:
            True if locked out.
        """
        count = await self.get_failed_login_count(email, lockout_minutes)
        return count >= max_attempts

    async def cleanup_old_login_attempts(self, older_than_days: int = 7) -> int:
        """Delete old login attempt records.

        Args:
            older_than_days: Delete attempts older than this.

        Returns:
            Number of records deleted.
        """
        cutoff = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat()

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _cleanup():
                cursor = conn.execute(
                    "DELETE FROM login_attempts WHERE attempted_at < ?",
                    (cutoff,),
                )
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _cleanup)

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
        """Create an audit log entry.

        Args:
            audit_id: UUID for the audit entry.
            action: Action type.
            user_id: User who performed the action.
            resource_type: Type of resource affected.
            resource_id: ID of the resource affected.
            details: Additional details (JSON string).
            ip_address: Client IP address.

        Returns:
            Created AuditLogEntry object.
        """
        now = datetime.utcnow().isoformat()

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _log():
                conn.execute(
                    """
                    INSERT INTO audit_log (id, user_id, action, resource_type, resource_id, details, ip_address, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        audit_id,
                        user_id,
                        action,
                        resource_type,
                        resource_id,
                        details,
                        ip_address,
                        now,
                    ),
                )
                conn.commit()

            await loop.run_in_executor(None, _log)

        return AuditLogEntry(
            id=audit_id,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            created_at=now,
        )

    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        since_days: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """Get audit log entries with optional filters.

        Args:
            user_id: Filter by user.
            action: Filter by action type.
            resource_type: Filter by resource type.
            since_days: Only include entries from last N days.
            limit: Maximum entries to return.
            offset: Offset for pagination.

        Returns:
            List of AuditLogEntry objects.
        """
        conditions = []
        params: list[Any] = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)
        if since_days:
            since = (datetime.utcnow() - timedelta(days=since_days)).isoformat()
            conditions.append("created_at > ?")
            params.append(since)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT id, user_id, action, resource_type, resource_id, details, ip_address, created_at
                    FROM audit_log
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    params,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            AuditLogEntry(
                id=row[0],
                user_id=row[1],
                action=row[2],
                resource_type=row[3],
                resource_id=row[4],
                details=row[5],
                ip_address=row[6],
                created_at=row[7],
            )
            for row in rows
        ]

    async def cleanup_old_audit_logs(self, retention_days: int) -> int:
        """Delete audit logs older than retention period.

        Args:
            retention_days: Delete logs older than this. 0 = keep forever.

        Returns:
            Number of records deleted.
        """
        if retention_days <= 0:
            return 0

        cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _cleanup():
                cursor = conn.execute(
                    "DELETE FROM audit_log WHERE created_at < ?",
                    (cutoff,),
                )
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _cleanup)

    # ==================== Settings Methods ====================

    async def get_setting(self, key: str) -> Optional[str]:
        """Get a system setting value.

        Args:
            key: Setting key.

        Returns:
            Setting value or None.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    "SELECT value FROM system_settings WHERE key = ?",
                    (key,),
                )
                row = cursor.fetchone()
                return row[0] if row else None

            return await loop.run_in_executor(None, _query)

    async def set_setting(
        self,
        key: str,
        value: str,
        updated_by: Optional[str] = None,
    ) -> None:
        """Set a system setting value.

        Args:
            key: Setting key.
            value: Setting value.
            updated_by: User who updated the setting.
        """
        now = datetime.utcnow().isoformat()

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _update():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO system_settings (key, value, updated_at, updated_by)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, value, now, updated_by),
                )
                conn.commit()

            await loop.run_in_executor(None, _update)

    async def get_all_settings(self) -> dict[str, str]:
        """Get all system settings.

        Returns:
            Dictionary of setting keys to values.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("SELECT key, value FROM system_settings")
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return {row[0]: row[1] for row in rows}

    async def is_multi_user_enabled(self) -> bool:
        """Check if multi-user mode is enabled.

        Returns:
            True if multi-user mode is enabled.
        """
        value = await self.get_setting("multi_user_enabled")
        return value == "1" if value else True
