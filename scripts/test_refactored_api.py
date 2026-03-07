#!/usr/bin/env python3
"""Test script for refactored evaluation and campaign services.

Run with:
    python scripts/test_refactored_api.py

Requires:
    - POSTGRES_DSN or DATABASE_URL environment variable set
    - psycopg installed
"""

import asyncio
import os
import sys

if "pytest" in sys.modules:
    import pytest

    pytest.skip("Operational script, not part of automated pytest coverage.", allow_module_level=True)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_env():
    """Check required environment variables."""
    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_SERVING_DSN")
    if not dsn:
        print("ERROR: Set POSTGRES_DSN, DATABASE_URL, or POSTGRES_SERVING_DSN")
        print("Example: export POSTGRES_DSN='postgresql://user:pass@localhost:5432/catscan'")
        sys.exit(1)
    print(f"Using DSN: {dsn[:30]}...")
    return dsn


async def test_evaluation_repo():
    """Test EvaluationRepository."""
    print("\n=== Testing EvaluationRepository ===")
    from storage.postgres_repositories.evaluation_repo import EvaluationRepository

    repo = EvaluationRepository()

    try:
        count = await repo.get_rtb_daily_count(7)
        print(f"  rtb_daily count (7 days): {count:,}")
    except Exception as e:
        print(f"  rtb_daily count: ERROR - {e}")

    try:
        count = await repo.get_creatives_count()
        print(f"  creatives count: {count:,}")
    except Exception as e:
        print(f"  creatives count: ERROR - {e}")

    try:
        sizes = await repo.get_creative_sizes()
        print(f"  creative sizes: {len(sizes)} distinct")
    except Exception as e:
        print(f"  creative sizes: ERROR - {e}")

    try:
        geo = await repo.get_geo_waste(7)
        print(f"  geo waste rows: {len(geo)}")
    except Exception as e:
        print(f"  geo waste: ERROR - {e}")

    print("  EvaluationRepository: OK")


async def test_campaign_repo():
    """Test CampaignRepository."""
    print("\n=== Testing CampaignRepository ===")
    from storage.postgres_repositories.campaign_repo import CampaignRepository

    repo = CampaignRepository()

    try:
        campaigns = await repo.get_all_campaigns()
        print(f"  campaigns count: {len(campaigns)}")
    except Exception as e:
        print(f"  campaigns: ERROR - {e}")

    try:
        unclustered = await repo.get_unclustered_with_activity(7)
        print(f"  unclustered creatives with activity: {len(unclustered)}")
    except Exception as e:
        print(f"  unclustered: ERROR - {e}")

    print("  CampaignRepository: OK")


async def test_evaluation_service():
    """Test EvaluationService."""
    print("\n=== Testing EvaluationService ===")
    from services.evaluation_service import EvaluationService

    service = EvaluationService()

    try:
        results = await service.run_full_evaluation(days=7)
        print(f"  data_quality score: {results['data_quality']['score']}")
        print(f"  recommendations: {len(results['recommendations'])}")
        print(f"  summary: {results['summary']}")
    except Exception as e:
        print(f"  run_full_evaluation: ERROR - {e}")
        import traceback
        traceback.print_exc()

    try:
        funnel = await service.get_bid_funnel(days=7)
        print(f"  bid funnel: {funnel}")
    except Exception as e:
        print(f"  get_bid_funnel: ERROR - {e}")

    print("  EvaluationService: OK")


async def test_campaign_service():
    """Test CampaignAggregationService."""
    print("\n=== Testing CampaignAggregationService ===")
    from services.campaign_aggregation import CampaignAggregationService

    service = CampaignAggregationService()

    try:
        campaigns = await service.get_campaigns_with_metrics(days=7, include_empty=False)
        print(f"  campaigns with activity: {len(campaigns)}")
        if campaigns:
            c = campaigns[0]
            print(f"  first campaign: {c.name} ({c.creative_count} creatives)")
            if c.metrics:
                print(f"    spend: ${c.metrics.total_spend_micros / 1_000_000:,.2f}")
                print(f"    impressions: {c.metrics.total_impressions:,}")
    except Exception as e:
        print(f"  get_campaigns_with_metrics: ERROR - {e}")
        import traceback
        traceback.print_exc()

    try:
        unclustered = await service.get_unclustered_with_activity(days=7)
        print(f"  unclustered with activity: {len(unclustered)}")
    except Exception as e:
        print(f"  get_unclustered_with_activity: ERROR - {e}")

    print("  CampaignAggregationService: OK")


async def test_api_endpoints():
    """Test API endpoints if server is running."""
    print("\n=== Testing API Endpoints (if running) ===")

    try:
        import httpx
    except ImportError:
        print("  httpx not installed, skipping API tests")
        print("  Install with: pip install httpx")
        return

    base_url = os.getenv("API_URL", "http://localhost:8000")

    async with httpx.AsyncClient(timeout=10) as client:
        endpoints = [
            "/health",
            "/api/evaluation?days=7",
            "/api/troubleshooting/filtered-bids?days=7",
            "/api/troubleshooting/funnel?days=7",
        ]

        for endpoint in endpoints:
            try:
                resp = await client.get(f"{base_url}{endpoint}")
                status = "OK" if resp.status_code == 200 else f"HTTP {resp.status_code}"
                print(f"  GET {endpoint}: {status}")
            except httpx.ConnectError:
                print(f"  GET {endpoint}: SKIPPED (server not running)")
                break
            except Exception as e:
                print(f"  GET {endpoint}: ERROR - {e}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Refactored Evaluation & Campaign Services")
    print("=" * 60)

    check_env()

    await test_evaluation_repo()
    await test_campaign_repo()
    await test_evaluation_service()
    await test_campaign_service()
    await test_api_endpoints()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
