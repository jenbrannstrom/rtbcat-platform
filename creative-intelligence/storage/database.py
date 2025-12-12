"""
Database access module for Cat-Scan.

This module provides thread-safe SQLite access for FastAPI's async environment.
ALL database access should go through this module.

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
from contextlib import contextmanager
import threading
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


# Schema management

async def init_database():
    """Initialize database with schema if needed.

    Called on application startup.
    """
    loop = asyncio.get_event_loop()

    def _init():
        with _get_connection() as conn:
            # Check if schema exists
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

            if not tables:
                logger.info("Initializing database schema...")
                _create_schema(conn)
                conn.commit()
                logger.info("Database schema created.")
            else:
                logger.info(f"Database exists with {len(tables)} tables.")

    await loop.run_in_executor(None, _init)


def _create_schema(conn: sqlite3.Connection):
    """Create the database schema.

    This is the canonical schema definition.
    """
    conn.executescript(SCHEMA_SQL)


# The canonical schema
SCHEMA_SQL = """
-- ============================================================
-- Cat-Scan Database Schema v40
-- ============================================================

-- ACCOUNTS
-- OSS: Single row (account_id=1 everywhere)
-- Enterprise: Multiple rows with account switching
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bidder_id TEXT UNIQUE NOT NULL,
    display_name TEXT,
    credentials_path TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PRETARGETING CONFIGS
-- Core of waste analysis. billing_id appears in CSV reports.
CREATE TABLE IF NOT EXISTS pretargeting_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    config_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    bidder_id TEXT,  -- Denormalized for query convenience
    display_name TEXT,
    user_name TEXT,
    state TEXT DEFAULT 'ACTIVE',
    included_formats TEXT,
    included_platforms TEXT,
    included_sizes TEXT,
    included_geos TEXT,
    excluded_geos TEXT,
    raw_config TEXT,
    synced_at TIMESTAMP,
    UNIQUE(account_id, config_id)
);

CREATE INDEX IF NOT EXISTS idx_pretargeting_billing ON pretargeting_configs(billing_id);
CREATE INDEX IF NOT EXISTS idx_pretargeting_account ON pretargeting_configs(account_id);

-- BUYER SEATS
-- Organizational structure - who pays for impressions
CREATE TABLE IF NOT EXISTS buyer_seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    buyer_id TEXT NOT NULL,
    display_name TEXT,
    is_active INTEGER DEFAULT 1,
    synced_at TIMESTAMP,
    UNIQUE(account_id, buyer_id)
);

-- CREATIVES
-- Synced from Google Authorized Buyers API
CREATE TABLE IF NOT EXISTS creatives (
    id TEXT PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    buyer_seat_id INTEGER REFERENCES buyer_seats(id),
    buyer_id TEXT,
    format TEXT,
    width INTEGER,
    height INTEGER,
    canonical_size TEXT,
    approval_status TEXT,
    final_url TEXT,
    advertiser_name TEXT,
    raw_data TEXT,
    synced_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_creatives_account ON creatives(account_id);
CREATE INDEX IF NOT EXISTS idx_creatives_size ON creatives(canonical_size);
CREATE INDEX IF NOT EXISTS idx_creatives_format ON creatives(format);

-- RTB_DAILY
-- THE FACT TABLE - All CSV imports land here
CREATE TABLE IF NOT EXISTS rtb_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    import_batch_id TEXT NOT NULL,
    metric_date DATE NOT NULL,
    creative_id TEXT NOT NULL,
    billing_id TEXT NOT NULL,
    creative_size TEXT,
    creative_format TEXT,
    country TEXT,
    platform TEXT,
    environment TEXT,
    publisher_id TEXT,
    publisher_name TEXT,
    app_id TEXT,
    app_name TEXT,
    reached_queries INTEGER DEFAULT 0,
    bids INTEGER DEFAULT 0,
    bids_in_auction INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros INTEGER DEFAULT 0,
    video_starts INTEGER,
    video_completions INTEGER,
    row_hash TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rtb_daily_date ON rtb_daily(metric_date);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_billing ON rtb_daily(billing_id);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_creative ON rtb_daily(creative_id);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_account ON rtb_daily(account_id);
CREATE INDEX IF NOT EXISTS idx_rtb_daily_batch ON rtb_daily(import_batch_id);

-- IMPORT_HISTORY
-- Audit trail for CSV imports
CREATE TABLE IF NOT EXISTS import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT UNIQUE NOT NULL,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    bidder_id TEXT,  -- Denormalized for multi-account queries
    filename TEXT,
    report_type TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rows_read INTEGER DEFAULT 0,
    rows_imported INTEGER DEFAULT 0,
    rows_skipped INTEGER DEFAULT 0,
    rows_duplicate INTEGER DEFAULT 0,
    date_range_start DATE,
    date_range_end DATE,
    total_spend_usd REAL DEFAULT 0,
    file_size_bytes INTEGER DEFAULT 0,
    billing_ids_found TEXT,  -- JSON array of billing IDs in the file
    status TEXT DEFAULT 'complete',
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_import_account ON import_history(account_id);

-- RTB_ENDPOINTS
-- QPS allocation per region
CREATE TABLE IF NOT EXISTS rtb_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    bidder_id TEXT,  -- Denormalized for query convenience
    endpoint_id TEXT NOT NULL,
    url TEXT NOT NULL,
    maximum_qps INTEGER,
    trading_location TEXT,
    bid_protocol TEXT,
    synced_at TIMESTAMP,
    UNIQUE(account_id, endpoint_id)
);

