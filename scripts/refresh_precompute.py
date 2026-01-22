#!/usr/bin/env python3
"""Refresh Home, config, and RTB precompute tables for a date range."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, timedelta

from services.config_precompute import refresh_config_breakdowns
from services.home_precompute import refresh_home_summaries
from services.precompute_validation import run_precompute_validation
from services.rtb_precompute import refresh_rtb_summaries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh precompute tables.")
    parser.add_argument("--start-date", help="YYYY-MM-DD")
    parser.add_argument("--end-date", help="YYYY-MM-DD")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Days back if no dates provided (inclusive)",
    )
    parser.add_argument("--buyer-id", help="Optional buyer_account_id (seat ID)")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run precompute validation after refresh",
    )
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> tuple[str, str]:
    if args.start_date and args.end_date:
        return args.start_date, args.end_date

    days = max(args.days, 1)
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    return start_date.isoformat(), end_date.isoformat()


async def main() -> None:
    args = parse_args()
    start_date, end_date = resolve_dates(args)
    refresh_kwargs = {"buyer_account_id": args.buyer_id}

    home_result = await refresh_home_summaries(
        start_date=start_date,
        end_date=end_date,
        **refresh_kwargs,
    )
    await refresh_config_breakdowns(
        start_date=start_date,
        end_date=end_date,
        **refresh_kwargs,
    )
    await refresh_rtb_summaries(
        start_date=start_date,
        end_date=end_date,
        **refresh_kwargs,
    )

    if args.validate:
        await run_precompute_validation(start_date, end_date)

    print(
        "Precompute refresh complete",
        {
            "home": home_result,
            "start_date": start_date,
            "end_date": end_date,
            "buyer_account_id": args.buyer_id,
            "validated": args.validate,
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
