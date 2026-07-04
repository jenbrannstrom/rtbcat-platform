"""Postgres repository for hashed outside-agent API tokens."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_execute, pg_query, pg_query_one


class AgentTokensRepository:
    """SQL-only repository for agent API tokens."""

    async def create_token(
        self,
        *,
        token_id: str,
        name: str,
        token_hash: str,
        token_prefix: str,
        user_id: str,
        buyer_id: str | None,
        scopes: str,
        expires_at: str,
        created_by: str | None,
    ) -> dict[str, Any]:
        await pg_execute(
            """
            INSERT INTO agent_api_tokens (
                id, name, token_hash, token_prefix, user_id, buyer_id, scopes,
                expires_at, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                token_id,
                name,
                token_hash,
                token_prefix,
                user_id,
                buyer_id,
                scopes,
                expires_at,
                created_by,
            ),
        )
        row = await self.get_token_by_id(token_id)
        if row is None:
            raise RuntimeError("Failed to load agent token after insert")
        return row

    async def get_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        return await pg_query_one(
            """
            SELECT
                t.id, t.name, t.token_prefix, t.user_id, t.buyer_id, t.scopes,
                t.is_active, t.expires_at, t.last_used_at, t.created_at,
                t.created_by, t.revoked_at, t.revoked_by,
                u.email AS user_email,
                u.display_name AS user_display_name,
                u.role AS user_role,
                u.is_active AS user_is_active
            FROM agent_api_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = %s
            """,
            (token_hash,),
        )

    async def get_token_by_id(self, token_id: str) -> dict[str, Any] | None:
        return await pg_query_one(
            """
            SELECT
                t.id, t.name, t.token_prefix, t.user_id, t.buyer_id, t.scopes,
                t.is_active, t.expires_at, t.last_used_at, t.last_used_ip,
                t.last_used_user_agent, t.created_at, t.created_by,
                t.revoked_at, t.revoked_by,
                u.email AS user_email,
                u.display_name AS user_display_name,
                u.role AS user_role,
                u.is_active AS user_is_active
            FROM agent_api_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.id = %s
            """,
            (token_id,),
        )

    async def list_tokens(
        self,
        *,
        user_id: str | None = None,
        buyer_id: str | None = None,
        active_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if user_id:
            conditions.append("t.user_id = %s")
            params.append(user_id)
        if buyer_id:
            conditions.append("t.buyer_id = %s")
            params.append(buyer_id)
        if active_only:
            conditions.append("t.is_active = TRUE AND t.revoked_at IS NULL")

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        params.append(max(1, min(limit, 500)))
        return await pg_query(
            f"""
            SELECT
                t.id, t.name, t.token_prefix, t.user_id, t.buyer_id, t.scopes,
                t.is_active, t.expires_at, t.last_used_at, t.created_at,
                t.created_by, t.revoked_at, t.revoked_by,
                u.email AS user_email,
                u.display_name AS user_display_name
            FROM agent_api_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE {where_clause}
            ORDER BY t.created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def mark_token_used(
        self,
        *,
        token_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        await pg_execute(
            """
            UPDATE agent_api_tokens
            SET last_used_at = NOW(),
                last_used_ip = %s,
                last_used_user_agent = %s
            WHERE id = %s
            """,
            (ip_address, user_agent, token_id),
        )

    async def revoke_token(
        self,
        *,
        token_id: str,
        revoked_by: str | None,
    ) -> bool:
        rowcount = await pg_execute(
            """
            UPDATE agent_api_tokens
            SET is_active = FALSE,
                revoked_at = NOW(),
                revoked_by = %s
            WHERE id = %s
              AND revoked_at IS NULL
            """,
            (revoked_by, token_id),
        )
        return rowcount > 0

    async def cleanup_expired_tokens(self) -> int:
        """Revoke tokens whose expiry has passed but were never revoked.

        Returns the number of rows revoked. ``revoked_by`` is left NULL to mark
        these as system-initiated rather than attributed to a user. The
        ``::timestamptz`` cast keeps the comparison correct whether ``expires_at``
        is stored as timestamptz or as an ISO-8601 string (the service writes
        ``expires_at.isoformat()`` on insert).
        """
        return await pg_execute(
            """
            UPDATE agent_api_tokens
            SET is_active = FALSE,
                revoked_at = NOW()
            WHERE revoked_at IS NULL
              AND expires_at::timestamptz < NOW()
            """,
        )
