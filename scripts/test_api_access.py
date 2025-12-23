#!/usr/bin/env python3
"""
Test Google Authorized Buyers API access.

This script verifies that the API credentials are properly configured
and can access the Real-time Bidding API.

Usage:
    # From creative-intelligence directory with venv activated:
    python scripts/test_api_access.py

    # Or directly:
    cd /home/jen/Documents/rtbcat-platform/creative-intelligence
    source venv/bin/activate
    python scripts/test_api_access.py
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors import CreativesClient, PretargetingClient
from collectors.seats import BuyerSeatsClient

# Configuration
CREDENTIALS_PATH = os.path.expanduser("~/.rtb-cat/credentials/google-credentials.json")
BIDDER_ID = "6634662463"  # Amazing MobYoung


async def test_api_access():
    """Test access to all Authorized Buyers API endpoints."""

    print("=" * 60)
    print("RTBcat API Access Test")
    print("=" * 60)
    print(f"\nCredentials: {CREDENTIALS_PATH}")
    print(f"Bidder ID: {BIDDER_ID}")

    # Check credentials file exists
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"\n[ERROR] Credentials file not found: {CREDENTIALS_PATH}")
        print("\nTo fix:")
        print("1. Place your service account JSON at the path above")
        print("2. Or update CREDENTIALS_PATH in this script")
        return False

    print(f"\n[OK] Credentials file exists")

    all_passed = True

    # Test 1: Creatives API
    print("\n" + "-" * 40)
    print("Test 1: Creatives API (bidders.creatives.list)")
    print("-" * 40)

    try:
        client = CreativesClient(
            credentials_path=CREDENTIALS_PATH,
            account_id=BIDDER_ID,
            page_size=10  # Just fetch a few for testing
        )

        creatives = await client.fetch_all_creatives()
        print(f"[PASS] Found {len(creatives)} creatives")

        if creatives:
            sample = creatives[0]
            print(f"       Sample: {sample.get('name', 'N/A')}")
            print(f"       Format: {sample.get('declaredFormat', 'N/A')}")

    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        all_passed = False

    # Test 2: Buyer Seats API
    print("\n" + "-" * 40)
    print("Test 2: Buyer Seats API (bidders.buyers.list)")
    print("-" * 40)

    try:
        client = BuyerSeatsClient(
            credentials_path=CREDENTIALS_PATH,
            account_id=BIDDER_ID
        )

        seats = await client.discover_buyer_seats()
        print(f"[PASS] Found {len(seats)} buyer seats")

        for seat in seats[:5]:  # Show first 5
            print(f"       - {seat.buyer_id}: {seat.display_name} (active={seat.active})")

    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        all_passed = False

    # Test 3: Pretargeting Configs API
    print("\n" + "-" * 40)
    print("Test 3: Pretargeting API (bidders.pretargetingConfigs.list)")
    print("-" * 40)

    try:
        client = PretargetingClient(
            credentials_path=CREDENTIALS_PATH,
            account_id=BIDDER_ID
        )

        configs = await client.fetch_all_pretargeting_configs()
        print(f"[PASS] Found {len(configs)} pretargeting configs")

        for config in configs[:10]:  # Show first 10
            config_id = config.get('configId', 'N/A')
            display_name = config.get('displayName', 'unnamed')
            billing_id = config.get('billingId', 'N/A')
            state = config.get('state', 'UNKNOWN')
            print(f"       - ID: {config_id}, Name: {display_name}")
            print(f"         Billing ID: {billing_id}, State: {state}")

    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("RESULT: All API tests passed!")
        print("=" * 60)
        print("\nYour Google Authorized Buyers API access is working correctly.")
        print("\nNext steps:")
        print("1. Sync creatives: POST http://localhost:8000/collect/sync")
        print("2. Discover seats: POST http://localhost:8000/seats/discover")
        print("3. View dashboard: http://localhost:3000")
    else:
        print("RESULT: Some tests failed")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("1. Verify service account is added in Authorized Buyers UI")
        print("   Settings -> API Access -> Add service account email")
        print("2. Check Real-time Bidding API is enabled in Google Cloud Console")
        print("3. Verify bidder ID is correct")

    return all_passed


async def test_rtb_troubleshooting():
    """Test RTB Troubleshooting API (Ad Exchange Buyer II).

    Note: This API requires a separate scope and may not be enabled.
    """
    print("\n" + "=" * 60)
    print("RTB Troubleshooting API Test (Optional)")
    print("=" * 60)
    print("\nNote: The RTB Troubleshooting API (adexchangebuyer2) requires:")
    print("  - Scope: https://www.googleapis.com/auth/adexchange.buyer")
    print("  - API enabled in Google Cloud Console")
    print("\nThis API provides bid metrics, filtered bids, etc.")
    print("It is NOT currently integrated into RTBcat collectors.")
    print("\nTo add this capability, a new TroubleshootingClient would need")
    print("to be created in collectors/ using the adexchangebuyer2 API.")


if __name__ == "__main__":
    print("\n")
    success = asyncio.run(test_api_access())
    asyncio.run(test_rtb_troubleshooting())
    print("\n")
    sys.exit(0 if success else 1)
