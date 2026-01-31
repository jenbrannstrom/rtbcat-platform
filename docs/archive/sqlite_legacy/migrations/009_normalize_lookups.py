"""
Migration 009: Add normalized lookup tables for performance data

This migration creates lookup tables to store repeated values once:
- geographies: Country/city lookup (reduces ~20 bytes/row to 4 bytes)
- apps: App metadata lookup
- billing_accounts: Billing account lookup
- publishers: Publisher lookup

This reduces storage by ~5x for large datasets and improves query performance
since integer comparisons are faster than string comparisons.

Run with:
    python -m storage.migrations.009_normalize_lookups

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


# Common countries with ISO codes
COMMON_COUNTRIES = [
    ('US', 'United States'),
    ('GB', 'United Kingdom'),
    ('CA', 'Canada'),
    ('AU', 'Australia'),
    ('DE', 'Germany'),
    ('FR', 'France'),
    ('JP', 'Japan'),
    ('BR', 'Brazil'),
    ('IN', 'India'),
    ('MX', 'Mexico'),
    ('ES', 'Spain'),
    ('IT', 'Italy'),
    ('NL', 'Netherlands'),
    ('SE', 'Sweden'),
    ('NO', 'Norway'),
    ('DK', 'Denmark'),
    ('FI', 'Finland'),
    ('PL', 'Poland'),
    ('RU', 'Russia'),
    ('CN', 'China'),
    ('KR', 'South Korea'),
    ('SG', 'Singapore'),
    ('ID', 'Indonesia'),
    ('TH', 'Thailand'),
    ('MY', 'Malaysia'),
    ('PH', 'Philippines'),
    ('VN', 'Vietnam'),
    ('AR', 'Argentina'),
    ('CL', 'Chile'),
    ('CO', 'Colombia'),
    ('PE', 'Peru'),
    ('ZA', 'South Africa'),
    ('NG', 'Nigeria'),
    ('EG', 'Egypt'),
    ('AE', 'United Arab Emirates'),
    ('SA', 'Saudi Arabia'),
    ('IL', 'Israel'),
    ('TR', 'Turkey'),
    ('IE', 'Ireland'),
    ('PT', 'Portugal'),
    ('AT', 'Austria'),
    ('CH', 'Switzerland'),
    ('BE', 'Belgium'),
    ('CZ', 'Czech Republic'),
    ('HU', 'Hungary'),
    ('RO', 'Romania'),
    ('UA', 'Ukraine'),
    ('GR', 'Greece'),
    ('NZ', 'New Zealand'),
    ('HK', 'Hong Kong'),
    ('TW', 'Taiwan'),
]


def upgrade(db_connection: Union[sqlite3.Connection, any]) -> None:
    """
    Create normalized lookup tables for performance data.

    This migration is idempotent - safe to run multiple times.
    """
    cursor = db_connection.cursor()
    db_type = detect_db_type(db_connection)

    print(f"Running migration 009 on {db_type} database...")

    # 1. Create geographies lookup table
    if db_type == 'sqlite':
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS geographies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_code TEXT,
                country_name TEXT,
                city_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(country_code, city_name)
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS geographies (
                id SERIAL PRIMARY KEY,
                country_code VARCHAR(2),
                country_name VARCHAR(100),
                city_name VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(country_code, city_name)
            )
        """)

    # 2. Create apps lookup table
    if db_type == 'sqlite':
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT UNIQUE,
                app_name TEXT,
                platform TEXT,
                store_url TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apps (
                id SERIAL PRIMARY KEY,
                app_id TEXT UNIQUE,
                app_name TEXT,
                platform VARCHAR(20),
                store_url TEXT,
                first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

    # 3. Create billing_accounts lookup table
    if db_type == 'sqlite':
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                billing_id TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_accounts (
                id SERIAL PRIMARY KEY,
                billing_id TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

    # 4. Create publishers lookup table
    if db_type == 'sqlite':
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS publishers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publisher_id TEXT UNIQUE,
                publisher_name TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS publishers (
                id SERIAL PRIMARY KEY,
                publisher_id TEXT UNIQUE,
                publisher_name TEXT,
                first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

    # 5. Create indexes for faster lookups
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_geo_country ON geographies(country_code)",
        "CREATE INDEX IF NOT EXISTS idx_geo_name ON geographies(country_name)",
        "CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(app_name)",
        "CREATE INDEX IF NOT EXISTS idx_apps_platform ON apps(platform)",
        "CREATE INDEX IF NOT EXISTS idx_publishers_name ON publishers(publisher_name)",
    ]

    for stmt in index_statements:
        try:
            cursor.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"Warning: Index creation issue: {e}")

    # 6. Pre-populate common geographies for faster lookups
    for code, name in COMMON_COUNTRIES:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO geographies (country_code, country_name) VALUES (?, ?)",
                (code, name)
            )
        except Exception as e:
            # PostgreSQL uses different syntax
            if db_type != 'sqlite':
                try:
                    cursor.execute(
                        "INSERT INTO geographies (country_code, country_name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (code, name)
                    )
                except Exception:
                    pass

    # 7. Add foreign key columns to performance_metrics (if they don't exist)
    # Note: SQLite doesn't support adding foreign key constraints to existing tables
    # So we just add the columns for now
    new_columns = [
        ("geo_id", "INTEGER"),
        ("app_id_fk", "INTEGER"),  # app_id already exists as text, use different name
        ("billing_account_id", "INTEGER"),
        ("publisher_id_fk", "INTEGER"),  # publisher_id might exist, use different name
    ]

    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE performance_metrics ADD COLUMN {col_name} {col_type}")
            print(f"  Added column {col_name} to performance_metrics")
        except Exception as e:
            if "duplicate column" not in str(e).lower() and "already exists" not in str(e).lower():
                print(f"Warning: Column {col_name}: {e}")

    # 8. Create index on new foreign key columns
    fk_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_perf_geo_id ON performance_metrics(geo_id)",
        "CREATE INDEX IF NOT EXISTS idx_perf_app_id_fk ON performance_metrics(app_id_fk)",
        "CREATE INDEX IF NOT EXISTS idx_perf_billing_id ON performance_metrics(billing_account_id)",
    ]

    for stmt in fk_indexes:
        try:
            cursor.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"Warning: FK index creation issue: {e}")

    db_connection.commit()
    print("Migration 009: Lookup tables created successfully")


def downgrade(db_connection: Union[sqlite3.Connection, any]) -> None:
    """
    Rollback migration (for testing).

    WARNING: This will delete all lookup data!
    """
    cursor = db_connection.cursor()
    db_type = detect_db_type(db_connection)

    print(f"Rolling back migration 009 on {db_type} database...")

    # Drop lookup tables
    cursor.execute("DROP TABLE IF EXISTS geographies")
    cursor.execute("DROP TABLE IF EXISTS apps")
    cursor.execute("DROP TABLE IF EXISTS billing_accounts")
    cursor.execute("DROP TABLE IF EXISTS publishers")

    # Note: We don't remove the FK columns from performance_metrics
    # as SQLite doesn't support DROP COLUMN easily

    db_connection.commit()
    print("Migration 009 rolled back")


def run_standalone():
    """Run migration standalone (for testing)."""
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