-- PRETARGETING CHANGES
CREATE TABLE IF NOT EXISTS pretargeting_pending_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value TEXT NOT NULL,
    reason TEXT,
    estimated_qps_impact REAL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    applied_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pretargeting_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id TEXT NOT NULL,
    bidder_id TEXT,
    change_type TEXT NOT NULL,
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT,
    change_source TEXT DEFAULT 'api_sync',
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PRETARGETING SNAPSHOTS (A/B comparison feature)
CREATE TABLE IF NOT EXISTS pretargeting_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT NOT NULL,
    snapshot_name TEXT,
    snapshot_type TEXT DEFAULT 'manual',
    included_formats TEXT,
    included_platforms TEXT,
    included_sizes TEXT,
    included_geos TEXT,
    excluded_geos TEXT,
    state TEXT,
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_spend_usd REAL DEFAULT 0,
    days_tracked INTEGER DEFAULT 0,
    avg_daily_impressions REAL,
    avg_daily_spend_usd REAL,
    ctr_pct REAL,
    cpm_usd REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS snapshot_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT NOT NULL,
    comparison_name TEXT NOT NULL,
    before_snapshot_id INTEGER REFERENCES pretargeting_snapshots(id),
    after_snapshot_id INTEGER REFERENCES pretargeting_snapshots(id),
    before_start_date DATE,
    before_end_date DATE,
    after_start_date DATE,
    after_end_date DATE,
    impressions_delta INTEGER,
    impressions_delta_pct REAL,
    spend_delta_usd REAL,
    spend_delta_pct REAL,
    ctr_delta_pct REAL,
    cpm_delta_pct REAL,
    status TEXT DEFAULT 'in_progress',
    conclusion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- CAMPAIGNS (Enterprise feature)
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    seat_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    is_ai_generated INTEGER DEFAULT 0,
    ai_generated INTEGER DEFAULT 1,
    ai_confidence REAL,
    clustering_method TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS creative_campaigns (
    campaign_id TEXT REFERENCES campaigns(id) ON DELETE CASCADE,
    creative_id TEXT REFERENCES creatives(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (campaign_id, creative_id)
);

CREATE TABLE IF NOT EXISTS campaign_daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
    date DATE NOT NULL,
    total_creatives INTEGER DEFAULT 0,
    active_creatives INTEGER DEFAULT 0,
    total_queries INTEGER DEFAULT 0,
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_spend REAL DEFAULT 0,
    total_video_starts INTEGER,
    total_video_completions INTEGER,
    avg_win_rate REAL,
    avg_ctr REAL,
    avg_cpm REAL,
    unique_geos INTEGER,
    top_geo_id INTEGER,
    top_geo_spend REAL,
    UNIQUE(campaign_id, date)
);

CREATE INDEX IF NOT EXISTS idx_cds_campaign_date ON campaign_daily_summary(campaign_id, date DESC);

-- SUPPORTING TABLES
CREATE TABLE IF NOT EXISTS thumbnail_status (
    creative_id TEXT PRIMARY KEY REFERENCES creatives(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    thumbnail_path TEXT,
    error_reason TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    config_id INTEGER REFERENCES pretargeting_configs(id),
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    evidence_json TEXT,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- VIEWS
CREATE VIEW IF NOT EXISTS v_config_performance AS
SELECT
    pc.id as config_id,
    pc.billing_id,
    pc.display_name,
    pc.user_name,
    pc.state,
    pc.included_sizes,
    pc.included_geos,
    COALESCE(SUM(r.reached_queries), 0) as total_reached,
    COALESCE(SUM(r.impressions), 0) as total_impressions,
    COALESCE(SUM(r.clicks), 0) as total_clicks,
    COALESCE(SUM(r.spend_micros), 0) / 1000000.0 as total_spend_usd,
    CASE WHEN COALESCE(SUM(r.reached_queries), 0) > 0
         THEN ROUND(100.0 * SUM(r.impressions) / SUM(r.reached_queries), 1)
         ELSE 0 END as win_rate_pct,
    CASE WHEN COALESCE(SUM(r.reached_queries), 0) > 0
         THEN ROUND(100.0 * (SUM(r.reached_queries) - SUM(r.impressions)) / SUM(r.reached_queries), 1)
         ELSE 0 END as waste_rate_pct
FROM pretargeting_configs pc
LEFT JOIN rtb_daily r ON pc.billing_id = r.billing_id
GROUP BY pc.id;

-- Daily upload summary for tracking CSV imports
CREATE VIEW IF NOT EXISTS daily_upload_summary AS
SELECT
    date(imported_at) as upload_date,
    COUNT(*) as total_uploads,
    SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as successful_uploads,
    SUM(CASE WHEN status != 'complete' THEN 1 ELSE 0 END) as failed_uploads,
    SUM(rows_imported) as total_rows_written,
    SUM(COALESCE(file_size_bytes, 0)) as total_file_size_bytes,
    CASE WHEN COUNT(*) > 0 THEN AVG(rows_imported) ELSE 0 END as avg_rows_per_upload,
    MIN(rows_imported) as min_rows,
    MAX(rows_imported) as max_rows,
    0 as has_anomaly,
    NULL as anomaly_reason
FROM import_history
GROUP BY date(imported_at);
"""
