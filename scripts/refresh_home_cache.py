#!/usr/bin/env python3
"""Refresh Home precompute tables for a date range.

Also refreshes RTB endpoint observed QPS so endpoint-efficiency and contracts
stay fresh when this script is the scheduled refresh path.
"""

import argparse
import asyncio

from services.endpoints_service import EndpointsService
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
    refresh_kwargs = {"buyer_account_id": args.buyer_id}
    if args.start_date and args.end_date:
        refresh_kwargs["start_date"] = args.start_date
        refresh_kwargs["end_date"] = args.end_date
    else:
        refresh_kwargs["days"] = max(args.days, 1)

    result = await refresh_home_summaries(**refresh_kwargs)
    endpoints_refreshed = await EndpointsService().refresh_endpoints_current()
    print(
        "Refreshed home cache",
        {"home": result, "endpoints_current_rows": endpoints_refreshed},
    )


if __name__ == "__main__":
    asyncio.run(main())
