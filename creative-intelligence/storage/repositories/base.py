"""Base repository class for database operations.

Provides common functionality for all repository classes including
connection management and async execution patterns.
"""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, TypeVar, Generic, Optional, Callable, Any

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base repository with common database operations.

    Provides:
    - Connection management
    - Async execution via run_in_executor
    - Transaction support

    Subclasses should implement entity-specific CRUD operations.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path).expanduser()

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[sqlite3.Connection]:
        """Context manager for database connections.

        Yields:
            SQLite connection with row factory set to sqlite3.Row.
        """
        loop = asyncio.get_event_loop()
        conn = await loop.run_in_executor(
            None,
            lambda: sqlite3.connect(self.db_path, check_same_thread=False),
        )
        conn.row_factory = sqlite3.Row

        try:
            yield conn
        finally:
            await loop.run_in_executor(None, conn.close)

    async def _execute(
        self,
        query: str,
        params: tuple = (),
        fetch: str = "none",
    ) -> Any:
        """Execute a query with optional fetch.

        Args:
            query: SQL query string.
            params: Query parameters.
            fetch: Fetch mode - "none", "one", "all".

        Returns:
            Query result based on fetch mode.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _run():
                cursor = conn.execute(query, params)
                if fetch == "one":
                    return cursor.fetchone()
                elif fetch == "all":
                    return cursor.fetchall()
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _run)

    async def _execute_many(
        self,
        query: str,
        params_list: list[tuple],
    ) -> int:
        """Execute a query with multiple parameter sets.

        Args:
            query: SQL query string.
            params_list: List of parameter tuples.

        Returns:
            Number of rows affected.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _run():
                conn.executemany(query, params_list)
                conn.commit()
                return len(params_list)

            return await loop.run_in_executor(None, _run)

    async def _run_in_transaction(
        self,
        operations: Callable[[sqlite3.Connection], T],
    ) -> T:
        """Run operations within a transaction.

        Args:
            operations: Function that takes connection and performs operations.

        Returns:
            Result from operations function.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _run():
                try:
                    result = operations(conn)
                    conn.commit()
                    return result
                except Exception:
                    conn.rollback()
                    raise

            return await loop.run_in_executor(None, _run)


class SyncBaseRepository(Generic[T]):
    """Synchronous base repository for use with existing sync code.

    Some repositories (like CampaignRepository) use synchronous database
    connections passed from FastAPI endpoints. This base class provides
    common patterns for those cases.
    """

    def __init__(self, db_connection: sqlite3.Connection) -> None:
        """Initialize with existing database connection.

        Args:
            db_connection: Active SQLite connection.
        """
        self.db = db_connection
        self.db.row_factory = sqlite3.Row

    def _execute(
        self,
        query: str,
        params: tuple = (),
        fetch: str = "none",
    ) -> Any:
        """Execute a query with optional fetch.

        Args:
            query: SQL query string.
            params: Query parameters.
            fetch: Fetch mode - "none", "one", "all".

        Returns:
            Query result based on fetch mode.
        """
        cursor = self.db.execute(query, params)
        if fetch == "one":
            return cursor.fetchone()
        elif fetch == "all":
            return cursor.fetchall()
        self.db.commit()
        return cursor.rowcount

    def _execute_many(
        self,
        query: str,
        params_list: list[tuple],
    ) -> int:
        """Execute a query with multiple parameter sets.

        Args:
            query: SQL query string.
            params_list: List of parameter tuples.

        Returns:
            Number of rows affected.
        """
        self.db.executemany(query, params_list)
        self.db.commit()
        return len(params_list)
