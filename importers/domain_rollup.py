"""Domain rollup: top-N + __OTHER__ aggregation for web_domain_daily.

Keeps the top N domains per (metric_date, buyer_account_id, billing_id) group
and merges the remainder into a single __OTHER__ row.
"""

import os
from collections import defaultdict
from typing import List

DOMAIN_TOP_N = int(os.getenv("CATSCAN_DOMAIN_TOP_N", "200"))


def rollup_domains(rows: list[dict], top_n: int = DOMAIN_TOP_N) -> list[dict]:
    """Per (metric_date, buyer_account_id, billing_id), keep top N domains
    by ranking metric, aggregate remainder into __OTHER__.

    Ranking metric: impressions if any row in the group has impressions > 0,
    else fall back to spend_micros.
    """
    if not rows:
        return []

    # Group by (metric_date, buyer_account_id, billing_id)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("metric_date", ""),
            row.get("buyer_account_id", ""),
            row.get("billing_id", ""),
        )
        groups[key].append(row)

    result: list[dict] = []

    for group_key, group_rows in groups.items():
        if len(group_rows) <= top_n:
            result.extend(group_rows)
            continue

        # Determine ranking metric: impressions if any > 0, else spend_micros
        has_impressions = any(
            (row.get("impressions") or 0) > 0 for row in group_rows
        )
        rank_key = "impressions" if has_impressions else "spend_micros"

        # Sort descending by ranking metric
        sorted_rows = sorted(
            group_rows, key=lambda r: r.get(rank_key, 0) or 0, reverse=True
        )

        # Keep top N
        top_rows = sorted_rows[:top_n]
        remainder = sorted_rows[top_n:]

        result.extend(top_rows)

        # Aggregate remainder into __OTHER__
        other_row = dict(remainder[0])  # copy first remainder as template
        other_row["publisher_domain"] = "__OTHER__"
        other_row["impressions"] = sum(
            (r.get("impressions") or 0) for r in remainder
        )
        other_row["reached_queries"] = sum(
            (r.get("reached_queries") or 0) for r in remainder
        )
        other_row["spend_micros"] = sum(
            (r.get("spend_micros") or 0) for r in remainder
        )
        result.append(other_row)

    return result
