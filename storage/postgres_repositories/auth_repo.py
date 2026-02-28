"""Postgres repository for users and sessions (SQL only)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


class AuthRepository:
    """SQL-only repository for user authentication and sessions."""

    # ==================== User Methods ====================

    async def create_user(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        role: str = "read",
        default_language: str = "en",
    ) -> dict[str, Any]:
        """Create a new user."""
        now = datetime.utcnow().isoformat()
        await pg_execute(
            """
            INSERT INTO users (id, email, display_name, role, is_active, created_at, default_language)
            VALUES (%s, %s, %s, %s, 1, %s, %s)
            """,
            (user_id, email, display_name, role, now, default_language),
        )
        return {
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "role": role,
            "is_active": True,
            "created_at": now,
            "default_language": default_language,
        }

    async def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        """Get a user by ID."""
        return await pg_query_one(
            """
            SELECT id, email, display_name, role, is_active,
                   created_at, updated_at, last_login_at, default_language
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )

    async def get_user_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Get a user by email address."""
        return await pg_query_one(
            """
            SELECT id, email, display_name, role, is_active,
                   created_at, updated_at, last_login_at, default_language
            FROM users
            WHERE email = %s
            """,
            (email,),
        )

    async def get_users(
        self,
        active_only: bool = False,
        role: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get all users, optionally filtered."""
        conditions = []
        params: list[Any] = []

        if active_only:
            conditions.append("is_active = 1")
        if role:
            conditions.append("role = %s")
            params.append(role)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        return await pg_query(
            f"""
            SELECT id, email, display_name, role, is_active,
                   created_at, updated_at, last_login_at, default_language
            FROM users
            WHERE {where_clause}
            ORDER BY created_at DESC
            """,
            tuple(params) if params else None,
        )

    async def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        default_language: Optional[str] = None,
    ) -> bool:
        """Update a user's fields. Returns True if user was updated."""
        updates = []
        params: list[Any] = []

        if display_name is not None:
            updates.append("display_name = %s")
            params.append(display_name)
        if role is not None:
            updates.append("role = %s")
            params.append(role)
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(is_active)
        if default_language is not None:
            updates.append("default_language = %s")
            params.append(default_language)

        if not updates:
            return False

        updates.append("updated_at = %s")
        params.append(datetime.utcnow().isoformat())
        params.append(user_id)

        rowcount = await pg_execute(
            f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = %s
            """,
            tuple(params),
        )
        return rowcount > 0

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        now = datetime.utcnow().isoformat()
        await pg_execute(
            "UPDATE users SET last_login_at = %s WHERE id = %s",
            (now, user_id),
        )

    async def count_users(self) -> int:
        """Count total number of users."""
        row = await pg_query_one("SELECT COUNT(*) as cnt FROM users")
        return row["cnt"] if row else 0

    async def get_user_password_hash(self, user_id: str) -> Optional[str]:
        """Get the stored password hash for a user, if any."""
        row = await pg_query_one(
            "SELECT password_hash FROM user_passwords WHERE user_id = %s",
            (user_id,),
        )
        return row["password_hash"] if row else None

    async def set_user_password_hash(self, user_id: str, password_hash: str) -> None:
        """Insert or update a user's password hash."""
        await pg_execute(
            """
            INSERT INTO user_passwords (user_id, password_hash, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                updated_at = NOW()
            """,
            (user_id, password_hash),
        )

    # ==================== Session Methods ====================

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        duration_days: int = 30,
    ) -> dict[str, Any]:
        """Create a new session for a user."""
        now = datetime.utcnow()
        expires_at = now + timedelta(days=duration_days)

        await pg_execute(
            """
            INSERT INTO user_sessions (id, user_id, created_at, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
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

        return {
            "id": session_id,
            "user_id": user_id,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get a session by ID."""
        return await pg_query_one(
            """
            SELECT id, user_id, created_at, expires_at, ip_address, user_agent
            FROM user_sessions
            WHERE id = %s
            """,
            (session_id,),
        )

    async def validate_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Validate a session and return the associated user if valid."""
        now = datetime.utcnow().isoformat()
        return await pg_query_one(
            """
            SELECT u.id, u.email, u.display_name, u.role, u.is_active,
                   u.created_at, u.updated_at, u.last_login_at, u.default_language
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.id = %s AND s.expires_at > %s AND u.is_active = 1
            """,
            (session_id, now),
        )

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session (logout). Returns True if deleted."""
        rowcount = await pg_execute(
            "DELETE FROM user_sessions WHERE id = %s",
            (session_id,),
        )
        return rowcount > 0

    async def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user. Returns count deleted."""
        return await pg_execute(
            "DELETE FROM user_sessions WHERE user_id = %s",
            (user_id,),
        )

    async def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions. Returns count deleted."""
        now = datetime.utcnow().isoformat()
        return await pg_execute(
            "DELETE FROM user_sessions WHERE expires_at < %s",
            (now,),
        )
