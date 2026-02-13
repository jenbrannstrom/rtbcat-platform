"""RTB Bidstream Service - Business logic for RTB analytics.

Orchestrates repository calls, computes derived metrics (win rate, waste),
and builds response structures for RTB funnel endpoints.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from storage.postgres_repositories.rtb_bidstream_repo import RtbBidstreamRepository
from services.home_analytics_service import HomeAnalyticsService

logger = logging.getLogger(__name__)


@dataclass
class PrecomputeStatus:
    """Status of a precompute table."""
    table: str
    exists: bool
    has_rows: bool
    row_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "exists": self.exists,
            "has_rows": self.has_rows,
            "row_count": self.row_count,
        }


class RtbBidstreamService:
    """Service for RTB bidstream analytics."""

    def __init__(self):
        self._repo = RtbBidstreamRepository()

    # =========================================================================
    # Precompute Status
    # =========================================================================

    async def get_precompute_status(
        self,
        table_name: str,
        days: int,
        filters: Optional[list[str]] = None,
        params: Optional[list] = None,
    ) -> PrecomputeStatus:
        """Check if a precompute table exists and has data."""
        exists = await self._repo.table_exists(table_name)
        if not exists:
            return PrecomputeStatus(
                table=table_name,
                exists=False,
                has_rows=False,
                row_count=0,
            )

        row_count = await self._repo.get_precompute_row_count(
            table_name, days, filters, params
        )
        return PrecomputeStatus(
            table=table_name,
            exists=True,
            has_rows=row_count > 0,
            row_count=row_count,
        )

    # =========================================================================
    # Billing ID Helpers
    # =========================================================================

    async def get_valid_billing_ids_for_buyer(
        self,
        buyer_id: Optional[str] = None,
    ) -> list[str]:
        """Get valid billing IDs for a buyer seat."""
        try:
            if buyer_id:
                bidder_id = await self._repo.get_bidder_id_for_buyer(buyer_id)
                if bidder_id:
                    return await self._repo.get_billing_ids_for_bidder(bidder_id)

            # Fallback: return all billing_ids
            return await self._repo.get_billing_ids_for_bidder(None)
        except Exception as e:
            logger.error(f"Failed to get billing IDs for buyer {buyer_id}: {e}")
            return []

    # =========================================================================
    # RTB Funnel Summary
    # =========================================================================

    async def get_rtb_funnel(
        self,
        days: int,
        buyer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get RTB funnel analysis with publishers and geos."""
        # Check precompute status
        buyer_filters = ["buyer_account_id = %s"] if buyer_id else None
        buyer_params = [buyer_id] if buyer_id else None

        funnel_status = await self.get_precompute_status(
            "rtb_funnel_daily", days, buyer_filters, buyer_params
        )
        publisher_status = await self.get_precompute_status(
            "rtb_publisher_daily", days, buyer_filters, buyer_params
        )
        geo_status = await self.get_precompute_status(
            "rtb_geo_daily", days, buyer_filters, buyer_params
        )

        buyer_filter_applied = buyer_id is not None
        buyer_filter_message = None

        if not funnel_status.has_rows:
            buyer_filter_message = (
                "No precompute available for this seat. Run an RTB refresh after imports."
                if buyer_id
                else "No precompute available for requested date range."
            )
            if buyer_id:
                buyer_filter_applied = False
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
                    "buyer_filter_message": buyer_filter_message,
                    "bidder_id_populated": None,
                    "buyer_account_id_populated": None,
                    "precompute_status": {
                        "rtb_funnel_daily": funnel_status.to_dict(),
                        "rtb_publisher_daily": publisher_status.to_dict(),
                        "rtb_geo_daily": geo_status.to_dict(),
                    },
                },
            }

        # Get funnel summary
        funnel_row = await self._repo.get_funnel_summary(days, buyer_id)
        total_reached = funnel_row["total_reached"] or 0 if funnel_row else 0
        total_impressions = funnel_row["total_impressions"] or 0 if funnel_row else 0
        total_bids = funnel_row["total_bids"] or 0 if funnel_row else 0
        total_successful = funnel_row["total_successful_responses"] or 0 if funnel_row else 0
        total_bid_requests = funnel_row["total_bid_requests"] or 0 if funnel_row else 0

        effective_reached = total_reached
        if effective_reached == 0:
            effective_reached = total_successful or total_bid_requests

        win_rate = (total_impressions / effective_reached * 100) if effective_reached > 0 else 0
        waste_rate = 100 - win_rate

        # Get publisher breakdown
        publishers = []
        if publisher_status.has_rows:
            pub_rows = await self._repo.get_publisher_breakdown(days, buyer_id, 10)
            publishers = self._build_publisher_list(pub_rows)

        # Get geo breakdown
        geos = []
        if geo_status.has_rows:
            geo_rows = await self._repo.get_geo_breakdown(days, buyer_id, 10)
            geos = self._build_geo_list(geo_rows)

        # Get counts
        publisher_count = 0
        country_count = 0
        if publisher_status.has_rows:
            publisher_count = await self._repo.get_publisher_count(days, buyer_id)
        if geo_status.has_rows:
            country_count = await self._repo.get_country_count(days, buyer_id)

        precompute_messages = {}
        if not publisher_status.has_rows:
            precompute_messages["publishers"] = "No precompute available for publisher breakdown."
        if not geo_status.has_rows:
            precompute_messages["geos"] = "No precompute available for geo breakdown."

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
                "bidder_id_populated": None,
                "buyer_account_id_populated": None,
                "precompute_messages": precompute_messages,
                "precompute_status": {
                    "rtb_funnel_daily": funnel_status.to_dict(),
                    "rtb_publisher_daily": publisher_status.to_dict(),
                    "rtb_geo_daily": geo_status.to_dict(),
                },
            },
        }

    # =========================================================================
    # Publisher Breakdown
    # =========================================================================

    async def get_publishers(
        self,
        days: int,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Get publisher performance breakdown."""
        status = await self.get_precompute_status("rtb_publisher_daily", days)
        if not status.has_rows:
            return {
                "publishers": [],
                "count": 0,
                "period_days": days,
                "message": "No precompute available for requested date range.",
                "precompute_status": {"rtb_publisher_daily": status.to_dict()},
            }

        rows = await self._repo.get_publisher_breakdown(days, None, limit)
        count = await self._repo.get_publisher_count(days, None)

        publishers = []
        for row in rows:
            reached = row["reached"] or 0
            imps = row["total_impressions"] if "total_impressions" in row else row.get("impressions", 0) or 0
            bids = row["total_bids"] or 0
            win_rate = (imps / reached * 100) if reached > 0 else 0
            bid_rate = (bids / reached * 100) if reached > 0 else 0

            pub_name = self._normalize_publisher_name(
                row.get("publisher_name"), row["publisher_id"]
            )

            publishers.append({
                "publisher_id": row["publisher_id"],
                "publisher_name": pub_name,
                "reached_queries": reached,
                "impressions": imps,
                "bids": bids,
                "win_rate": round(win_rate, 2),
                "bid_rate": round(bid_rate, 2),
                "waste_pct": round(100 - win_rate, 2),
            })

        return {
            "publishers": publishers,
            "count": count,
            "period_days": days,
            "precompute_status": {"rtb_publisher_daily": status.to_dict()},
        }

    # =========================================================================
    # Geo Breakdown
    # =========================================================================

    async def get_geos(
        self,
        days: int,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Get geographic performance breakdown."""
        status = await self.get_precompute_status("rtb_geo_daily", days)
        if not status.has_rows:
            return {
                "geos": [],
                "count": 0,
                "period_days": days,
                "message": "No precompute available for requested date range.",
                "precompute_status": {"rtb_geo_daily": status.to_dict()},
            }

        rows = await self._repo.get_geo_breakdown(days, None, limit)
        count = await self._repo.get_country_count(days, None)

        geos = []
        for row in rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            win_rate = (imps / reached * 100) if reached > 0 else 0
            bid_rate = (bids / reached * 100) if reached > 0 else 0

            geos.append({
                "country": row["country"],
                "reached_queries": reached,
                "impressions": imps,
                "bids": bids,
                "win_rate": round(win_rate, 2),
                "bid_rate": round(bid_rate, 2),
                "waste_pct": round(100 - win_rate, 2),
            })

        return {
            "geos": geos,
            "count": count,
            "period_days": days,
            "precompute_status": {"rtb_geo_daily": status.to_dict()},
        }

    # =========================================================================
    # Config Performance
    # =========================================================================

    async def get_config_performance(
        self,
        days: int,
        buyer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get performance breakdown by pretargeting config (billing_id).

        This endpoint now reads from home precompute tables to avoid costly
        runtime scans/aggregations from config_size/fact tables on Home loads.
        """
        payload = await HomeAnalyticsService().get_config_payload(
            days=days,
            buyer_id=buyer_id,
        )
        payload["total_configs"] = len(payload.get("configs", []))
        return payload

    # =========================================================================
    # Config Breakdown
    # =========================================================================

    async def get_config_breakdown(
        self,
        billing_id: str,
        breakdown_type: str,
        days: int,
        buyer_account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get detailed breakdown for a specific config."""
        table_map = {
            "size": "config_size_daily",
            "geo": "config_geo_daily",
            "publisher": "config_publisher_daily",
            "creative": "config_creative_daily",
        }
        table_name = table_map.get(breakdown_type)

        if table_name:
            filters = ["billing_id = %s"]
            params = [billing_id]
            if buyer_account_id:
                filters.append("buyer_account_id = %s")
                params.append(buyer_account_id)

            status = await self.get_precompute_status(table_name, days, filters, params)

            if not status.exists and breakdown_type not in ("geo", "publisher"):
                return {
                    "billing_id": billing_id,
                    "breakdown_by": breakdown_type,
                    "breakdown": [],
                    "is_aggregate": False,
                    "has_funnel_metrics": False,
                    "no_data_reason": (
                        "Config breakdown tables are missing. Run migration 020 and "
                        "recompute config breakdowns."
                    ),
                }

            if not status.has_rows and breakdown_type not in ("geo", "publisher"):
                return {
                    "billing_id": billing_id,
                    "breakdown_by": breakdown_type,
                    "breakdown": [],
                    "is_aggregate": False,
                    "has_funnel_metrics": False,
                    "no_data_reason": (
                        "No precompute available for requested date range. "
                        "Run a config refresh after imports."
                    ),
                    "precompute_status": {table_name: status.to_dict()},
                }

        # Get target countries for creative breakdown (language mismatch check)
        target_geo_ids: list[str] = []
        target_country_codes: list[str] = []
        if breakdown_type == "creative":
            target_geo_ids, target_country_codes = await self._get_config_target_countries(
                billing_id
            )

        # Fetch breakdown data
        rows = await self._get_breakdown_rows(
            breakdown_type, billing_id, days, buyer_account_id
        )

        if not rows:
            reason_map = {
                "geo": "No geo breakdown data. Billing-level CSV data is not available for this config.",
                "publisher": "No publisher breakdown data. Billing-level CSV data is not available for this config.",
                "creative": "No creative breakdown data. Run a config precompute refresh after importing catscan-quality.",
                "size": "No size breakdown data. Run a config precompute refresh after importing catscan-quality.",
            }
            return {
                "billing_id": billing_id,
                "breakdown_by": breakdown_type,
                "breakdown": [],
                "is_aggregate": False,
                "has_funnel_metrics": False,
                "no_data_reason": reason_map.get(breakdown_type, "No data available."),
                "data_state": "unavailable",
                "fallback_applied": False,
                "fallback_reason": "no_canonical_rows",
            }

        # Build breakdown items
        breakdown = self._build_breakdown_items(
            rows, breakdown_type, target_geo_ids, target_country_codes
        )
        return {
            "billing_id": billing_id,
            "breakdown_by": breakdown_type,
            "breakdown": breakdown,
            "is_aggregate": False,
            "has_funnel_metrics": any(item.get("bids_in_auction", 0) > 0 for item in breakdown),
            "data_state": "healthy",
            "fallback_applied": False,
            "fallback_reason": None,
        }

    async def _get_breakdown_rows(
        self,
        breakdown_type: str,
        billing_id: str,
        days: int,
        buyer_account_id: Optional[str],
    ) -> list[dict[str, Any]]:
        """Fetch breakdown rows from appropriate table."""
        if breakdown_type == "geo":
            return await self._repo.get_config_breakdown_geo(
                billing_id, days, buyer_account_id
            )
        elif breakdown_type == "publisher":
            return await self._repo.get_config_breakdown_publisher(
                billing_id, days, buyer_account_id
            )
        elif breakdown_type == "creative":
            return await self._repo.get_config_breakdown_creative(
                billing_id, days, buyer_account_id
            )
        else:  # size
            return await self._repo.get_config_breakdown_size(
                billing_id, days, buyer_account_id
            )

    async def _get_config_target_countries(
        self,
        billing_id: str,
    ) -> tuple[list[str], list[str]]:
        """Get target geo IDs and country codes for a config."""
        geo_ids: list[str] = []
        country_codes: list[str] = []

        included_geos_json = await self._repo.get_pretargeting_config_geos(billing_id)
        if included_geos_json:
            try:
                geo_ids = json.loads(included_geos_json) or []
            except (TypeError, json.JSONDecodeError):
                geo_ids = []

        if geo_ids:
            country_codes = await self._repo.get_country_codes_for_geo_ids(geo_ids)

        return geo_ids, country_codes

    def _build_breakdown_items(
        self,
        rows: list[dict[str, Any]],
        breakdown_type: str,
        target_geo_ids: list[str],
        target_country_codes: list[str],
    ) -> list[dict[str, Any]]:
        """Build breakdown item list with computed metrics."""
        breakdown = []

        for row in rows:
            reached = row["total_reached"] or 0
            impressions = row["total_impressions"] or 0
            bids = row.get("total_bids", 0) or 0
            bids_in_auction = row.get("total_bids_in_auction", 0) or 0
            auctions_won = row.get("total_auctions_won", 0) or 0
            spend_micros = row.get("total_spend_micros", 0) or 0

            # Calculate win rate
            if bids_in_auction > 0:
                win_rate = (auctions_won / bids_in_auction * 100)
            elif reached > 0:
                win_rate = (impressions / reached * 100)
            else:
                win_rate = 0

            item = {
                "name": row["name"] or "Unknown",
                "reached": reached,
                "impressions": impressions,
                "win_rate": round(win_rate, 1),
                "waste_rate": round(100 - win_rate, 1),
                "spend_usd": round(spend_micros / 1_000_000, 2),
                "data_scope": row.get("data_scope", "billing"),
                "data_source": row.get("data_source", "csv"),
            }

            if row.get("target_value"):
                item["target_value"] = str(row["target_value"])

            if bids > 0 or bids_in_auction > 0:
                item["bids"] = bids
                item["bids_in_auction"] = bids_in_auction
                item["auctions_won"] = auctions_won

            if breakdown_type == "creative":
                item = self._add_language_info(
                    item, row, target_geo_ids, target_country_codes
                )

            breakdown.append(item)

        return breakdown

    def _add_language_info(
        self,
        item: dict[str, Any],
        row: dict[str, Any],
        target_geo_ids: list[str],
        target_country_codes: list[str],
    ) -> dict[str, Any]:
        """Add language and mismatch info to creative breakdown item."""
        language_code = row.get("detected_language_code")
        language_name = row.get("detected_language")
        item["creative_language"] = language_name or language_code
        item["creative_language_code"] = language_code

        if target_country_codes:
            try:
                from utils.language_country_map import check_language_country_match
                from utils.country_codes import get_country_alpha3

                match = check_language_country_match(language_code or "", target_country_codes)
                mismatched = [get_country_alpha3(code) for code in match["mismatched_countries"]]
                item["target_countries"] = [get_country_alpha3(code) for code in target_country_codes]
                item["language_mismatch"] = len(mismatched) > 0 and bool(language_code)
                item["mismatched_countries"] = mismatched
            except Exception:
                item["target_countries"] = target_country_codes
                item["language_mismatch"] = False
                item["mismatched_countries"] = []
        elif target_geo_ids:
            item["target_countries"] = target_geo_ids
            item["language_mismatch"] = False
        else:
            item["target_countries"] = []
            item["language_mismatch"] = False

        return item

    # =========================================================================
    # Config Creatives
    # =========================================================================

    async def get_config_creatives(
        self,
        billing_id: str,
        days: int,
        buyer_account_id: Optional[str] = None,
        size: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get creatives for a config, optionally filtered by size."""
        filters = ["billing_id = %s"]
        params = [billing_id]
        if buyer_account_id:
            filters.append("buyer_account_id = %s")
            params.append(buyer_account_id)

        status = await self.get_precompute_status(
            "config_creative_daily", days, filters, params
        )

        if not status.has_rows:
            return {
                "creatives": [],
                "message": "No precompute available for requested date range.",
                "precompute_status": {"config_creative_daily": status.to_dict()},
            }

        creative_ids = await self._repo.get_config_creative_ids(
            billing_id, days, buyer_account_id, size
        )

        if not creative_ids:
            return {
                "creatives": [],
                "precompute_status": {"config_creative_daily": status.to_dict()},
            }

        creative_rows = await self._repo.get_creatives_by_ids(creative_ids)
        creative_map = {row["id"]: row for row in creative_rows}

        creatives = []
        for creative_id in creative_ids:
            row = creative_map.get(creative_id)
            creatives.append({
                "id": creative_id,
                "name": row["name"] if row and row.get("name") else creative_id,
                "format": row["format"] if row else None,
                "width": row["width"] if row else None,
                "height": row["height"] if row else None,
                "serving_countries": [],
            })

        return {
            "creatives": creatives,
            "precompute_status": {"config_creative_daily": status.to_dict()},
        }

    # =========================================================================
    # App Drilldown
    # =========================================================================

    async def get_app_drilldown(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get detailed breakdown for an app/publisher."""
        # Check precompute status
        filters = ["app_name = %s"]
        params = [app_name]
        if billing_id:
            filters.append("billing_id = %s")
            params.append(billing_id)

        app_summary_status = await self.get_precompute_status(
            "rtb_app_daily", days, filters, params
        )
        app_size_status = await self.get_precompute_status(
            "rtb_app_size_daily", days, filters, params
        )
        app_country_status = await self.get_precompute_status(
            "rtb_app_country_daily", days, filters, params
        )
        app_creative_status = await self.get_precompute_status(
            "rtb_app_creative_daily", days, filters, params
        )

        if not app_summary_status.has_rows:
            fallback_message = "No precompute available for requested date range."
            if billing_id:
                # Check if data exists for this app at all
                total_status = await self.get_precompute_status(
                    "rtb_app_daily", days, ["app_name = %s"], [app_name]
                )
                if total_status.has_rows:
                    fallback_message = (
                        f"Data exists for '{app_name}' but not for this specific "
                        f"pretargeting config (billing_id={billing_id}). "
                        "Run RTB precompute for that config."
                    )

            return {
                "app_name": app_name,
                "has_data": False,
                "message": fallback_message,
                "precompute_status": {
                    "rtb_app_daily": app_summary_status.to_dict(),
                    "rtb_app_size_daily": app_size_status.to_dict(),
                    "rtb_app_country_daily": app_country_status.to_dict(),
                    "rtb_app_creative_daily": app_creative_status.to_dict(),
                },
            }

        # Get app summary
        summary_row = await self._repo.get_app_summary(app_name, days, billing_id)
        total_reached = summary_row["total_reached"] or 0 if summary_row else 0
        total_impressions = summary_row["total_impressions"] or 0 if summary_row else 0
        win_rate = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        # Get counts
        creative_count = await self._repo.get_app_creative_count(app_name, days, billing_id)
        country_count = await self._repo.get_app_country_count(app_name, days, billing_id)

        # Get breakdowns
        sizes = await self._build_app_sizes(app_name, days, billing_id, total_reached, win_rate)
        countries = await self._build_app_countries(app_name, days, billing_id, total_reached)
        creatives = await self._build_app_creatives(app_name, days, billing_id, total_reached)

        # Get bid filtering data
        creative_ids = [c["creative_id"] for c in creatives]
        bid_filtering = await self._get_bid_filtering(creative_ids, days)

        # Identify wasteful sizes
        wasteful_sizes = [s for s in sizes if s.get("is_wasteful")]
        waste_insight = None
        if wasteful_sizes:
            worst = max(wasteful_sizes, key=lambda x: x["reached"])
            waste_insight = {
                "type": "size",
                "value": worst["size"],
                "message": (
                    f"{worst['size']} has only {worst['win_rate']}% win rate but accounts for "
                    f"{worst['pct_of_traffic']}% of traffic"
                ),
                "wasted_queries": int(worst["reached"] * (1 - worst["win_rate"] / 100)),
                "recommendation": f"Consider removing {worst['size']} from pretargeting for this app",
            }

        return {
            "app_name": app_name,
            "app_id": summary_row["app_id"] if summary_row else None,
            "has_data": True,
            "period_days": days,
            "summary": {
                "total_reached": total_reached,
                "total_impressions": total_impressions,
                "total_clicks": summary_row["total_clicks"] or 0 if summary_row else 0,
                "total_spend_usd": (summary_row["total_spend_micros"] or 0) / 1_000_000 if summary_row else 0,
                "win_rate": round(win_rate, 1),
                "waste_rate": round(100 - win_rate, 1),
                "days_with_data": summary_row["days_with_data"] if summary_row else 0,
                "creative_count": creative_count,
                "country_count": country_count,
            },
            "by_size": sizes,
            "by_country": countries,
            "by_creative": creatives,
            "waste_insight": waste_insight,
            "bid_filtering": bid_filtering,
            "precompute_status": {
                "rtb_app_daily": app_summary_status.to_dict(),
                "rtb_app_size_daily": app_size_status.to_dict(),
                "rtb_app_country_daily": app_country_status.to_dict(),
                "rtb_app_creative_daily": app_creative_status.to_dict(),
            },
        }

    async def _build_app_sizes(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str],
        total_reached: int,
        overall_win_rate: float,
    ) -> list[dict[str, Any]]:
        """Build app size breakdown."""
        rows = await self._repo.get_app_size_breakdown(app_name, days, billing_id)
        sizes = []
        for row in rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            size_win_rate = (imps / reached * 100) if reached > 0 else 0
            is_wasteful = size_win_rate < (overall_win_rate * 0.5) and reached > 10000

            sizes.append({
                "size": row["creative_size"],
                "format": row["creative_format"],
                "reached": reached,
                "impressions": imps,
                "clicks": row["clicks"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "win_rate": round(size_win_rate, 1),
                "waste_pct": round(100 - size_win_rate, 1),
                "pct_of_traffic": round(reached / total_reached * 100, 1) if total_reached > 0 else 0,
                "is_wasteful": is_wasteful,
            })
        return sizes

    async def _build_app_countries(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str],
        total_reached: int,
    ) -> list[dict[str, Any]]:
        """Build app country breakdown."""
        rows = await self._repo.get_app_country_breakdown(app_name, days, billing_id)
        countries = []
        for row in rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            country_win_rate = (imps / reached * 100) if reached > 0 else 0

            countries.append({
                "country": row["country"],
                "reached": reached,
                "impressions": imps,
                "clicks": row["clicks"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "win_rate": round(country_win_rate, 1),
                "pct_of_traffic": round(reached / total_reached * 100, 1) if total_reached > 0 else 0,
            })
        return countries

    async def _build_app_creatives(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str],
        total_reached: int,
    ) -> list[dict[str, Any]]:
        """Build app creative breakdown."""
        rows = await self._repo.get_app_creative_breakdown(app_name, days, billing_id)
        creatives = []
        for row in rows:
            reached = row["reached"] or 0
            imps = row["impressions"] or 0
            creative_win_rate = (imps / reached * 100) if reached > 0 else 0

            creatives.append({
                "creative_id": row["creative_id"],
                "size": row["creative_size"],
                "format": row["creative_format"],
                "reached": reached,
                "impressions": imps,
                "clicks": row["clicks"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "win_rate": round(creative_win_rate, 1),
                "pct_of_traffic": round(reached / total_reached * 100, 1) if total_reached > 0 else 0,
            })
        return creatives

    async def _get_bid_filtering(
        self,
        creative_ids: list[str],
        days: int,
    ) -> list[dict[str, Any]]:
        """Get bid filtering data for creatives."""
        if not creative_ids:
            return []

        try:
            # Check if table exists
            if not await self._repo.table_exists("rtb_bid_filtering"):
                return []

            rows = await self._repo.get_bid_filtering_for_creatives(creative_ids, days)
            if not rows:
                return []

            total_filtered_bids = sum(r["total_bids"] or 0 for r in rows)

            result = []
            for row in rows:
                bids = row["total_bids"] or 0
                passed = row["bids_passed"] or 0
                result.append({
                    "reason": row["filtering_reason"],
                    "bids_filtered": bids,
                    "bids_passed": passed,
                    "pct_of_filtered": round(bids / total_filtered_bids * 100, 1) if total_filtered_bids > 0 else 0,
                    "opportunity_cost_usd": (row["opportunity_cost_micros"] or 0) / 1_000_000,
                })
            return result
        except Exception as e:
            logger.warning(f"Could not fetch bid filtering data: {e}")
            return []

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_publisher_list(
        self,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build publisher list with computed metrics."""
        publishers = []
        for row in rows:
            reached = row["reached"] or 0
            if reached == 0:
                reached = (row.get("successful_responses") or 0) or (row.get("bid_requests") or 0)

            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            wins = row.get("auctions_won") or 0
            win_rate = (imps / reached * 100) if reached > 0 else 0

            pub_name = self._normalize_publisher_name(
                row.get("publisher_name"), row["publisher_id"]
            )

            publishers.append({
                "publisher_id": row["publisher_id"],
                "publisher_name": pub_name,
                "reached_queries": reached,
                "bids": bids,
                "impressions": imps,
                "auctions_won": wins,
                "win_rate": round(win_rate, 2),
            })
        return publishers

    def _build_geo_list(
        self,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build geo list with computed metrics."""
        geos = []
        for row in rows:
            reached = row["reached"] or 0
            if reached == 0:
                reached = (row.get("successful_responses") or 0) or (row.get("bid_requests") or 0)

            imps = row["impressions"] or 0
            bids = row["total_bids"] or 0
            wins = row.get("auctions_won") or 0
            win_rate = (imps / reached * 100) if reached > 0 else 0

            geos.append({
                "country": row["country"],
                "reached_queries": reached,
                "bids": bids,
                "impressions": imps,
                "auctions_won": wins,
                "win_rate": round(win_rate, 2),
            })
        return geos

    def _normalize_publisher_name(
        self,
        publisher_name: Optional[str],
        publisher_id: str,
    ) -> str:
        """Normalize publisher name, handling NULL/empty/whitespace."""
        if publisher_name and publisher_name.strip():
            return publisher_name.strip()
        if publisher_id and str(publisher_id).strip():
            return publisher_id
        return "Unknown publisher"
