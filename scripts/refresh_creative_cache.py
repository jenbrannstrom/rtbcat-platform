#!/usr/bin/env python3
"""Refresh live creative cache for active creatives (off-hours job)."""

from __future__ import annotations

import argparse
import asyncio

from config import ConfigManager
from services.creative_cache_service import CreativeCacheService
from storage.postgres_store import PostgresStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh active creative cache.")
    parser.add_argument("--days", type=int, default=7, help="Lookback days for active creatives")
    parser.add_argument("--limit", type=int, default=500, help="Max creatives to refresh")
    parser.add_argument(
        "--skip-html-thumbnails",
        action="store_true",
        help="Skip HTML thumbnail extraction",
    )
    parser.add_argument(
        "--force-html-thumbnail-retry",
        action="store_true",
        help="Retry HTML thumbnails that previously failed",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    store = PostgresStore()
    await store.initialize()
    config = ConfigManager()
    svc = CreativeCacheService(store=store, config=config)

    result = await svc.refresh_active_creatives(
        days=max(1, args.days),
        limit=max(1, args.limit),
        include_html_thumbnails=not args.skip_html_thumbnails,
        force_html_thumbnail_retry=args.force_html_thumbnail_retry,
    )
    print(result.to_dict())


if __name__ == "__main__":
    asyncio.run(main())
