"""Buyer-scoped data guards for recommendation generation."""

from __future__ import annotations

from storage.serving_database import db_query_one


class RecommendationDataUnavailable(RuntimeError):
    """Raised when buyer-safe recommendation inputs are unavailable."""


async def ensure_recommendation_data_available(*, buyer_id: str, days: int) -> None:
    """Require recent canonical buyer metrics before running any analyzer.

    ``rtb_buyer_spend_daily`` is populated by the scheduled RTB precompute from
    the one report shape designated as authoritative for buyer totals.  Using it
    as the gate prevents request paths from falling back to global legacy facts
    or querying ``rtb_daily`` directly.
    """
    if not buyer_id:
        raise RecommendationDataUnavailable("A buyer scope is required.")

    try:
        row = await db_query_one(
            """
            SELECT COUNT(*) AS row_count
            FROM rtb_buyer_spend_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
            """,
            (buyer_id, f"-{days} days"),
        )
    except Exception as exc:
        raise RecommendationDataUnavailable(
            "Buyer-scoped recommendation metrics are unavailable."
        ) from exc

    if not row or int(row.get("row_count", 0) or 0) == 0:
        raise RecommendationDataUnavailable(
            "Buyer-scoped recommendation metrics are unavailable."
        )
