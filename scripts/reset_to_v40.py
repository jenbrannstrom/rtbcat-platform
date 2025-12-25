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
