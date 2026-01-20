#!/usr/bin/env python3
"""Validate precomputed tables against raw data totals."""

import argparse
import asyncio
from datetime import datetime, timedelta

from services.precompute_validation import run_precompute_validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate precomputed totals.")
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

    result = await run_precompute_validation(
        start_date,
        end_date,
        buyer_account_id=args.buyer_id,
    )
    print(f"Precompute validation results: {result}")


if __name__ == "__main__":
    asyncio.run(main())
