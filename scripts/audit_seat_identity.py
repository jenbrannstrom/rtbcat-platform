#!/usr/bin/env python3
"""Audit seat identity (bidder_id) coverage in raw fact tables.

Run on VM with POSTGRES_DSN set:
  python scripts/audit_seat_identity.py

Output: JSON summary of missing identity counts and precompute status.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime

# Ensure we can import from project root
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.postgres_database import pg_query, pg_query_one


async def audit_missing_identity() -> dict:
    """Count rows with missing bidder_id in raw fact tables (last 90 days)."""
    tables = ["rtb_daily", "rtb_bidstream", "rtb_bid_filtering", "rtb_quality"]
    results = {}

    for table in tables:
        try:
            # Check if table exists
            exists = await pg_query_one(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = %s
                ) as exists
                """,
                (table,),
            )
            if not exists or not exists.get("exists"):
                results[table] = {"error": "table does not exist"}
                continue

            # Check if bidder_id column exists
            col_exists = await pg_query_one(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = %s AND column_name = 'bidder_id'
                ) as exists
                """,
                (table,),
            )
            if not col_exists or not col_exists.get("exists"):
                results[table] = {"error": "bidder_id column does not exist"}
                continue

            # Count missing bidder_id
            row = await pg_query_one(
                f"""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(*) FILTER (
                        WHERE bidder_id IS NULL OR BTRIM(bidder_id) = ''
                    ) as missing_bidder_id,
                    COUNT(*) FILTER (WHERE import_batch_id IS NULL) as missing_import_batch_id,
                    MIN(metric_date) as min_date,
                    MAX(metric_date) as max_date
                FROM {table}
                WHERE metric_date >= CURRENT_DATE - INTERVAL '90 days'
                """,
            )
            results[table] = {
                "total_rows": row["total_rows"],
                "missing_bidder_id": row["missing_bidder_id"],
                "missing_import_batch_id": row["missing_import_batch_id"],
                "coverage_pct": round(
                    100 * (1 - row["missing_bidder_id"] / row["total_rows"])
                    if row["total_rows"] > 0 else 0,
                    2,
                ),
                "import_batch_coverage_pct": round(
                    100 * (1 - row["missing_import_batch_id"] / row["total_rows"])
                    if row["total_rows"] > 0 else 0,
                    2,
                ),
                "min_date": str(row["min_date"]) if row["min_date"] else None,
                "max_date": str(row["max_date"]) if row["max_date"] else None,
            }
        except Exception as e:
            results[table] = {"error": str(e)}

    return results


async def audit_precompute_tables() -> dict:
    """Check precompute table row counts (last 90 days)."""
    tables = [
        # Home precompute
        "home_publisher_daily",
        "home_geo_daily",
        "home_size_daily",
        "home_seat_daily",
        "home_config_daily",
        # RTB precompute
        "rtb_publisher_daily",
        "rtb_geo_daily",
        "rtb_size_daily",
        # Config precompute
        "config_creative_daily",
        "config_geo_daily",
        "config_publisher_daily",
    ]
    results = {}

    for table in tables:
        try:
            # Check if table exists
            exists = await pg_query_one(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = %s
                ) as exists
                """,
                (table,),
            )
            if not exists or not exists.get("exists"):
                results[table] = {"error": "table does not exist", "row_count": 0}
                continue

            # Get row count and date range
            row = await pg_query_one(
                f"""
                SELECT
                    COUNT(*) as row_count,
                    MIN(metric_date) as min_date,
                    MAX(metric_date) as max_date
                FROM {table}
                WHERE metric_date >= CURRENT_DATE - INTERVAL '90 days'
                """,
            )
            results[table] = {
                "row_count": row["row_count"],
                "min_date": str(row["min_date"]) if row["min_date"] else None,
                "max_date": str(row["max_date"]) if row["max_date"] else None,
            }
        except Exception as e:
            results[table] = {"error": str(e), "row_count": 0}

    return results


async def audit_refresh_log() -> list:
    """Get recent precompute refresh log entries."""
    try:
        rows = await pg_query(
            """
            SELECT cache_name, buyer_account_id, refresh_start, refresh_end, refreshed_at
            FROM precompute_refresh_log
            ORDER BY refreshed_at DESC
            LIMIT 20
            """
        )
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


async def main() -> None:
    print("=" * 60)
    print("SEAT IDENTITY & PRECOMPUTE AUDIT")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("=" * 60)

    print("\n## Part A: Missing bidder_id (last 90 days)\n")
    identity_results = await audit_missing_identity()
    for table, data in identity_results.items():
        if "error" in data:
            print(f"  {table}: ERROR - {data['error']}")
        else:
            print(f"  {table}:")
            print(f"    total_rows: {data['total_rows']:,}")
            print(f"    missing_bidder_id: {data['missing_bidder_id']:,}")
            print(f"    coverage: {data['coverage_pct']}%")
            print(f"    missing_import_batch_id: {data['missing_import_batch_id']:,}")
            print(f"    import_batch_coverage: {data['import_batch_coverage_pct']}%")
            print(f"    date_range: {data['min_date']} → {data['max_date']}")

    print("\n## Part B: Precompute table population (last 90 days)\n")
    precompute_results = await audit_precompute_tables()
    for table, data in precompute_results.items():
        if "error" in data:
            print(f"  {table}: ERROR - {data['error']}")
        elif data["row_count"] == 0:
            print(f"  {table}: EMPTY (0 rows)")
        else:
            print(f"  {table}: {data['row_count']:,} rows ({data['min_date']} → {data['max_date']})")

    print("\n## Part C: Recent refresh log entries\n")
    refresh_log = await audit_refresh_log()
    if refresh_log and "error" not in refresh_log[0]:
        for entry in refresh_log[:10]:
            print(f"  {entry.get('cache_name', 'unknown')}: {entry.get('refreshed_at', 'unknown')}")
    else:
        print(f"  Error: {refresh_log[0].get('error', 'unknown')}")

    # JSON output for parsing
    print("\n## JSON Summary\n")
    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "identity_audit": identity_results,
        "precompute_audit": precompute_results,
        "refresh_log": refresh_log[:5] if refresh_log else [],
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
