"""Helpers for estimating traffic cost from account performance data.

Savings calculations in analytics should prefer account-derived performance data.
When recent spend/query data is unavailable, fall back to a deterministic format
profile so estimates remain stable and explainable.
"""

from __future__ import annotations

import logging
from typing import Optional

from storage.serving_database import db_query_one

logger = logging.getLogger(__name__)

# Legacy baseline used before account-derived estimation existed.
DEFAULT_REQUEST_COST_PER_1000 = 0.002

# Static fallback profile (CPM in USD) by creative format.
FALLBACK_CPM_BY_FORMAT_USD = {
    "BANNER": 0.008,
    "NATIVE": 0.012,
    "VIDEO": 0.024,
}

# Convert CPM (per 1000 impressions) into a request-cost estimate by applying
# a conservative default win-rate.
ASSUMED_WIN_RATE_FOR_CPM_FALLBACK = 0.25

# Guardrails for noisy low-volume windows and bad data spikes.
MIN_RELIABLE_VOLUME = 1000
MAX_REASONABLE_REQUEST_COST_PER_1000 = 50.0

FORMAT_ALIASES = {
    "DISPLAY": "BANNER",
    "HTML": "BANNER",
    "HTML5": "BANNER",
}


def normalize_format(format_hint: Optional[str]) -> str:
    """Normalize creative format names to known buckets."""
    fmt = (format_hint or "BANNER").strip().upper()
    return FORMAT_ALIASES.get(fmt, fmt)


def fallback_request_cost_per_1000(format_hint: Optional[str] = None) -> float:
    """Return deterministic fallback request-cost estimate."""
    fmt = normalize_format(format_hint)
    cpm = FALLBACK_CPM_BY_FORMAT_USD.get(fmt, FALLBACK_CPM_BY_FORMAT_USD["BANNER"])
    request_cost = cpm * ASSUMED_WIN_RATE_FOR_CPM_FALLBACK
    return round(request_cost, 6)


def _is_reasonable_cost(cost_per_1000: float) -> bool:
    return 0 < cost_per_1000 <= MAX_REASONABLE_REQUEST_COST_PER_1000


async def resolve_request_cost_per_1000(
    days: int,
    buyer_id: Optional[str] = None,
    format_hint: Optional[str] = None,
) -> float:
    """Resolve effective cost-per-1000-requests for the target account window.

    Priority:
    1) Use account spend/reached_queries data (most direct request-cost signal).
    2) If reached_queries is missing, approximate from spend/impressions CPM.
    3) Fall back to static format profile.
    """
    if days <= 0:
        return fallback_request_cost_per_1000(format_hint)

    query = """
        SELECT
            COALESCE(SUM(pm.spend_micros), 0) AS spend_micros,
            COALESCE(SUM(pm.reached_queries), 0) AS reached_queries,
            COALESCE(SUM(pm.impressions), 0) AS impressions
        FROM performance_metrics pm
        JOIN creatives c ON c.id = pm.creative_id
        WHERE pm.metric_date >= date('now', ?)
    """
    params: list = [f"-{days} days"]

    if buyer_id:
        query += " AND c.buyer_id = ?"
        params.append(buyer_id)

    row = await db_query_one(query, tuple(params)) or {}

    spend_micros = row.get("spend_micros", 0) or 0
    reached_queries = row.get("reached_queries", 0) or 0
    impressions = row.get("impressions", 0) or 0

    if spend_micros <= 0:
        return fallback_request_cost_per_1000(format_hint)

    spend_usd = spend_micros / 1_000_000

    if reached_queries >= MIN_RELIABLE_VOLUME:
        request_cost = (spend_usd / reached_queries) * 1000
        if _is_reasonable_cost(request_cost):
            return round(request_cost, 6)

    if impressions >= MIN_RELIABLE_VOLUME:
        derived_cpm = (spend_usd / impressions) * 1000
        request_cost = derived_cpm * ASSUMED_WIN_RATE_FOR_CPM_FALLBACK
        if _is_reasonable_cost(request_cost):
            return round(request_cost, 6)

    fallback = fallback_request_cost_per_1000(format_hint)
    logger.debug(
        "Using fallback request cost per 1000 (buyer_id=%s, days=%s, format=%s): %s",
        buyer_id,
        days,
        format_hint,
        fallback,
    )
    return fallback
