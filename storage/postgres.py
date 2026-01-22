"""Postgres helpers for analytics precompute jobs."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Callable, Iterable, Optional

import psycopg


def _get_dsn() -> str:
    return os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL") or ""


def _get_connection() -> psycopg.Connection:
    dsn = _get_dsn()
    if not dsn:
        raise RuntimeError("POSTGRES_DSN or DATABASE_URL must be set for Postgres access.")
    return psycopg.connect(dsn)


class PostgresTransaction:
    """Context manager for Postgres transactions."""

    def __init__(self) -> None:
        self.conn: Optional[psycopg.Connection] = None

    def __enter__(self) -> psycopg.Connection:
        self.conn = _get_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
        return False


async def pg_transaction_async(func: Callable[[psycopg.Connection], Any]) -> Any:
    """Run a function with a Postgres connection in a transaction."""
    loop = asyncio.get_event_loop()

    def _execute():
        with PostgresTransaction() as conn:
            return func(conn)

    return await loop.run_in_executor(None, _execute)


def execute_many(
    conn: psycopg.Connection,
    *,
    sql: str,
    rows: Iterable[tuple],
) -> None:
    with conn.cursor() as cursor:
        cursor.executemany(sql, list(rows))
