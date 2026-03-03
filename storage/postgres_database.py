"""
PostgreSQL database access module for Cat-Scan.

This module provides thread-safe PostgreSQL access for FastAPI's async environment.

Usage:
    from storage.postgres_database import pg_query, pg_execute, pg_transaction_async

    # Simple query
    rows = await pg_query("SELECT * FROM creatives WHERE id = %s", (creative_id,))

    # Insert/Update
    await pg_execute("INSERT INTO creatives (id, name) VALUES (%s, %s)", (id, name))

    # Transaction (multiple operations)
    def do_work(conn):
        conn.execute("UPDATE ...", (...))
        conn.execute("INSERT ...", (...))
    await pg_transaction_async(do_work)

Environment:
    POSTGRES_DSN or DATABASE_URL must be set to a PostgreSQL connection string.
    Example: postgresql://user:pass@localhost:5432/catscan
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from typing import Any, Callable, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore

logger = logging.getLogger(__name__)


def _get_dsn() -> str:
    """Get PostgreSQL connection string from environment."""
    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL") or ""
    if not dsn:
        raise RuntimeError(
            "POSTGRES_DSN or DATABASE_URL must be set for PostgreSQL access."
        )
    return dsn


def _get_connection() -> "psycopg.Connection":
    """Create a new PostgreSQL connection.

    Each call creates a fresh connection. For production, consider
    using a connection pool (psycopg_pool).
    """
    if psycopg is None:
        raise RuntimeError("psycopg not installed. Run: pip install psycopg[binary]")

    dsn = _get_dsn()
    conn = psycopg.connect(dsn, row_factory=dict_row)
    return conn


async def pg_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a SELECT query and return all rows as dicts.

    Args:
        sql: SELECT statement (use %s for placeholders, NOT ?)
        params: Query parameters

    Returns:
        List of dict objects (column name -> value)

    Example:
        rows = await pg_query(
            "SELECT * FROM creatives WHERE format = %s",
            ("VIDEO",)
        )
        for row in rows:
            print(row["id"], row["canonical_size"])
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    return await loop.run_in_executor(None, _execute)


async def pg_query_with_timeout(
    sql: str,
    params: tuple = (),
    statement_timeout_ms: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Execute a SELECT query with an optional PostgreSQL statement timeout.

    Args:
        sql: SELECT statement (use %s placeholders)
        params: Query parameters
        statement_timeout_ms: Per-statement timeout in milliseconds. If None,
            behavior matches ``pg_query``.
    """
    if statement_timeout_ms is None:
        return await pg_query(sql, params)

    timeout_ms = max(int(statement_timeout_ms), 1)
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            # SET does not support server-side parameter binding ($1),
            # so we embed the validated integer directly.
            conn.execute(f"SET statement_timeout = {timeout_ms}")
            try:
                cursor = conn.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.execute("RESET statement_timeout")

    return await loop.run_in_executor(None, _execute)


