"""Validation helpers for precomputed analytics tables."""

from __future__ import annotations

import logging
from typing import Any, Optional

from storage.serving_database import db_query_one

logger = logging.getLogger(__name__)


def _sum_row(row: Any, keys: list[str]) -> dict[str, int]:
    if row is None:
        return {key: 0 for key in keys}
    return {key: int(row.get(key) or 0) for key in keys}


def _compare_totals(
    name: str,
    precomputed: dict[str, int],
    raw: dict[str, int],
) -> dict[str, dict[str, int]]:
    discrepancies: dict[str, dict[str, int]] = {}
    for metric, pre_value in precomputed.items():
        raw_value = raw.get(metric, 0)
        diff = pre_value - raw_value
        if diff != 0:
            discrepancies[metric] = {
                "precomputed": pre_value,
                "raw": raw_value,
                "diff": diff,
            }
            logger.warning(
                "Precompute validation mismatch (%s) %s: precomputed=%s raw=%s diff=%s",
                name,
                metric,
                pre_value,
                raw_value,
                diff,
            )
    if not discrepancies:
        logger.info("Precompute validation OK (%s)", name)
    return discrepancies


async def validate_precompute_totals(
    start_date: str,
    end_date: str,
    buyer_account_id: Optional[str] = None,
) -> dict[str, Any]:
    """Compare totals between raw and precomputed tables for a date range."""

    # Build params for queries
    params = [start_date, end_date]
    seat_filter = ""
    if buyer_account_id:
        seat_filter = " AND buyer_account_id = ?"
        params.append(buyer_account_id)

    # Seat daily precomputed
    home_pre_row = await db_query_one(
        f"""
        SELECT
            COALESCE(SUM(reached_queries), 0) AS reached_queries,
            COALESCE(SUM(impressions), 0) AS impressions
        FROM seat_daily
        WHERE metric_date BETWEEN ? AND ?{seat_filter}
        """,
        tuple(params),
    )

    # Raw bidstream
    raw_bidstream_params = [start_date, end_date]
    raw_bidstream_filter = ""
    if buyer_account_id:
        raw_bidstream_filter = " AND buyer_account_id = ?"
        raw_bidstream_params.append(buyer_account_id)

    home_raw_row = await db_query_one(
        f"""
        SELECT
            COALESCE(SUM(reached_queries), 0) AS reached_queries,
            COALESCE(SUM(impressions), 0) AS impressions
        FROM rtb_bidstream
        WHERE metric_date BETWEEN ? AND ?
          AND buyer_account_id IS NOT NULL
          AND buyer_account_id != ''{raw_bidstream_filter}
        """,
        tuple(raw_bidstream_params),
    )

    # Pretargeting size daily precomputed
    config_pre_row = await db_query_one(
        f"""
        SELECT
            COALESCE(SUM(reached_queries), 0) AS reached_queries,
            COALESCE(SUM(impressions), 0) AS impressions,
            COALESCE(SUM(spend_micros), 0) AS spend_micros
        FROM pretarg_size_daily
        WHERE metric_date BETWEEN ? AND ?{seat_filter}
        """,
        tuple(params),
    )

    # Raw daily
    raw_daily_params = [start_date, end_date]
    raw_daily_filter = ""
    if buyer_account_id:
        raw_daily_filter = " AND buyer_account_id = ?"
        raw_daily_params.append(buyer_account_id)

    config_raw_row = await db_query_one(
        f"""
        SELECT
            COALESCE(SUM(reached_queries), 0) AS reached_queries,
            COALESCE(SUM(impressions), 0) AS impressions,
            COALESCE(SUM(spend_micros), 0) AS spend_micros
        FROM rtb_daily
        WHERE metric_date BETWEEN ? AND ?
          AND creative_size IS NOT NULL
          AND creative_size != ''{raw_daily_filter}
        """,
        tuple(raw_daily_params),
    )

    home_pre = _sum_row(home_pre_row, ["reached_queries", "impressions"])
    home_raw = _sum_row(home_raw_row, ["reached_queries", "impressions"])
    config_pre = _sum_row(
        config_pre_row,
        ["reached_queries", "impressions", "spend_micros"],
    )
    config_raw = _sum_row(
        config_raw_row,
        ["reached_queries", "impressions", "spend_micros"],
    )

    checks = {
        "home_seat_daily_vs_rtb_bidstream": {
            "precomputed": home_pre,
            "raw": home_raw,
            "discrepancies": _compare_totals(
                "home_seat_daily_vs_rtb_bidstream",
                home_pre,
                home_raw,
            ),
        },
        "config_size_daily_vs_rtb_daily": {
            "precomputed": config_pre,
            "raw": config_raw,
            "discrepancies": _compare_totals(
                "config_size_daily_vs_rtb_daily",
                config_pre,
                config_raw,
            ),
        },
    }

    return {
        "start_date": start_date,
        "end_date": end_date,
        "buyer_account_id": buyer_account_id,
        "checks": checks,
    }


async def run_precompute_validation(
    start_date: str,
    end_date: str,
    buyer_account_id: Optional[str] = None,
) -> dict[str, Any]:
    """Run validation with warnings only (no hard failure)."""
    try:
        return await validate_precompute_totals(
            start_date,
            end_date,
            buyer_account_id=buyer_account_id,
        )
    except Exception:
        logger.exception(
            "Precompute validation failed for %s to %s (buyer_account_id=%s)",
            start_date,
            end_date,
            buyer_account_id,
        )
        return {
            "start_date": start_date,
            "end_date": end_date,
            "buyer_account_id": buyer_account_id,
            "checks": {},
            "status": "failed",
        }
