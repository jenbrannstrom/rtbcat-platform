"""Service layer for home analytics endpoints."""

from __future__ import annotations

from typing import Any

from storage.postgres_repositories.home_repo import HomeAnalyticsRepository
from api.routers.analytics.common import get_precompute_status


class HomeAnalyticsService:
    """Orchestrates home analytics responses."""

    def __init__(self, repo: HomeAnalyticsRepository | None = None) -> None:
        self._repo = repo or HomeAnalyticsRepository()

    async def get_funnel_payload(
        self,
        days: int,
        buyer_id: str | None,
        limit: int,
    ) -> dict[str, Any]:
        seat_status = await get_precompute_status(
            "home_seat_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        publisher_status = await get_precompute_status(
            "home_publisher_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        geo_status = await get_precompute_status(
            "home_geo_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )

        buyer_filter_applied = bool(buyer_id)
        buyer_filter_message = None

        if not seat_status["has_rows"]:
            if buyer_id:
                buyer_filter_applied = False
                buyer_filter_message = (
                    "No precomputed data for this seat. Run a refresh after imports."
                )
            return {
                "has_data": False,
                "funnel": {
                    "total_reached_queries": 0,
                    "total_impressions": 0,
                    "total_bids": 0,
                    "win_rate": 0,
                    "waste_rate": 100,
                },
                "publishers": [],
                "geos": [],
                "data_sources": {
                    "publisher_count": 0,
                    "country_count": 0,
                    "period_days": days,
                    "buyer_filter_applied": buyer_filter_applied,
                    "buyer_filter_message": buyer_filter_message or (
                        "No precompute available for requested date range."
                    ),
                    "precomputed": True,
                    "precompute_status": {
                        "home_seat_daily": seat_status,
                        "home_publisher_daily": publisher_status,
                        "home_geo_daily": geo_status,
                    },
                },
            }

        funnel_row = await self._repo.get_funnel_row(days, buyer_id)

        total_reached = (funnel_row["total_reached"] or 0) if funnel_row else 0
        total_impressions = (funnel_row["total_impressions"] or 0) if funnel_row else 0
        total_bids = (funnel_row["total_bids"] or 0) if funnel_row else 0
        total_successful = (
            (funnel_row["total_successful_responses"] or 0) if funnel_row else 0
        )
        total_bid_requests = (funnel_row["total_bid_requests"] or 0) if funnel_row else 0

        effective_reached = total_reached or total_successful or total_bid_requests
        win_rate = (total_impressions / effective_reached * 100) if effective_reached > 0 else 0
        waste_rate = 100 - win_rate

        publisher_rows = await self._repo.get_publisher_rows(days, buyer_id, limit)
        publishers = []
        for row in publisher_rows:
            reached = row["reached"] or 0
            if reached == 0:
                reached = (row["successful_responses"] or 0) or (row["bid_requests"] or 0)
            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            wins = row["auctions_won"] or 0
            pub_win_rate = (imps / reached * 100) if reached > 0 else 0
            raw_name = row["publisher_name"]
            name = (raw_name or "").strip() or "Unknown publisher"
            publishers.append(
                {
                    "publisher_id": row["publisher_id"],
                    "publisher_name": name,
                    "reached_queries": reached,
                    "bids": bids,
                    "impressions": imps,
                    "auctions_won": wins,
                    "win_rate": round(pub_win_rate, 2),
                }
            )

        geo_rows = await self._repo.get_geo_rows(days, buyer_id, limit)
        geos = []
        for row in geo_rows:
            reached = row["reached"] or 0
            if reached == 0:
                reached = (row["successful_responses"] or 0) or (row["bid_requests"] or 0)
            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            wins = row["auctions_won"] or 0
            geo_win_rate = (imps / reached * 100) if reached > 0 else 0
            geos.append(
                {
                    "country": row["country"],
                    "reached_queries": reached,
                    "bids": bids,
                    "impressions": imps,
                    "auctions_won": wins,
                    "win_rate": round(geo_win_rate, 2),
                }
            )

        if buyer_id and total_reached == 0 and total_impressions == 0:
            buyer_filter_applied = False
            buyer_filter_message = (
                "No precomputed data for this seat. Run a refresh after imports."
            )

        publisher_count = await self._repo.get_publisher_count(days, buyer_id)
        country_count = await self._repo.get_country_count(days, buyer_id)

        return {
            "has_data": effective_reached > 0,
            "funnel": {
                "total_reached_queries": effective_reached,
                "total_impressions": total_impressions,
                "total_bids": total_bids,
                "win_rate": round(win_rate, 2),
                "waste_rate": round(waste_rate, 2),
            },
            "publishers": publishers,
            "geos": geos,
            "data_sources": {
                "publisher_count": publisher_count,
                "country_count": country_count,
                "period_days": days,
                "buyer_filter_applied": buyer_filter_applied,
                "buyer_filter_message": buyer_filter_message,
                "precomputed": True,
                "precompute_status": {
                    "home_seat_daily": seat_status,
                    "home_publisher_daily": publisher_status,
                    "home_geo_daily": geo_status,
                },
            },
        }

    async def get_config_payload(self, days: int, buyer_id: str | None) -> dict[str, Any]:
        config_status = await get_precompute_status(
            "home_config_daily",
            days,
            filters=["buyer_account_id = ?"] if buyer_id else None,
            params=[buyer_id] if buyer_id else None,
        )
        if not config_status["has_rows"]:
            return {
                "period_days": days,
                "data_source": "home_precompute",
                "message": "No precompute available for requested date range.",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
                "precompute_status": {"home_config_daily": config_status},
            }

        rows = await self._repo.get_config_rows(days, buyer_id)
        if not rows:
            return {
                "period_days": days,
                "data_source": "home_precompute",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
            }

        configs = []
        total_reached = 0
        total_impressions = 0

        for row in rows:
            reached = row["total_reached"] or 0
            impressions = row["total_impressions"] or 0
            bids_in_auction = row["total_bids_in_auction"] or 0
            auctions_won = row["total_auctions_won"] or 0

            if bids_in_auction > 0:
                win_rate = (auctions_won / bids_in_auction * 100)
            elif reached > 0:
                win_rate = (impressions / reached * 100)
            else:
                win_rate = 0

            total_reached += reached
            total_impressions += impressions

            configs.append(
                {
                    "billing_id": row["billing_id"],
                    "name": f"Config {row['billing_id']}",
                    "reached": reached,
                    "bids": 0,
                    "impressions": impressions,
                    "win_rate_pct": round(win_rate, 1),
                    "waste_pct": round(100 - win_rate, 1),
                    "settings": {
                        "format": "BANNER",
                        "geos": [],
                        "platforms": [],
                        "qps_limit": None,
                        "budget_usd": None,
                    },
                    "sizes": [],
                }
            )

        overall_win = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        return {
            "period_days": days,
            "data_source": "home_precompute",
            "configs": configs[:20],
            "total_reached": total_reached,
            "total_impressions": total_impressions,
            "overall_win_rate_pct": round(overall_win, 1),
            "overall_waste_pct": round(100 - overall_win, 1),
            "precompute_status": {"home_config_daily": config_status},
        }
