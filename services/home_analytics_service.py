"""Service layer for home analytics endpoints."""

from __future__ import annotations

import asyncio
import copy
import time
from typing import Any

from storage.postgres_repositories.home_repo import HomeAnalyticsRepository
from services.analytics_service import AnalyticsService

_analytics_service: AnalyticsService | None = None


def _get_analytics_service() -> AnalyticsService:
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service


async def _get_precompute_status(
    table_name: str,
    days: int,
    filters: list[str] | None = None,
    params: list[str] | None = None,
) -> dict[str, Any]:
    status = await _get_analytics_service().get_precompute_status(
        table_name=table_name,
        days=days,
        filters=filters,
        params=params,
    )
    return {
        "table": status.table,
        "exists": status.exists,
        "has_rows": status.has_rows,
        "row_count": status.row_count,
    }


class HomeAnalyticsService:
    """Orchestrates home analytics responses."""

    _PAYLOAD_CACHE_TTL_SECONDS = 15.0
    _FUNNEL_PAYLOAD_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
    _CONFIG_PAYLOAD_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
    _ENDPOINT_EFFICIENCY_PAYLOAD_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

    def __init__(self, repo: HomeAnalyticsRepository | None = None) -> None:
        self._repo = repo or HomeAnalyticsRepository()
        self._cache_enabled = isinstance(self._repo, HomeAnalyticsRepository)

    @classmethod
    def clear_payload_caches(cls) -> None:
        cls._FUNNEL_PAYLOAD_CACHE.clear()
        cls._CONFIG_PAYLOAD_CACHE.clear()
        cls._ENDPOINT_EFFICIENCY_PAYLOAD_CACHE.clear()

    @classmethod
    def _read_cached_payload(
        cls,
        cache: dict[str, tuple[float, dict[str, Any]]],
        key: str,
    ) -> dict[str, Any] | None:
        cached_entry = cache.get(key)
        if not cached_entry:
            return None
        expires_at, payload = cached_entry
        if expires_at <= time.monotonic():
            cache.pop(key, None)
            return None
        return copy.deepcopy(payload)

    @classmethod
    def _write_cached_payload(
        cls,
        cache: dict[str, tuple[float, dict[str, Any]]],
        key: str,
        payload: dict[str, Any],
    ) -> None:
        cache[key] = (
            time.monotonic() + cls._PAYLOAD_CACHE_TTL_SECONDS,
            copy.deepcopy(payload),
        )

    @staticmethod
    def _has_config_rows(rows: list[dict[str, Any]]) -> bool:
        return len(rows) > 0

    async def get_funnel_payload(
        self,
        days: int,
        buyer_id: str | None,
        limit: int,
    ) -> dict[str, Any]:
        funnel_cache_key = f"{days}:{buyer_id or '__all__'}:{limit}"
        if self._cache_enabled:
            cached = self._read_cached_payload(self._FUNNEL_PAYLOAD_CACHE, funnel_cache_key)
            if cached is not None:
                return cached

        filters = ["buyer_account_id = %s"] if buyer_id else None
        params = [buyer_id] if buyer_id else None
        seat_status, publisher_status, geo_status = await asyncio.gather(
            _get_precompute_status(
                "seat_daily",
                days,
                filters=filters,
                params=params,
            ),
            _get_precompute_status(
                "seat_publisher_daily",
                days,
                filters=filters,
                params=params,
            ),
            _get_precompute_status(
                "seat_geo_daily",
                days,
                filters=filters,
                params=params,
            ),
        )

        buyer_filter_applied = bool(buyer_id)
        buyer_filter_message = None

        if not seat_status["has_rows"]:
            if buyer_id:
                buyer_filter_applied = False
                buyer_filter_message = (
                    "No precomputed data for this seat. Run a refresh after imports."
                )
            payload = {
                "has_data": False,
                "data_state": "unavailable",
                "fallback_applied": False,
                "fallback_reason": "no_precompute_rows",
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
                "coverage": {
                    "publisher_rows_available": publisher_status.get("has_rows", False),
                    "geo_rows_available": geo_status.get("has_rows", False),
                },
            }
            if self._cache_enabled:
                self._write_cached_payload(self._FUNNEL_PAYLOAD_CACHE, funnel_cache_key, payload)
            return payload

        funnel_row, publisher_rows, geo_rows = await asyncio.gather(
            self._repo.get_funnel_row(days, buyer_id),
            self._repo.get_publisher_rows(days, buyer_id, limit),
            self._repo.get_geo_rows(days, buyer_id, limit),
        )

        total_reached = (funnel_row["total_reached"] or 0) if funnel_row else 0
        total_impressions = (funnel_row["total_impressions"] or 0) if funnel_row else 0
        total_bids = (funnel_row["total_bids"] or 0) if funnel_row else 0
        total_successful = (
            (funnel_row["total_successful_responses"] or 0) if funnel_row else 0
        )
        total_bid_requests = (funnel_row["total_bid_requests"] or 0) if funnel_row else 0

        effective_reached = total_reached
        win_rate = (total_impressions / effective_reached * 100) if effective_reached > 0 else 0
        waste_rate = 100 - win_rate

        publishers = []
        for row in publisher_rows:
            reached = row["reached"] or 0
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

        geos = []
        for row in geo_rows:
            reached = row["reached"] or 0
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

        publisher_count = int((publisher_rows[0].get("total_publishers") or 0)) if publisher_rows else 0
        country_count = int((geo_rows[0].get("total_countries") or 0)) if geo_rows else 0

        data_state = "healthy"
        fallback_reason = None
        if seat_status.get("has_rows") and (
            not publisher_status.get("has_rows") or not geo_status.get("has_rows")
        ):
            data_state = "degraded"
            fallback_reason = "missing_dimension_precompute"

        payload = {
            "has_data": effective_reached > 0,
            "data_state": data_state,
            "fallback_applied": data_state == "degraded",
            "fallback_reason": fallback_reason,
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
            "coverage": {
                "publisher_rows_available": publisher_status.get("has_rows", False),
                "geo_rows_available": geo_status.get("has_rows", False),
            },
        }
        if self._cache_enabled:
            self._write_cached_payload(self._FUNNEL_PAYLOAD_CACHE, funnel_cache_key, payload)
        return payload

    async def get_config_payload(self, days: int, buyer_id: str | None) -> dict[str, Any]:
        config_cache_key = f"{days}:{buyer_id or '__all__'}"
        if self._cache_enabled:
            cached = self._read_cached_payload(self._CONFIG_PAYLOAD_CACHE, config_cache_key)
            if cached is not None:
                return cached

        requested_days = max(days, 1)
        effective_days = requested_days
        fallback_applied = False
        fallback_reason: str | None = None

        filters = ["buyer_account_id = %s"] if buyer_id else None
        params = [buyer_id] if buyer_id else None

        config_status, rows = await asyncio.gather(
            _get_precompute_status(
                "pretarg_daily",
                requested_days,
                filters=filters,
                params=params,
            ),
            self._repo.get_config_rows(requested_days, buyer_id),
        )
        rows = rows if (config_status.get("has_rows") or self._has_config_rows(rows)) else []

        if requested_days < 30 and not self._has_config_rows(rows):
            fallback_days = 30
            fallback_status, fallback_rows = await asyncio.gather(
                _get_precompute_status(
                    "pretarg_daily",
                    fallback_days,
                    filters=filters,
                    params=params,
                ),
                self._repo.get_config_rows(fallback_days, buyer_id),
            )
            if fallback_status.get("has_rows") or self._has_config_rows(fallback_rows):
                if self._has_config_rows(fallback_rows):
                    rows = fallback_rows
                    effective_days = fallback_days
                    fallback_applied = True
                    fallback_reason = f"no_rows_{requested_days}d_used_{fallback_days}d"
                    config_status = fallback_status

        if not self._has_config_rows(rows):
            payload = {
                "period_days": requested_days,
                "requested_days": requested_days,
                "effective_days": effective_days,
                "data_source": "home_precompute",
                "data_state": "unavailable",
                "fallback_applied": fallback_applied,
                "fallback_reason": fallback_reason or "no_precompute_rows",
                "message": "No precompute available for requested date range.",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
                "precompute_status": {"home_config_daily": config_status},
            }
            if self._cache_enabled:
                self._write_cached_payload(self._CONFIG_PAYLOAD_CACHE, config_cache_key, payload)
            return payload

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

            total_reached += reached
            total_impressions += impressions

        if rows:
            total_reached = int(rows[0].get("overall_total_reached") or total_reached)
            total_impressions = int(rows[0].get("overall_total_impressions") or total_impressions)

        overall_win = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        payload = {
            "period_days": requested_days,
            "requested_days": requested_days,
            "effective_days": effective_days,
            "data_source": "home_precompute",
            "data_state": "degraded" if fallback_applied else "healthy",
            "fallback_applied": fallback_applied,
            "fallback_reason": fallback_reason,
            "configs": configs,
            "total_reached": total_reached,
            "total_impressions": total_impressions,
            "overall_win_rate_pct": round(overall_win, 1),
            "overall_waste_pct": round(100 - overall_win, 1),
            "precompute_status": {"home_config_daily": config_status},
        }
        if self._cache_enabled:
            self._write_cached_payload(self._CONFIG_PAYLOAD_CACHE, config_cache_key, payload)
        return payload

    async def get_endpoint_efficiency_payload(
        self,
        days: int,
        buyer_id: str | None,
    ) -> dict[str, Any]:
        endpoint_cache_key = f"{days}:{buyer_id or '__all__'}"
        if self._cache_enabled:
            cached = self._read_cached_payload(
                self._ENDPOINT_EFFICIENCY_PAYLOAD_CACHE,
                endpoint_cache_key,
            )
            if cached is not None:
                return cached

        bidder_task = (
            self._repo.get_bidder_id_for_buyer(buyer_id)
            if buyer_id
            else asyncio.sleep(0, result=None)
        )
        funnel_row, bidstream_summary, bidder_id, home_seat_coverage, bidstream_coverage = (
            await asyncio.gather(
                self._repo.get_funnel_row(days, buyer_id),
                self._repo.get_bidstream_summary(days, buyer_id),
                bidder_task,
                self._repo.get_home_seat_coverage(days, buyer_id),
                self._repo.get_bidstream_coverage(days, buyer_id),
            )
        )
        total_reached = int((funnel_row or {}).get("total_reached") or 0)
        total_impressions = int((funnel_row or {}).get("total_impressions") or 0)
        total_bid_requests = int((funnel_row or {}).get("total_bid_requests") or 0)

        start_date, end_date = self._repo.get_window_bounds(days)
        window_seconds = days * 24 * 3600

        funnel_proxy_qps = (total_reached / window_seconds) if window_seconds > 0 else 0.0
        delivery_win_rate_pct = (
            (total_impressions / total_reached * 100) if total_reached > 0 else 0.0
        )

        total_bids = int((bidstream_summary or {}).get("total_bids") or 0)
        total_bids_in_auction = int((bidstream_summary or {}).get("total_bids_in_auction") or 0)
        total_auctions_won = int((bidstream_summary or {}).get("total_auctions_won") or 0)
        filtered_bids = max(total_bids - total_bids_in_auction, 0)

        auction_win_rate_over_bids_pct = (
            (total_auctions_won / total_bids * 100) if total_bids > 0 else None
        )
        auction_win_rate_over_bids_in_auction_pct = (
            (total_auctions_won / total_bids_in_auction * 100)
            if total_bids_in_auction > 0
            else None
        )
        filtered_bid_rate_pct = (
            (filtered_bids / total_bids * 100) if total_bids > 0 else None
        )

        endpoints, observed_rows = await asyncio.gather(
            self._repo.get_endpoints_for_bidder(bidder_id),
            self._repo.get_observed_endpoint_rows(bidder_id),
        )
        observed_rows = [r for r in observed_rows if float(r.get("current_qps") or 0) > 0]

        # observed_query_rate_qps from actual endpoint delivery data only
        observed_qps: float | None = None
        endpoint_delivery_state = "missing"
        if observed_rows:
            observed_qps = sum(float(r.get("current_qps") or 0) for r in observed_rows)
            endpoint_delivery_state = "available"

        allocated_qps = int(sum(int(r.get("maximum_qps") or 0) for r in endpoints))
        utilization_pct = (
            (observed_qps / allocated_qps * 100)
            if observed_qps is not None and allocated_qps > 0
            else None
        )
        overshoot_x = (
            (allocated_qps / observed_qps)
            if observed_qps is not None and observed_qps > 0
            else None
        )

        endpoint_by_id = {str(r.get("endpoint_id")): r for r in endpoints}
        observed_by_id = {str(r.get("endpoint_id")): r for r in observed_rows}

        mapped = [eid for eid in endpoint_by_id.keys() if eid in observed_by_id]
        missing = [eid for eid in endpoint_by_id.keys() if eid not in observed_by_id]
        extra = [eid for eid in observed_by_id.keys() if eid not in endpoint_by_id]

        rows: list[dict[str, Any]] = []
        for eid, endpoint in endpoint_by_id.items():
            obs = observed_by_id.get(eid)
            rows.append(
                {
                    "catscan_endpoint_id": eid,
                    "catscan_url": endpoint.get("url"),
                    "catscan_location": endpoint.get("trading_location"),
                    "allocated_qps": int(endpoint.get("maximum_qps") or 0),
                    "google_location": (
                        endpoint.get("trading_location")
                        or ((obs or {}).get("trading_location"))
                    ),
                    "google_url": (obs or {}).get("url"),
                    "google_current_qps": float(obs.get("current_qps")) if obs else None,
                    "mapping_status": "mapped" if obs else "missing_in_google",
                }
            )

        for eid in extra:
            obs = observed_by_id[eid]
            rows.append(
                {
                    "catscan_endpoint_id": None,
                    "catscan_url": None,
                    "catscan_location": None,
                    "allocated_qps": None,
                    "google_location": obs.get("trading_location"),
                    "google_url": obs.get("url"),
                    "google_current_qps": float(obs.get("current_qps") or 0),
                    "mapping_status": "extra_in_google",
                }
            )

        available_impressions = total_bid_requests
        inventory_matches = total_reached
        filtered_impressions = max(available_impressions - inventory_matches, 0)
        pretargeting_loss_pct = (
            (filtered_impressions / available_impressions * 100)
            if available_impressions > 0
            else None
        )
        supply_capture_pct = (
            (inventory_matches / available_impressions * 100)
            if available_impressions > 0
            else None
        )

        alerts: list[dict[str, Any]] = []
        if missing:
            alerts.append(
                {
                    "code": "ENDPOINT_MAPPING_MISSING",
                    "severity": "high",
                    "message": (
                        f"{len(missing)} endpoint(s) configured in CatScan have no matching "
                        "observed delivery row in selected period."
                    ),
                }
            )
        if endpoint_delivery_state == "missing":
            alerts.append(
                {
                    "code": "ENDPOINT_DELIVERY_MISSING",
                    "severity": "high",
                    "message": (
                        "No endpoint delivery feed data available. "
                        "observed_query_rate_qps is unavailable until "
                        "rtb_endpoints_current is populated."
                    ),
                }
            )
        if utilization_pct is not None and allocated_qps > 0 and utilization_pct < 0.2 and total_reached > 0:
            alerts.append(
                {
                    "code": "ALLOCATED_VS_OBSERVED_GAP",
                    "severity": "medium",
                    "message": (
                        "Observed query-rate utilization is below 0.2% of allocated cap "
                        "for this period."
                    ),
                }
            )
        if pretargeting_loss_pct is not None and pretargeting_loss_pct > 70:
            alerts.append(
                {
                    "code": "PRETARGETING_LOSS_HIGH",
                    "severity": "medium",
                    "message": (
                        f"Pretargeting loss is high at {pretargeting_loss_pct:.1f}% "
                        "for selected period."
                    ),
                }
            )

        status = "healthy"
        if missing or extra:
            status = "warning"

        latest_observed_at = max(
            (r.get("observed_at") for r in observed_rows if r.get("observed_at") is not None),
            default=None,
        )

        requested_days = max(days, 1)
        home_seat_days_with_data = int(home_seat_coverage.get("days_with_data") or 0)
        bidstream_days_with_data = int(bidstream_coverage.get("days_with_data") or 0)

        payload = {
            "period_days": days,
            "window": {
                "start_date": start_date,
                "end_date": end_date,
                "seconds": window_seconds,
            },
            "data_coverage": {
                "requested_window": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "days": requested_days,
                },
                "home_seat_daily": {
                    "start_date": home_seat_coverage.get("min_date"),
                    "end_date": home_seat_coverage.get("max_date"),
                    "days_with_data": home_seat_days_with_data,
                    "row_count": int(home_seat_coverage.get("row_count") or 0),
                    "is_complete": home_seat_days_with_data >= requested_days,
                },
                "rtb_bidstream": {
                    "start_date": bidstream_coverage.get("min_date"),
                    "end_date": bidstream_coverage.get("max_date"),
                    "days_with_data": bidstream_days_with_data,
                    "row_count": int(bidstream_coverage.get("row_count") or 0),
                    "is_complete": bidstream_days_with_data >= requested_days,
                },
                "endpoint_feed": {
                    "latest_observed_at": latest_observed_at.isoformat()
                    if hasattr(latest_observed_at, "isoformat")
                    else latest_observed_at,
                    "rows_with_positive_qps": len(observed_rows),
                },
            },
            "summary": {
                "allocated_qps": allocated_qps,
                "observed_query_rate_qps": round(observed_qps, 2) if observed_qps is not None else None,
                "funnel_proxy_qps_avg": round(funnel_proxy_qps, 2),
                "endpoint_delivery_state": endpoint_delivery_state,
                "qps_utilization_pct": round(utilization_pct, 2) if utilization_pct is not None else None,
                "allocation_overshoot_x": round(overshoot_x, 2) if overshoot_x is not None else None,
                "total_reached_queries": total_reached,
                "total_impressions": total_impressions,
                # Delivery win = impressions / reached queries (legacy CatScan card).
                "delivery_win_rate_pct": round(delivery_win_rate_pct, 2),
                # Backward compatibility for older clients.
                "win_rate_pct": round(delivery_win_rate_pct, 2),
                # AB-style auction funnel parity metrics (from rtb_bidstream).
                "bids": total_bids,
                "bids_in_auction": total_bids_in_auction,
                "auctions_won": total_auctions_won,
                "filtered_bids": filtered_bids,
                "filtered_bid_rate_pct": round(filtered_bid_rate_pct, 2)
                if filtered_bid_rate_pct is not None
                else None,
                "auction_win_rate_over_bids_pct": round(auction_win_rate_over_bids_pct, 2)
                if auction_win_rate_over_bids_pct is not None
                else None,
                "auction_win_rate_over_bids_in_auction_pct": round(
                    auction_win_rate_over_bids_in_auction_pct, 2
                )
                if auction_win_rate_over_bids_in_auction_pct is not None
                else None,
            },
            "endpoint_reconciliation": {
                "status": status,
                "counts": {
                    "catscan_endpoints": len(endpoint_by_id),
                    "google_delivery_rows": len(observed_by_id),
                    "mapped": len(mapped),
                    "missing_in_google": len(missing),
                    "extra_in_google": len(extra),
                },
                "rows": rows,
            },
            "funnel_breakout": {
                "available_impressions": available_impressions,
                "inventory_matches": inventory_matches,
                "filtered_impressions": filtered_impressions,
                "pretargeting_loss_pct": round(pretargeting_loss_pct, 2)
                if pretargeting_loss_pct is not None
                else None,
                "supply_capture_pct": round(supply_capture_pct, 2)
                if supply_capture_pct is not None
                else None,
                "available_impressions_proxy_source": "home_seat_daily.bid_requests",
            },
            "alerts": alerts,
        }
        if self._cache_enabled:
            self._write_cached_payload(
                self._ENDPOINT_EFFICIENCY_PAYLOAD_CACHE,
                endpoint_cache_key,
                payload,
            )
        return payload
