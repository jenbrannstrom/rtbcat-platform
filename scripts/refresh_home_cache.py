#!/usr/bin/env python3
"""Refresh Home precompute tables for a date range."""

import argparse
import asyncio
from datetime import datetime, timedelta

from services.home_precompute import refresh_home_summaries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Home precomputed tables.")
    parser.add_argument("--start-date", help="YYYY-MM-DD")
    parser.add_argument("--end-date", help="YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=30, help="Days back if no dates provided")
    parser.add_argument("--buyer-id", help="Optional buyer_account_id (seat ID)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    else:
        end = datetime.utcnow().date()
        start = end - timedelta(days=max(args.days, 1))
        start_date = start.strftime("%Y-%m-%d")
        end_date = end.strftime("%Y-%m-%d")

    result = await refresh_home_summaries(
        start_date,
        end_date,
        buyer_account_id=args.buyer_id,
    )
    print(f"Refreshed home cache: {result}")


if __name__ == "__main__":
    asyncio.run(main())
