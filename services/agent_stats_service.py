"""Precomputed stats payloads for outside reporting agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException

from storage.postgres_database import pg_query_one, pg_query_with_timeout


def _int(value: object) -> int:
    if value is None:
        return 0
    return int(value)


def _date_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _money_from_micros(micros: int) -> float:
    return round(micros / 1_000_000, 2)


def _cpm(spend_micros: int, impressions: int) -> float:
    if impressions <= 0:
        return 0.0
    return round((spend_micros / 1_000_000) / impressions * 1000, 4)


@dataclass
class AgentStatsRepository:
    """SQL access for precomputed agent stats."""

    statement_timeout_ms: int = 5000

    async def get_buyer(self, buyer_id: str) -> dict[str, Any] | None:
        return await pg_query_one(
            """
            SELECT buyer_id, bidder_id, display_name, active, last_synced
            FROM buyer_seats
            WHERE buyer_id = %s
            """,
            (buyer_id,),
        )

    async def get_funnel_totals(self, buyer_id: str, days: int) -> dict[str, Any] | None:
        return await pg_query_one(
            """
            SELECT
                MIN(metric_date) AS start_date,
                MAX(metric_date) AS end_date,
                COALESCE(SUM(reached_queries), 0) AS reached_queries,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(bids), 0) AS bids,
                COALESCE(SUM(successful_responses), 0) AS successful_responses,
                COALESCE(SUM(bid_requests), 0) AS bid_requests,
                COALESCE(SUM(auctions_won), 0) AS auctions_won
            FROM home_seat_daily
            WHERE buyer_account_id = %s
              AND metric_date >= CURRENT_DATE - (%s::int - 1)
            """,
            (buyer_id, days),
        )

    async def get_auction_totals(self, buyer_id: str, days: int) -> dict[str, Any] | None:
        # home_seat_daily has no bids_in_auction column; the config-level
        # precompute is the only home_* table that carries it.
        return await pg_query_one(
            """
            SELECT
                COALESCE(SUM(bids_in_auction), 0) AS bids_in_auction,
                COALESCE(SUM(auctions_won), 0) AS auctions_won
            FROM home_config_daily
            WHERE buyer_account_id = %s
              AND metric_date >= CURRENT_DATE - (%s::int - 1)
            """,
            (buyer_id, days),
        )

    async def get_spend_totals(self, buyer_id: str, days: int) -> dict[str, Any] | None:
        # Spend/impressions/clicks come from the buyer-level rtb_buyer_spend_daily
        # (sourced from rtb_daily). app_count/billing_count stay sourced from
        # rtb_app_daily and remain 0 until the upstream app-name ETL gap is fixed.
        return await pg_query_one(
            """
            SELECT
                s.start_date,
                s.end_date,
                s.impressions,
                s.clicks,
                s.spend_micros,
                COALESCE(a.app_count, 0) AS app_count,
                COALESCE(a.billing_count, 0) AS billing_count
            FROM (
                SELECT
                    MIN(metric_date) AS start_date,
                    MAX(metric_date) AS end_date,
                    COALESCE(SUM(impressions), 0) AS impressions,
                    COALESCE(SUM(clicks), 0) AS clicks,
                    COALESCE(SUM(spend_micros), 0) AS spend_micros
                FROM rtb_buyer_spend_daily
                WHERE buyer_account_id = %s
                  AND metric_date >= CURRENT_DATE - (%s::int - 1)
            ) s
            CROSS JOIN (
                SELECT
                    COUNT(DISTINCT app_name) AS app_count,
                    COUNT(DISTINCT billing_id) AS billing_count
                FROM rtb_app_daily
                WHERE buyer_account_id = %s
                  AND metric_date >= CURRENT_DATE - (%s::int - 1)
            ) a
            """,
            (buyer_id, days, buyer_id, days),
        )

    async def get_top_publishers(self, buyer_id: str, days: int, limit: int) -> list[dict[str, Any]]:
        return await pg_query_with_timeout(
            """
            SELECT
                publisher_id,
                COALESCE(MAX(publisher_name), publisher_id) AS publisher_name,
                COALESCE(SUM(reached_queries), 0) AS reached_queries,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(bids), 0) AS bids,
                COALESCE(SUM(auctions_won), 0) AS auctions_won
            FROM home_publisher_daily
            WHERE buyer_account_id = %s
              AND metric_date >= CURRENT_DATE - (%s::int - 1)
            GROUP BY publisher_id
            ORDER BY impressions DESC, reached_queries DESC, publisher_id
            LIMIT %s
            """,
            (buyer_id, days, limit),
            statement_timeout_ms=self.statement_timeout_ms,
        )

    async def get_top_geos(self, buyer_id: str, days: int, limit: int) -> list[dict[str, Any]]:
        return await pg_query_with_timeout(
            """
            SELECT
                country,
                COALESCE(SUM(reached_queries), 0) AS reached_queries,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(bids), 0) AS bids,
                COALESCE(SUM(auctions_won), 0) AS auctions_won
            FROM home_geo_daily
            WHERE buyer_account_id = %s
              AND metric_date >= CURRENT_DATE - (%s::int - 1)
            GROUP BY country
            ORDER BY impressions DESC, reached_queries DESC, country
            LIMIT %s
            """,
            (buyer_id, days, limit),
            statement_timeout_ms=self.statement_timeout_ms,
        )

    async def get_top_configs(self, buyer_id: str, days: int, limit: int) -> list[dict[str, Any]]:
        return await pg_query_with_timeout(
            """
            SELECT
                h.billing_id,
                COALESCE(MAX(pc.display_name), h.billing_id) AS display_name,
                COALESCE(SUM(h.reached_queries), 0) AS reached_queries,
                COALESCE(SUM(h.impressions), 0) AS impressions,
                COALESCE(SUM(h.bids_in_auction), 0) AS bids_in_auction,
                COALESCE(SUM(h.auctions_won), 0) AS auctions_won
            FROM home_config_daily h
            LEFT JOIN pretargeting_configs pc
              ON pc.billing_id = h.billing_id
             AND pc.bidder_id = h.buyer_account_id
            WHERE h.buyer_account_id = %s
              AND h.metric_date >= CURRENT_DATE - (%s::int - 1)
            GROUP BY h.billing_id
            ORDER BY impressions DESC, reached_queries DESC, h.billing_id
            LIMIT %s
            """,
            (buyer_id, days, limit),
            statement_timeout_ms=self.statement_timeout_ms,
        )

    async def get_daily_spend_rows(
        self, buyer_id: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        # One row per requested date via generate_series so callers can tell
        # "no source rows" apart from a true zero-spend day with source rows.
        #
        # Spend/impressions/clicks come from rtb_buyer_spend_daily (buyer-level,
        # sourced from rtb_daily). The app-dimension columns app_count/billing_count
        # come from rtb_app_daily, which is currently empty because the upstream ETL
        # does not populate app_name/app_id on rtb_daily; they light up automatically
        # once that gap is fixed, without any further code change here.
        return await pg_query_with_timeout(
            """
            WITH requested_dates AS (
                SELECT generate_series(%s::date, %s::date, interval '1 day')::date AS metric_date
            ),
            app_dims AS (
                SELECT
                    metric_date,
                    COUNT(DISTINCT NULLIF(app_name, ''))::int AS app_count,
                    COUNT(DISTINCT NULLIF(billing_id, ''))::int AS billing_count
                FROM rtb_app_daily
                WHERE buyer_account_id = %s
                GROUP BY metric_date
            )
            SELECT
                requested_dates.metric_date,
                COALESCE(s.impressions, 0)::bigint AS impressions,
                COALESCE(s.clicks, 0)::bigint AS clicks,
                COALESCE(s.spend_micros, 0)::bigint AS spend_micros,
                (s.metric_date IS NOT NULL)::int AS source_row_count,
                COALESCE(app_dims.app_count, 0)::int AS app_count,
                COALESCE(app_dims.billing_count, 0)::int AS billing_count
            FROM requested_dates
            LEFT JOIN rtb_buyer_spend_daily s
              ON s.metric_date = requested_dates.metric_date
             AND s.buyer_account_id = %s
            LEFT JOIN app_dims
              ON app_dims.metric_date = requested_dates.metric_date
            ORDER BY requested_dates.metric_date
            """,
            (start_date, end_date, buyer_id, buyer_id),
            statement_timeout_ms=self.statement_timeout_ms,
        )

    async def get_top_apps(self, buyer_id: str, days: int, limit: int) -> list[dict[str, Any]]:
        return await pg_query_with_timeout(
            """
            SELECT
                app_name,
                MAX(app_id) AS app_id,
                COALESCE(SUM(reached_queries), 0) AS reached_queries,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(spend_micros), 0) AS spend_micros
            FROM rtb_app_daily
            WHERE buyer_account_id = %s
              AND metric_date >= CURRENT_DATE - (%s::int - 1)
            GROUP BY app_name
            ORDER BY spend_micros DESC, impressions DESC, app_name
            LIMIT %s
            """,
            (buyer_id, days, limit),
            statement_timeout_ms=self.statement_timeout_ms,
        )


class AgentStatsService:
    """Build stable, buyer-scoped JSON for email-summary agents."""

    def __init__(self, repo: AgentStatsRepository | None = None) -> None:
        self._repo = repo or AgentStatsRepository()

    async def get_stats_summary(
        self,
        *,
        buyer_id: str,
        days: int,
        top_limit: int,
    ) -> dict[str, Any]:
        safe_days = max(1, min(days, 30))
        safe_limit = max(1, min(top_limit, 25))

        buyer = await self._repo.get_buyer(buyer_id)
        if not buyer:
            raise HTTPException(status_code=404, detail="Buyer seat not found.")

        funnel_row = await self._repo.get_funnel_totals(buyer_id, safe_days) or {}
        auction_row = await self._repo.get_auction_totals(buyer_id, safe_days) or {}
        spend_row = await self._repo.get_spend_totals(buyer_id, safe_days) or {}
        top_publishers = await self._repo.get_top_publishers(buyer_id, safe_days, safe_limit)
        top_geos = await self._repo.get_top_geos(buyer_id, safe_days, safe_limit)
        top_configs = await self._repo.get_top_configs(buyer_id, safe_days, safe_limit)
        top_apps = await self._repo.get_top_apps(buyer_id, safe_days, safe_limit)

        totals = self._build_totals(funnel_row, spend_row, auction_row)
        freshness = self._build_freshness(funnel_row, spend_row)
        has_data = bool(totals["reached_queries"] or totals["impressions"] or totals["spend_micros"])
        warnings = self._build_warnings(
            has_data=has_data, freshness=freshness, totals=totals
        )

        sections = {
            "top_publishers": [self._publisher_payload(row) for row in top_publishers],
            "top_geos": [self._geo_payload(row) for row in top_geos],
            "top_configs": [self._config_payload(row) for row in top_configs],
            "top_apps": [self._app_payload(row) for row in top_apps],
        }

        email_summary = self._build_email_summary(
            buyer_name=str(buyer.get("display_name") or buyer_id),
            days=safe_days,
            totals=totals,
            sections=sections,
            warnings=warnings,
        )

        return {
            "api_version": "agent.v1",
            "buyer": {
                "buyer_id": str(buyer["buyer_id"]),
                "bidder_id": buyer.get("bidder_id"),
                "display_name": buyer.get("display_name"),
                "active": bool(buyer.get("active", True)),
                "last_synced": str(buyer.get("last_synced")) if buyer.get("last_synced") else None,
            },
            "period": {
                "days": safe_days,
                "start_date": freshness["start_date"],
                "end_date": freshness["end_date"],
            },
            "data_state": "healthy" if has_data and not warnings else "warning" if has_data else "empty",
            "warnings": warnings,
            "totals": totals,
            **sections,
            "email_summary": email_summary,
            "data_sources": {
                "tables": [
                    "home_seat_daily",
                    "home_publisher_daily",
                    "home_geo_daily",
                    "home_config_daily",
                    "rtb_app_daily",
                ],
                "precomputed_only": True,
            },
        }

    async def get_daily_spend(
        self,
        *,
        buyer_id: str,
        start_date: date,
        end_date: date,
        include_empty: bool = True,
    ) -> dict[str, Any]:
        if end_date < start_date:
            raise HTTPException(
                status_code=400, detail="end_date must be on or after start_date."
            )
        requested_days = (end_date - start_date).days + 1
        if requested_days > 90:
            raise HTTPException(
                status_code=400,
                detail="Date range is limited to 90 days per request. Backfills can call in chunks.",
            )

        buyer = await self._repo.get_buyer(buyer_id)
        if not buyer:
            raise HTTPException(status_code=404, detail="Buyer seat not found.")

        raw_rows = await self._repo.get_daily_spend_rows(buyer_id, start_date, end_date)
        rows = [self._daily_spend_payload(row, buyer_id) for row in raw_rows]

        missing_dates = [row["metric_date"] for row in rows if row["source_status"] == "missing"]
        if not include_empty:
            rows = [row for row in rows if row["source_status"] == "present"]

        return {
            "api_version": "agent.v1",
            "buyer": {
                "buyer_id": str(buyer["buyer_id"]),
                "bidder_id": buyer.get("bidder_id"),
                "display_name": buyer.get("display_name"),
                "active": bool(buyer.get("active", True)),
                "last_synced": str(buyer.get("last_synced")) if buyer.get("last_synced") else None,
            },
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": requested_days,
            },
            "data_source": {
                "table": "rtb_buyer_spend_daily",
                "precomputed_only": True,
                "source_metric": "Spend (buyer currency)",
                # RTBcat does not store report currency; consumers map it externally.
                "currency": None,
            },
            "rows": rows,
            "summary": {
                "requested_days": requested_days,
                "days_with_source_rows": requested_days - len(missing_dates),
                "total_impressions": sum(_int(row.get("impressions")) for row in raw_rows),
                "total_clicks": sum(_int(row.get("clicks")) for row in raw_rows),
                "total_spend_micros": sum(_int(row.get("spend_micros")) for row in raw_rows),
            },
            "warnings": [
                f"No RTBcat spend source rows found for {missing_date}."
                for missing_date in missing_dates
            ],
        }

    def _daily_spend_payload(self, row: dict[str, Any], buyer_id: str) -> dict[str, Any]:
        source_row_count = _int(row.get("source_row_count"))
        return {
            "metric_date": _date_str(row.get("metric_date")),
            "buyer_account_id": buyer_id,
            "impressions": _int(row.get("impressions")),
            "clicks": _int(row.get("clicks")),
            "spend_micros": _int(row.get("spend_micros")),
            "source_row_count": source_row_count,
            "app_count": _int(row.get("app_count")),
            "billing_count": _int(row.get("billing_count")),
            "source_status": "present" if source_row_count > 0 else "missing",
        }

    def _build_totals(
        self,
        funnel_row: dict[str, Any],
        spend_row: dict[str, Any],
        auction_row: dict[str, Any],
    ) -> dict[str, Any]:
        reached_queries = _int(funnel_row.get("reached_queries"))
        impressions = _int(funnel_row.get("impressions"))
        bids = _int(funnel_row.get("bids"))
        successful_responses = _int(funnel_row.get("successful_responses"))
        bid_requests = _int(funnel_row.get("bid_requests"))
        auctions_won = _int(funnel_row.get("auctions_won"))
        bids_in_auction = _int(auction_row.get("bids_in_auction"))
        auction_wins = _int(auction_row.get("auctions_won"))
        spend_micros = _int(spend_row.get("spend_micros"))
        clicks = _int(spend_row.get("clicks"))
        spend_impressions = _int(spend_row.get("impressions"))

        return {
            "reached_queries": reached_queries,
            "bid_requests": bid_requests,
            "bids": bids,
            "successful_responses": successful_responses,
            "auctions_won": auctions_won,
            "bids_in_auction": bids_in_auction,
            "impressions": impressions,
            "clicks": clicks,
            "spend_micros": spend_micros,
            "spend_usd": _money_from_micros(spend_micros),
            # Win rate per METRICS_GUIDE.md: Auctions Won / Bids in Auction.
            # Both terms come from home_config_daily so the ratio is consistent.
            "win_rate_pct": _rate(auction_wins, bids_in_auction),
            "efficiency_rate_pct": _rate(impressions, reached_queries),
            "bid_rate_pct": _rate(bids, reached_queries),
            "response_rate_pct": _rate(successful_responses, bid_requests),
            "ctr_pct": _rate(clicks, spend_impressions or impressions),
            "avg_cpm_usd": _cpm(spend_micros, spend_impressions or impressions),
            "app_count": _int(spend_row.get("app_count")),
            "billing_count": _int(spend_row.get("billing_count")),
        }

    def _build_freshness(self, funnel_row: dict[str, Any], spend_row: dict[str, Any]) -> dict[str, Any]:
        start_candidates = [
            _date_str(funnel_row.get("start_date")),
            _date_str(spend_row.get("start_date")),
        ]
        end_candidates = [
            _date_str(funnel_row.get("end_date")),
            _date_str(spend_row.get("end_date")),
        ]
        starts = [value for value in start_candidates if value]
        ends = [value for value in end_candidates if value]
        return {
            "start_date": min(starts) if starts else None,
            "end_date": max(ends) if ends else None,
        }

    def _build_warnings(
        self,
        *,
        has_data: bool,
        freshness: dict[str, Any],
        totals: dict[str, Any],
    ) -> list[str]:
        warnings: list[str] = []
        if not has_data:
            warnings.append("No precomputed rows were available for this buyer and period.")
        if not freshness.get("end_date"):
            warnings.append("Latest metric date is unavailable.")
        if totals.get("impressions") and not totals.get("bids_in_auction"):
            warnings.append(
                "Bids-in-auction data is unavailable for this period, so win_rate_pct "
                "reads 0. Check that the bidsinauction report includes the 'Bids in "
                "auction' and 'Auctions won' columns."
            )
        return warnings

    def _publisher_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        reached = _int(row.get("reached_queries"))
        impressions = _int(row.get("impressions"))
        bids = _int(row.get("bids"))
        auctions_won = _int(row.get("auctions_won"))
        return {
            "publisher_id": row.get("publisher_id"),
            "publisher_name": row.get("publisher_name"),
            "reached_queries": reached,
            "impressions": impressions,
            "bids": bids,
            "auctions_won": auctions_won,
            # home_publisher_daily has no bids_in_auction; auctions_won/bids is
            # the nearest computable win rate at this grain.
            "win_rate_pct": _rate(auctions_won, bids),
        }

    def _geo_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        reached = _int(row.get("reached_queries"))
        impressions = _int(row.get("impressions"))
        bids = _int(row.get("bids"))
        auctions_won = _int(row.get("auctions_won"))
        return {
            "country": row.get("country"),
            "reached_queries": reached,
            "impressions": impressions,
            "bids": bids,
            "auctions_won": auctions_won,
            "win_rate_pct": _rate(auctions_won, bids),
        }

    def _config_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        reached = _int(row.get("reached_queries"))
        impressions = _int(row.get("impressions"))
        bids_in_auction = _int(row.get("bids_in_auction"))
        auctions_won = _int(row.get("auctions_won"))
        return {
            "billing_id": row.get("billing_id"),
            "display_name": row.get("display_name"),
            "reached_queries": reached,
            "impressions": impressions,
            "bids_in_auction": bids_in_auction,
            "auctions_won": auctions_won,
            "win_rate_pct": _rate(auctions_won, bids_in_auction),
        }

    def _app_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        impressions = _int(row.get("impressions"))
        clicks = _int(row.get("clicks"))
        spend_micros = _int(row.get("spend_micros"))
        return {
            "app_name": row.get("app_name"),
            "app_id": row.get("app_id"),
            "reached_queries": _int(row.get("reached_queries")),
            "impressions": impressions,
            "clicks": clicks,
            "spend_micros": spend_micros,
            "spend_usd": _money_from_micros(spend_micros),
            "ctr_pct": _rate(clicks, impressions),
            "avg_cpm_usd": _cpm(spend_micros, impressions),
        }

    def _build_email_summary(
        self,
        *,
        buyer_name: str,
        days: int,
        totals: dict[str, Any],
        sections: dict[str, list[dict[str, Any]]],
        warnings: list[str],
    ) -> dict[str, Any]:
        subject = f"{buyer_name} {days}-day Cat-Scan performance summary"
        bullets = [
            (
                f"Reached {totals['reached_queries']:,} queries and served "
                f"{totals['impressions']:,} impressions."
            ),
            (
                f"Spend was ${totals['spend_usd']:,.2f} with "
                f"{totals['clicks']:,} clicks and {totals['ctr_pct']:.2f}% CTR."
            ),
            (
                f"Win rate was {totals['win_rate_pct']:.2f}% and bid rate was "
                f"{totals['bid_rate_pct']:.2f}%."
            ),
        ]
        top_app = sections["top_apps"][0] if sections["top_apps"] else None
        if top_app:
            bullets.append(
                f"Top app by spend was {top_app['app_name']} at ${top_app['spend_usd']:,.2f}."
            )
        top_geo = sections["top_geos"][0] if sections["top_geos"] else None
        if top_geo:
            bullets.append(
                f"Top country by impressions was {top_geo['country']} with {top_geo['impressions']:,} impressions."
            )
        bullets.extend(warnings)
        markdown = "\n".join(f"- {bullet}" for bullet in bullets)
        return {
            "subject": subject,
            "bullets": bullets,
            "markdown": markdown,
        }
