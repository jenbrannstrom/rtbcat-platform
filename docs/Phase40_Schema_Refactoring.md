# Phase 40: Schema Refactoring & Database Consolidation

**Date:** December 10, 2025  
**Status:** Planning  
**Estimated Effort:** 2-3 focused sessions  

---

## Executive Summary

Cat-Scan has accumulated technical debt through rapid feature development. This phase consolidates the database layer, simplifies the schema, and prepares the codebase for open-source release.

### Goals
1. Fix SQLite threading bugs that cause "objects created in a thread" errors
2. Reduce 17 tables to 12 with clear purposes
3. Single database access pattern (no more mixed approaches)
4. Clean foundation for OSS release

### Non-Goals
- Adding new features
- Changing the UI
- Multi-account UI (that's Phase 41+)

---

## Context for Claude

### What is Cat-Scan?

Cat-Scan is a **QPS optimization platform for Google Authorized Buyers**. It helps RTB bidders eliminate wasted bid requests by:

1. **Syncing creatives** from Google's API (what ads you have)
2. **Importing CSV reports** from Google (how those ads performed)
3. **Analyzing waste** - traffic for sizes you can't serve
4. **Recommending pretargeting changes** - which sizes/geos to include/exclude

### The Google Authorized Buyers Hierarchy

```
Service Account (JSON key file)
    │
    └── Bidder Account (bidder_id: "12345678")
            │
            ├── Buyer Seat A (buyer_id: "buyer-abc")
            │       └── Pretargeting Config 1 (config_id, billing_id)
            │
            └── Buyer Seat B (buyer_id: "buyer-xyz")
                    └── Pretargeting Config 2 (config_id, billing_id)
```

**Critical insight:** The `billing_id` in CSV reports identifies which **pretargeting config** generated the traffic. This is the key join field.

### Current Problem

The codebase has two database access patterns:

```python
# Pattern 1: Uses store dependency (some endpoints)
async def endpoint(store: SQLiteStore = Depends(get_store)):
    async with store._connection() as conn:
        # ...

# Pattern 2: Direct sqlite3.connect (other endpoints)  
async def endpoint():
    with sqlite3.connect(db_path) as conn:  # Created in Thread A
        result = await loop.run_in_executor(
            None,
            lambda: conn.execute(...)  # Executed in Thread B - BOOM!
        )
```

Pattern 2 causes: `SQLite objects created in a thread can only be used in that same thread`

---

## The Target Schema

### Tables to KEEP (12 tables)

```
CORE ENTITIES
├── accounts              (1 row for OSS, many for Enterprise)
├── pretargeting_configs  (synced from Google API)
├── buyer_seats           (organizational - who pays)
├── creatives             (synced from Google API)
└── rtb_endpoints         (QPS allocation per region)

FACT TABLE
└── rtb_daily             (ALL CSV imports - single source of truth)

TRACKING
├── import_history        (audit trail for CSV imports)
├── pretargeting_pending_changes  (staged changes)
└── pretargeting_history  (audit trail)

FEATURES
├── campaigns             (user groupings - Enterprise feature)
├── campaign_creatives    (junction table)
├── thumbnail_status      (video thumbnail generation)
└── recommendations       (AI suggestions)
```

### Tables to REMOVE (with reasoning)

| Table | Reason |
|-------|--------|
| `seats` | Confused with billing_id. Billing ID belongs to pretargeting_configs |
| `service_accounts` | Merged into `accounts.credentials_path` |
| `clusters` | Merged into `campaigns.is_ai_generated` |
| `ai_campaigns` | Merged into `campaigns` |
| `performance_metrics` | Duplicate of `rtb_daily` |
| `daily_creative_summary` | Compute on-the-fly from rtb_daily |
| `campaign_daily_summary` | Compute on-the-fly from rtb_daily |
| `daily_upload_summary` | Over-engineering, use import_history |
| `account_daily_upload_summary` | Over-engineering |
| `video_metrics` | Columns already in rtb_daily |
| `rtb_traffic` | Unclear purpose, covered by rtb_daily |
| `apps` | Extract from rtb_daily when needed |
| `publishers` | Extract from rtb_daily when needed |
| `pretargeting_snapshots` | Future feature, not in current scope |
| `snapshot_comparisons` | Future feature |
| `pretargeting_change_log` | Redundant with pretargeting_history |
| `retention_config` | Over-engineering |

---

## Implementation Plan

### Step 1: Create New Database Module

**File:** `creative-intelligence/storage/database.py`

This becomes the ONLY way to access the database.

```python
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
from typing import Any, Optional, Generator
from contextlib import contextmanager
import threading
import logging

logger = logging.getLogger(__name__)

# Database location
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


async def db_transaction_async(func):
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
    format TEXT,
    width INTEGER,
    height INTEGER,
    canonical_size TEXT,
    approval_status TEXT,
    final_url TEXT,
    advertiser_name TEXT,
    raw_data TEXT,
    synced_at TIMESTAMP
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
    filename TEXT,
    report_type TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rows_imported INTEGER DEFAULT 0,
    rows_skipped INTEGER DEFAULT 0,
    date_range_start DATE,
    date_range_end DATE,
    status TEXT DEFAULT 'complete',
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_import_account ON import_history(account_id);

-- RTB_ENDPOINTS
-- QPS allocation per region
CREATE TABLE IF NOT EXISTS rtb_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
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
    config_id INTEGER NOT NULL REFERENCES pretargeting_configs(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value TEXT NOT NULL,
    reason TEXT,
    estimated_qps_impact REAL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pretargeting_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL REFERENCES pretargeting_configs(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL,
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT,
    change_source TEXT DEFAULT 'api_sync',
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CAMPAIGNS (Enterprise feature)
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_ai_generated INTEGER DEFAULT 0,
    ai_confidence REAL,
    clustering_method TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaign_creatives (
    campaign_id TEXT REFERENCES campaigns(id) ON DELETE CASCADE,
    creative_id TEXT REFERENCES creatives(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (campaign_id, creative_id)
);

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
"""
```

### Step 2: Update Dependencies

**File:** `creative-intelligence/api/dependencies.py`

```python
"""FastAPI dependencies for Cat-Scan API."""

from storage.database import init_database

# Remove old store dependencies - they're no longer needed
# All endpoints will use the database module directly

async def startup_event():
    """Called when FastAPI starts up."""
    await init_database()
```

### Step 3: Update Main App

**File:** `creative-intelligence/api/main.py`

Add to startup:

```python
from api.dependencies import startup_event

@app.on_event("startup")
async def on_startup():
    await startup_event()
```

### Step 4: Migrate Each Router

For each router file, replace the database access pattern.

**Example: `api/routers/settings.py`**

Before:
```python
async def get_pretargeting_config_detail(billing_id: str, store: SQLiteStore = Depends(get_store)):
    db_path = Path.home() / ".catscan" / "catscan.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        config = await loop.run_in_executor(
            None,
            lambda: conn.execute(
                "SELECT * FROM pretargeting_configs WHERE billing_id = ?",
                (billing_id,)
            ).fetchone()
        )
```

After:
```python
from storage.database import db_query_one, db_query

async def get_pretargeting_config_detail(billing_id: str):
    config = await db_query_one(
        "SELECT * FROM pretargeting_configs WHERE billing_id = ?",
        (billing_id,)
    )
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Config not found: {billing_id}")
    
    pending_changes = await db_query(
        "SELECT * FROM pretargeting_pending_changes WHERE config_id = ? AND status = 'pending'",
        (config["id"],)
    )
    
    # ... rest of logic
```

---

## File-by-File Changes

### Files to CREATE

| File | Purpose |
|------|---------|
| `storage/database.py` | New unified database module |
| `migrations/040_schema_v40.sql` | Fresh schema (for reference/documentation) |

### Files to MODIFY

| File | Changes |
|------|---------|
| `api/main.py` | Add startup event, remove old store imports |
| `api/dependencies.py` | Simplify to just startup_event |
| `api/routers/settings.py` | Use new db module (biggest changes) |
| `api/routers/analytics.py` | Use new db module |
| `api/routers/creatives.py` | Use new db module |
| `api/routers/seats.py` | Use new db module |
| `api/routers/config.py` | Use new db module |
| `api/routers/uploads.py` | Use new db module |
| `api/routers/gmail.py` | Use new db module |
| `api/routers/recommendations.py` | Use new db module |
| `api/routers/retention.py` | Use new db module |
| `api/routers/system.py` | Use new db module |

### Files to DELETE

| File | Reason |
|------|--------|
| `storage/sqlite_store.py` | Replaced by database.py |
| `storage/sqlite_store_new.py` | Replaced by database.py |
| `storage/adapters.py` | No longer needed |

### Files to KEEP (no changes)

| File | Reason |
|------|--------|
| `storage/models.py` | Pydantic models still useful |
| `storage/schema.py` | May have useful constants |
| `collectors/*` | Google API clients unchanged |
| `analytics/*` | Analysis logic unchanged |

---

## Verification Checkpoints

After each step, verify with these tests:

### Checkpoint 1: Database Module Works

```bash
cd creative-intelligence
source venv/bin/activate
python -c "
import asyncio
from storage.database import db_query, init_database

async def test():
    await init_database()
    rows = await db_query('SELECT name FROM sqlite_master WHERE type=\"table\"')
    print(f'Tables: {[r[\"name\"] for r in rows]}')

asyncio.run(test())
"
```

Expected: List of 12 tables

### Checkpoint 2: API Starts

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Expected: No startup errors

### Checkpoint 3: Settings Endpoint Works

```bash
curl http://localhost:8000/settings/pretargeting | python3 -m json.tool
```

Expected: JSON array (empty is fine)

### Checkpoint 4: Detail Endpoint Works (The Bug Fix)

```bash
# First sync some configs
curl -X POST http://localhost:8000/settings/pretargeting/sync

# Then get detail (this was the failing endpoint)
curl http://localhost:8000/settings/pretargeting/104602012074/detail
```

Expected: JSON object, NOT threading error

---

## Migration Script

For a fresh start (since not live), create this script:

**File:** `scripts/reset_to_v40.py`

```python
#!/usr/bin/env python3
"""Reset database to v40 schema.

WARNING: This deletes all data. Only use for development.

Usage:
    python scripts/reset_to_v40.py
    python scripts/reset_to_v40.py --confirm
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import DB_PATH, SCHEMA_SQL, _get_connection


def reset_database(confirm: bool = False):
    if DB_PATH.exists():
        if not confirm:
            print(f"This will DELETE: {DB_PATH}")
            print("Run with --confirm to proceed")
            return False
        
        print(f"Removing old database: {DB_PATH}")
        DB_PATH.unlink()
    
    print("Creating fresh database with v40 schema...")
    conn = _get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    
    # Verify
    conn = _get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    
    print(f"\nCreated {len(tables)} tables:")
    for t in tables:
        print(f"  - {t[0]}")
    
    print(f"\nDatabase ready: {DB_PATH}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset database to v40 schema")
    parser.add_argument("--confirm", action="store_true", help="Confirm deletion")
    args = parser.parse_args()
    
    success = reset_database(confirm=args.confirm)
    sys.exit(0 if success else 1)
```

---

## Order of Operations

Execute in this exact order to avoid breaking things:

```
1. Create storage/database.py (new file, no dependencies)
   └── Test: Checkpoint 1

2. Create scripts/reset_to_v40.py  
   └── Run: python scripts/reset_to_v40.py --confirm

3. Update api/dependencies.py
   └── Remove old store code, add startup_event

4. Update api/main.py  
   └── Add startup event, keep routers for now
   └── Test: Checkpoint 2

5. Update api/routers/settings.py (highest priority - has the bug)
   └── Test: Checkpoint 3, 4

6. Update remaining routers one by one:
   └── analytics.py
   └── creatives.py
   └── seats.py
   └── config.py
   └── uploads.py
   └── system.py
   └── gmail.py (if time)
   └── recommendations.py (if time)
   └── retention.py (if time)

7. Delete old files:
   └── storage/sqlite_store.py
   └── storage/sqlite_store_new.py

8. Full test: Start both backend and frontend, test waste-analysis page
```

---

## What Success Looks Like

After Phase 40:

1. **No threading errors** - "Edit Settings" works
2. **Single database pattern** - All code uses `storage/database.py`
3. **Clean schema** - 12 tables with clear purposes
4. **Ready for OSS** - Codebase is understandable

---

## OSS vs Enterprise Features

For the open-source release, these features are included:

| Feature | OSS | Enterprise |
|---------|-----|------------|
| CSV Import | ✅ | ✅ |
| Creative Sync | ✅ | ✅ |
| Waste Analysis | ✅ | ✅ |
| Pretargeting Recommendations | ✅ | ✅ |
| Size Coverage | ✅ | ✅ |
| Fraud Signals | ✅ | ✅ |
| RTB Funnel | ✅ | ✅ |
| Single Account | ✅ | ✅ |
| Multi-Account Switching | ❌ | ✅ |
| AI Campaign Clustering | ❌ | ✅ |

Enterprise features will be gated by license check in Phase 41+.

---

## Questions for Before Starting

1. Should we keep any data from current database? (Assuming no)
2. License preference for OSS? (MIT recommended for adoption)
3. Any features to add/remove from scope?

---

**Document Version:** 1.0  
**Author:** Claude + Jen  
**Phase:** 40
