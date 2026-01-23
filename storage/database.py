"""
Database access module for Cat-Scan (SQLite backend).

This module provides thread-safe SQLite access for FastAPI's async environment.
ALL database access should go through this module.

TODO: PostgreSQL Migration
    For PostgreSQL backend, use storage.postgres_database instead:
        from storage.postgres_database import pg_query, pg_execute, pg_transaction_async

    The postgres_database module has the same API but uses %s placeholders
    instead of ? and returns dicts instead of sqlite3.Row objects.

    To switch backends:
        1. Set CATSCAN_DB_BACKEND=postgres
        2. Set POSTGRES_DSN=postgresql://user:pass@host:5432/dbname
        3. Run: python scripts/postgres_migrate.py

Usage:
    from storage.database import db_query, db_execute, db_transaction

    # Simple query
    rows = await db_query("SELECT * FROM creatives WHERE id = ?", (creative_id,))

    # Insert/Update
    await db_execute("INSERT INTO creatives (id, name) VALUES (?, ?)", (id, name))

    # Transaction (multiple operations)
    async with db_transaction() as conn:
        conn.execute("UPDATE ...", (...))
        conn.execute("INSERT ...", (...))
        # Auto-commits on success, rolls back on exception
"""

import sqlite3
import asyncio
import hashlib
from pathlib import Path
from typing import Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)

# Database location - use ~/.catscan for user data
DB_PATH = Path.home() / ".catscan" / "catscan.db"


def _get_connection() -> sqlite3.Connection:
    """Create a new connection for the current context.

    Each call creates a fresh connection. This is intentional -
    SQLite connections are cheap, and this avoids threading issues.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")   # Enforce FK constraints
    return conn


async def db_query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Execute a SELECT query and return all rows.

    Args:
        sql: SELECT statement
        params: Query parameters

    Returns:
        List of Row objects (can be accessed like dicts)

    Example:
        rows = await db_query(
            "SELECT * FROM creatives WHERE format = ?",
            ("VIDEO",)
        )
        for row in rows:
            print(row["id"], row["canonical_size"])
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            return conn.execute(sql, params).fetchall()

    return await loop.run_in_executor(None, _execute)


async def db_query_one(sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    """Execute a SELECT query and return first row or None.

    Example:
        config = await db_query_one(
            "SELECT * FROM pretargeting_configs WHERE billing_id = ?",
            (billing_id,)
        )
        if config:
            print(config["display_name"])
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            return conn.execute(sql, params).fetchone()

    return await loop.run_in_executor(None, _execute)


async def db_execute(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE and return rows affected.

    Auto-commits on success.

    Example:
        rows_affected = await db_execute(
            "UPDATE creatives SET synced_at = CURRENT_TIMESTAMP WHERE id = ?",
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


async def db_execute_many(sql: str, params_list: list[tuple]) -> int:
    """Execute same statement with multiple parameter sets.

    Useful for bulk inserts. All operations are in one transaction.

    Example:
        await db_execute_many(
            "INSERT INTO rtb_daily (metric_date, creative_id, billing_id) VALUES (?, ?, ?)",
            [
                ("2025-12-09", "cr-1", "billing-1"),
                ("2025-12-09", "cr-2", "billing-1"),
                ("2025-12-09", "cr-3", "billing-2"),
            ]
        )
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            cursor = conn.executemany(sql, params_list)
            conn.commit()
            return cursor.rowcount

    return await loop.run_in_executor(None, _execute)


async def db_insert_returning_id(sql: str, params: tuple = ()) -> int:
    """Execute INSERT and return the new row's ID.

    Example:
        new_id = await db_insert_returning_id(
            "INSERT INTO import_history (batch_id, filename) VALUES (?, ?)",
            (batch_id, filename)
        )
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.lastrowid

    return await loop.run_in_executor(None, _execute)


class DatabaseTransaction:
    """Context manager for multi-statement transactions.

    Usage:
        async with db_transaction() as conn:
            conn.execute("UPDATE ...", (...))
            conn.execute("INSERT ...", (...))
            # Commits automatically on success
            # Rolls back on any exception
    """
    def __init__(self):
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = _get_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
        return False  # Don't suppress exceptions


async def db_transaction_async(func: Callable[[sqlite3.Connection], Any]) -> Any:
    """Run a function with a database connection in a transaction.

    The function receives a connection and should perform all DB operations.
    Commits on success, rolls back on exception.

    Example:
        async def import_csv_data(rows):
            def _do_import(conn):
                for row in rows:
                    conn.execute("INSERT INTO rtb_daily ...", row)
                return len(rows)

            return await db_transaction_async(_do_import)
    """
    loop = asyncio.get_event_loop()

    def _execute():
        with DatabaseTransaction() as conn:
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


# Schema management via migrations

async def init_database():
    """Initialize database by running pending migrations.

    Called on application startup. Uses the migration runner from
    migrations/runner.py as the single source of truth for schema.
    """
    loop = asyncio.get_event_loop()

    def _run_migrations():
        # Import here to avoid circular imports
        from migrations.runner import run_migrations as sync_run_migrations

        logger.info("Checking for pending database migrations...")
        applied, failed = sync_run_migrations(DB_PATH)

        if failed > 0:
            logger.error(f"Migration failed! {failed} migration(s) could not be applied.")
            raise RuntimeError(f"Database migration failed: {failed} migration(s) failed")
        elif applied > 0:
            logger.info(f"Applied {applied} migration(s) successfully.")
        else:
            logger.info("Database schema is up to date.")

    await loop.run_in_executor(None, _run_migrations)


# Legacy embedded schema removed - migrations are now the single source of truth.
# See migrations/*.sql for the canonical schema definition.