async def pg_query_one(sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    """Execute a SELECT query and return first row or None.

    Example:
        config = await pg_query_one(
            "SELECT * FROM pretargeting_configs WHERE billing_id = %s",
            (billing_id,)
        )
        if config:
            print(config["display_name"])
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    return await loop.run_in_executor(None, _execute)


async def pg_query_one_with_timeout(
    sql: str,
    params: tuple = (),
    statement_timeout_ms: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Execute a SELECT query with an optional PostgreSQL statement timeout.

    Args:
        sql: SELECT statement (use %s placeholders)
        params: Query parameters
        statement_timeout_ms: Per-statement timeout in milliseconds. If None,
            behavior matches ``pg_query_one``.
    """
    if statement_timeout_ms is None:
        return await pg_query_one(sql, params)

    timeout_ms = max(int(statement_timeout_ms), 1)
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            # SET does not support server-side parameter binding ($1),
            # so we embed the validated integer directly.
            conn.execute(f"SET statement_timeout = {timeout_ms}")
            try:
                cursor = conn.execute(sql, params)
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.execute("RESET statement_timeout")

    return await loop.run_in_executor(None, _execute)


async def pg_execute(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE and return rows affected.

    Auto-commits on success.

    Example:
        rows_affected = await pg_execute(
            "UPDATE creatives SET updated_at = NOW() WHERE id = %s",
            (creative_id,)
        )
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount

    return await loop.run_in_executor(None, _execute)


async def pg_execute_many(sql: str, params_list: list[tuple]) -> int:
    """Execute same statement with multiple parameter sets.

    Useful for bulk inserts. All operations are in one transaction.

    Example:
        await pg_execute_many(
            "INSERT INTO rtb_daily (metric_date, creative_id, billing_id) VALUES (%s, %s, %s)",
            [
                ("2025-12-09", "cr-1", "billing-1"),
                ("2025-12-09", "cr-2", "billing-1"),
            ]
        )
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            conn.commit()
            return cursor.rowcount

    return await loop.run_in_executor(None, _execute)


async def pg_insert_returning_id(sql: str, params: tuple = ()) -> int:
    """Execute INSERT and return the new row's ID.

    Note: SQL must include RETURNING id clause for PostgreSQL.

    Example:
        new_id = await pg_insert_returning_id(
            "INSERT INTO import_history (batch_id, filename) VALUES (%s, %s) RETURNING id",
            (batch_id, filename)
        )
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            conn.commit()
            return row["id"] if row else 0

    return await loop.run_in_executor(None, _execute)


class PostgresTransaction:
    """Context manager for multi-statement transactions.

    Usage:
        with PostgresTransaction() as conn:
            conn.execute("UPDATE ...", (...))
            conn.execute("INSERT ...", (...))
            # Commits automatically on success
            # Rolls back on any exception
    """

    def __init__(self) -> None:
        self.conn: Optional["psycopg.Connection"] = None

    def __enter__(self) -> "psycopg.Connection":
        self.conn = _get_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
        return False  # Don't suppress exceptions


async def pg_transaction_async(func: Callable[["psycopg.Connection"], Any]) -> Any:
    """Run a function with a database connection in a transaction.

    The function receives a connection and should perform all DB operations.
    Commits on success, rolls back on exception.

    Example:
        async def import_csv_data(rows):
            def _do_import(conn):
                for row in rows:
                    conn.execute("INSERT INTO rtb_daily ...", row)
                return len(rows)

            return await pg_transaction_async(_do_import)
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with PostgresTransaction() as conn:
            return func(conn)

    return await loop.run_in_executor(None, _execute)


def compute_row_hash(*values) -> str:
    """Compute a hash for deduplication.

    Used to prevent duplicate CSV imports.

    Example:
        row_hash = compute_row_hash(metric_date, creative_id, billing_id, size)
    """
    combined = "|".join(str(v) for v in values)
    return hashlib.md5(combined.encode()).hexdigest()


# ============================================================================
# Database initialization
# ============================================================================


async def init_postgres_database() -> None:
    """Initialize PostgreSQL database by running pending migrations.

    Called on application startup when using PostgreSQL backend.
    """
    loop = asyncio.get_event_loop()

    def _run_migrations():
        import sys
        from pathlib import Path

        # Add scripts to path
        scripts_dir = Path(__file__).parent.parent / "scripts"
        sys.path.insert(0, str(scripts_dir))

        try:
            from postgres_migrate import run_migrations

            logger.info("Checking for pending PostgreSQL migrations...")
            applied, failed = run_migrations()

            if failed > 0:
                raise RuntimeError(f"PostgreSQL migration failed: {failed} migration(s) failed")
            elif applied > 0:
                logger.info(f"Applied {applied} PostgreSQL migration(s) successfully.")
            else:
                logger.info("PostgreSQL schema is up to date.")

        except ImportError as e:
            logger.warning(f"Could not import postgres_migrate: {e}")
            logger.info("Skipping automatic migration - run scripts/postgres_migrate.py manually")

    await loop.run_in_executor(None, _run_migrations)


# ============================================================================
# Compatibility layer
# ============================================================================

# Aliases for backward compatibility
db_query = pg_query
db_query_one = pg_query_one
db_execute = pg_execute
db_execute_many = pg_execute_many
db_insert_returning_id = pg_insert_returning_id
db_transaction_async = pg_transaction_async
init_database = init_postgres_database
