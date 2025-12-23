"""
Migration 008: Add performance metrics tracking

This migration adds:
1. performance_metrics table for granular performance data (impressions, clicks, spend)
2. Campaign cache columns for fast aggregated lookups

Run with:
    python -m storage.migrations.run

Or automatically applied via SQLiteStore.initialize()
"""

import sqlite3
from typing import Union


def detect_db_type(connection) -> str:
    """Detect database type from connection."""
    conn_type = str(type(connection)).lower()
    if 'sqlite' in conn_type:
        return 'sqlite'
    elif 'psycopg' in conn_type or 'postgres' in conn_type:
        return 'postgresql'
    return 'unknown'


def upgrade(db_connection: Union[sqlite3.Connection, any]) -> None:
    """
    Add performance_metrics table and update campaigns table.

    This migration is idempotent - safe to run multiple times.
    """
    cursor = db_connection.cursor()
    db_type = detect_db_type(db_connection)

    print(f"Running migration 008 on {db_type} database...")

    # Create performance_metrics table
    if db_type == 'sqlite':
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creative_id TEXT NOT NULL,
                campaign_id TEXT,
                metric_date DATE NOT NULL,
                hour INTEGER CHECK (hour IS NULL OR (hour >= 0 AND hour <= 23)),
                impressions INTEGER NOT NULL DEFAULT 0,
                clicks INTEGER NOT NULL DEFAULT 0,
                spend_micros INTEGER NOT NULL DEFAULT 0,
                cpm_micros INTEGER,
                cpc_micros INTEGER,
                geography TEXT,
                device_type TEXT,
                placement TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE
            )
        """)
    else:
        # PostgreSQL version with CHECK constraints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id BIGSERIAL PRIMARY KEY,
                creative_id TEXT NOT NULL,
                campaign_id TEXT,
                metric_date DATE NOT NULL,
                hour INTEGER CHECK (hour IS NULL OR (hour >= 0 AND hour <= 23)),
                impressions BIGINT NOT NULL DEFAULT 0 CHECK (impressions >= 0),
                clicks BIGINT NOT NULL DEFAULT 0 CHECK (clicks >= 0),
                spend_micros BIGINT NOT NULL DEFAULT 0 CHECK (spend_micros >= 0),
                cpm_micros BIGINT CHECK (cpm_micros IS NULL OR cpm_micros >= 0),
                cpc_micros BIGINT CHECK (cpc_micros IS NULL OR cpc_micros >= 0),
                geography VARCHAR(2),
                device_type VARCHAR(20) CHECK (device_type IN ('DESKTOP', 'MOBILE', 'TABLET', 'CTV', 'UNKNOWN')),
                placement TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                CONSTRAINT fk_creative FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE,
                CONSTRAINT chk_clicks_lte_impressions CHECK (clicks <= impressions)
            )
        """)

    # Create indexes (idempotent with IF NOT EXISTS)
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_perf_creative_date ON performance_metrics(creative_id, metric_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_perf_campaign_date ON performance_metrics(campaign_id, metric_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_perf_date_geo ON performance_metrics(metric_date, geography)",
        "CREATE INDEX IF NOT EXISTS idx_perf_spend ON performance_metrics(spend_micros DESC)",
        "CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_metrics(metric_date DESC)",
    ]

    for stmt in index_statements:
        try:
            cursor.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"Warning: Index creation issue: {e}")

    # Create unique constraint for UPSERT support
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_perf_unique_daily
            ON performance_metrics(creative_id, metric_date, geography, device_type, placement)
        """)
    except Exception as e:
        if "already exists" not in str(e).lower():
            print(f"Warning: Unique index creation issue: {e}")

    # Add campaign cache columns (idempotent)
    campaign_columns = [
        ("spend_7d_micros", "INTEGER DEFAULT 0"),
        ("spend_30d_micros", "INTEGER DEFAULT 0"),
        ("total_impressions", "INTEGER DEFAULT 0"),
        ("total_clicks", "INTEGER DEFAULT 0"),
        ("avg_cpm_micros", "INTEGER"),
        ("avg_cpc_micros", "INTEGER"),
        ("top_geography", "TEXT"),
        ("top_device_type", "TEXT"),
        ("perf_updated_at", "TIMESTAMP"),
    ]

    for col_name, col_type in campaign_columns:
        try:
            cursor.execute(f"ALTER TABLE campaigns ADD COLUMN {col_name} {col_type}")
        except Exception as e:
            # Column already exists (expected for idempotent migrations)
            if "duplicate column" not in str(e).lower() and "already exists" not in str(e).lower():
                print(f"Warning: Column {col_name}: {e}")

    db_connection.commit()
    print("✓ Migration 008: Performance metrics table created successfully")


def downgrade(db_connection: Union[sqlite3.Connection, any]) -> None:
    """
    Rollback migration (for testing).

    WARNING: This will delete all performance data!
    """
    cursor = db_connection.cursor()
    db_type = detect_db_type(db_connection)

    print(f"Rolling back migration 008 on {db_type} database...")

    # Drop performance_metrics table
    cursor.execute("DROP TABLE IF EXISTS performance_metrics")

    # Note: SQLite doesn't support DROP COLUMN easily
    # For PostgreSQL, we could drop the columns, but safer to leave them
    if db_type != 'sqlite':
        columns_to_drop = [
            "spend_7d_micros", "spend_30d_micros", "total_impressions",
            "total_clicks", "avg_cpm_micros", "avg_cpc_micros",
            "top_geography", "top_device_type", "perf_updated_at"
        ]
        for col in columns_to_drop:
            try:
                cursor.execute(f"ALTER TABLE campaigns DROP COLUMN IF EXISTS {col}")
            except Exception:
                pass

    db_connection.commit()
    print("✓ Migration 008 rolled back")


def run_standalone():
    """Run migration standalone (for testing)."""
    import os
    from pathlib import Path

    db_path = Path.home() / ".catscan" / "catscan.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    try:
        upgrade(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run_standalone()
