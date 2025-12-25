#!/usr/bin/env python3
"""Fix Campaign Names Script.

Phase 24: Identify and fix malformed campaign names caused by
URL-encoded tracking URLs.
"""

import sqlite3
import re
from pathlib import Path
from urllib.parse import unquote

# Import from our clustering module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.clustering.rule_based import (
    clean_tracking_url,
    extract_app_bundle_id,
    format_bundle_id,
    extract_domain,
)


def is_bad_name(name: str) -> bool:
    """Check if campaign name looks malformed."""
    if not name:
        return False

    indicators = [
        '%%' in name,           # Click macros
        '%3A' in name,          # URL encoding
        '%2F' in name,          # URL encoding
        len(name) > 100,        # Too long
        name.count(' ') > 15,   # Too many words (from .replace(".", " "))
        'Click_Url' in name,    # Common macro
        'Unesc' in name,        # Part of macro
    ]
    return any(indicators)


def suggest_new_name(campaign_id: str, creative_urls: list[str]) -> str:
    """Suggest a better name based on creative URLs."""
    # Try to extract bundle ID from URLs
    for url in creative_urls:
        bundle_id = extract_app_bundle_id(url)
        if bundle_id:
            return f"{format_bundle_id(bundle_id)} Campaign"

    # Try to extract domain
    for url in creative_urls:
        domain = extract_domain(url)
        if domain and len(domain) < 50 and '%' not in domain:
            return f"{domain.replace('.', ' ').title()} Campaign"

    return f"Campaign {campaign_id}"


def main():
    db_path = Path.home() / ".catscan" / "catscan.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get all campaigns
    cursor = conn.execute("SELECT id, name FROM campaigns")
    campaigns = cursor.fetchall()

    bad_campaigns = []
    for c in campaigns:
        if is_bad_name(c['name']):
            bad_campaigns.append(dict(c))

    if not bad_campaigns:
        print("No campaigns with bad names found!")
        conn.close()
        return

    print(f"Found {len(bad_campaigns)} campaigns with bad names:\n")

    for c in bad_campaigns:
        print(f"ID: {c['id']}")
        print(f"  Current: {c['name'][:80]}...")

        # Get creative URLs for this campaign
        cursor = conn.execute("""
            SELECT c.final_url
            FROM creatives c
            JOIN campaign_creatives cc ON c.id = cc.creative_id
            WHERE cc.campaign_id = ?
            LIMIT 5
        """, (c['id'],))
        urls = [row['final_url'] for row in cursor.fetchall() if row['final_url']]

        suggested = suggest_new_name(c['id'], urls)
        print(f"  Suggested: {suggested}")
        print()

        c['suggested'] = suggested

    # Ask for confirmation
    print("-" * 50)
    response = input("Apply fixes? (yes/no): ").strip().lower()

    if response == 'yes':
        for c in bad_campaigns:
            conn.execute(
                "UPDATE campaigns SET name = ? WHERE id = ?",
                (c['suggested'], c['id'])
            )
            print(f"Updated {c['id']} -> {c['suggested']}")

        conn.commit()
        print(f"\nFixed {len(bad_campaigns)} campaign names!")
    else:
        print("No changes made.")

    conn.close()


if __name__ == "__main__":
    main()
