#!/usr/bin/env python3
"""
Backfill script to populate app_id and app_name for existing creatives.

This script parses existing creatives' URLs and HTML snippets to extract
app information and fetch real app names from the stores.

Run this after:
1. Deploying the new schema with app_id, app_name, app_store columns
2. Running schema migrations
3. Syncing creatives from the Google API (optional - will work on existing data)

Usage:
    python scripts/backfill_app_info.py [--dry-run] [--limit N]

Options:
    --dry-run    Don't actually update the database, just show what would change
    --limit N    Only process N creatives (for testing)

The script will:
1. Find all creatives without app_name set
2. Parse their URLs and HTML snippets for app store links
3. Fetch actual app names from Google Play Store and Apple App Store
4. Update the database with the extracted information
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.app_parser import (
    extract_app_info_from_creative,
    parse_app_store_url,
    extract_urls_from_html_snippet,
)


def get_db_path() -> Path:
    """Get the database path from environment or default."""
    import os
    db_path = os.environ.get("DATABASE_PATH", "data/catscan.db")
    return project_root / db_path


async def backfill_app_info(db_path: Path, dry_run: bool = False, limit: int = None) -> dict:
    """
    Backfill app_id and app_name for creatives that don't have them.

    Args:
        db_path: Path to the SQLite database
        dry_run: If True, don't actually update the database
        limit: Maximum number of creatives to process

    Returns:
        Dict with statistics about the backfill
    """
    stats = {
        "total_checked": 0,
        "already_has_app_info": 0,
        "updated": 0,
        "no_app_found": 0,
        "errors": 0,
    }

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        # Get all creatives that don't have app_name set
        cursor = conn.cursor()
        query = """
            SELECT id, final_url, advertiser_name, raw_data
            FROM creatives
            WHERE app_name IS NULL OR app_name = ''
        """
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        creatives_to_update = cursor.fetchall()
        stats["total_checked"] = len(creatives_to_update)

        print(f"Found {len(creatives_to_update)} creatives without app info")

        for i, row in enumerate(creatives_to_update):
            creative_id = row["id"]
            final_url = row["final_url"]
            advertiser_name = row["advertiser_name"]
            raw_data_str = row["raw_data"]

            if (i + 1) % 10 == 0:
                print(f"  Processing {i + 1}/{len(creatives_to_update)}...")

            try:
                # Parse raw_data to get HTML snippet
                raw_data = json.loads(raw_data_str) if raw_data_str else {}
                html_snippet = raw_data.get("html", {}).get("snippet") if raw_data.get("html") else None
                declared_urls = raw_data.get("declaredClickThroughUrls", [])

                # Extract app info (async - fetches from stores)
                app_info = await extract_app_info_from_creative(
                    final_url=final_url,
                    declared_urls=declared_urls,
                    html_snippet=html_snippet,
                    advertiser_name=advertiser_name,
                    fetch_names=True,  # Fetch real names from stores
                )

                if app_info.get("app_id") or app_info.get("app_name"):
                    if not dry_run:
                        cursor.execute("""
                            UPDATE creatives
                            SET app_id = ?, app_name = ?, app_store = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (
                            app_info.get("app_id"),
                            app_info.get("app_name"),
                            app_info.get("app_store"),
                            creative_id,
                        ))
                    stats["updated"] += 1
                    print(f"  [{creative_id}] -> {app_info.get('app_name')} ({app_info.get('app_store') or 'website'})")
                else:
                    stats["no_app_found"] += 1

            except Exception as e:
                stats["errors"] += 1
                print(f"  [{creative_id}] Error: {e}")

        if not dry_run:
            conn.commit()
            print(f"\nCommitted {stats['updated']} updates to database")
        else:
            print(f"\n[DRY RUN] Would update {stats['updated']} creatives")

    finally:
        conn.close()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill app_id and app_name for existing creatives"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually update the database, just show what would be updated",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of creatives to process (for testing)",
    )
    args = parser.parse_args()

    db_path = get_db_path()
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        sys.exit(1)

    print(f"Database: {db_path}")
    print(f"Dry run: {args.dry_run}")
    if args.limit:
        print(f"Limit: {args.limit}")
    print()

    # Run the async backfill
    stats = asyncio.run(backfill_app_info(db_path, dry_run=args.dry_run, limit=args.limit))

    print()
    print("=" * 40)
    print("Backfill Statistics:")
    print(f"  Total checked: {stats['total_checked']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  No app found: {stats['no_app_found']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
