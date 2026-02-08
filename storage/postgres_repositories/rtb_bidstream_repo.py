"""Postgres repository for RTB bidstream analytics (SQL only).

Handles all SQL queries for:
- RTB funnel summary
- Publisher breakdown
- Geo breakdown
- Config performance
- Config breakdown (size/geo/publisher/creative)
- App drilldown
"""

from __future__ import annotations

from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


class RtbBidstreamRepository:
    """SQL-only repository for RTB bidstream analytics tables."""

    # =========================================================================
    # Precompute Status
    # =========================================================================

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        row = await pg_query_one(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = %s
            ) as exists
            """,
            (table_name,),
        )
        return row["exists"] if row else False

    async def get_precompute_row_count(
        self,
        table_name: str,
        days: int,
        filters: Optional[list[str]] = None,
        params: Optional[list] = None,
    ) -> int:
        """Get row count for a precompute table within date range."""
        where_clauses = ["metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')"]
        query_params: list = [days]

        if filters:
            where_clauses.extend(filters)
            if params:
                query_params.extend(params)

        row = await pg_query_one(
            f"""
            SELECT COUNT(*) as cnt
            FROM {table_name}
            WHERE {" AND ".join(where_clauses)}
            """,
            tuple(query_params),
        )
        return row["cnt"] or 0 if row else 0

    # =========================================================================
    # RTB Funnel Summary
    # =========================================================================

    async def get_funnel_summary(
        self,
        days: int,
        buyer_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get aggregated funnel metrics from rtb_funnel_daily."""
        where = ["metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')"]
        params: list = [days]

        if buyer_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_id)

        return await pg_query_one(
            f"""
            SELECT
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids,
                SUM(successful_responses) as total_successful_responses,
                SUM(bid_requests) as total_bid_requests
            FROM rtb_funnel_daily
            WHERE {" AND ".join(where)}
            """,
            tuple(params),
        )

    # =========================================================================
    # Publisher Breakdown
    # =========================================================================

    async def get_publisher_breakdown(
        self,
        days: int,
        buyer_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get publisher breakdown from rtb_publisher_daily."""
        where = [
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
            "publisher_id != ''",
        ]
        params: list = [days]

        if buyer_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_id)

        params.append(limit)

        return await pg_query(
            f"""
            SELECT
                publisher_id,
                publisher_name,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(bids) as total_bids,
                SUM(auctions_won) as auctions_won,
                SUM(successful_responses) as successful_responses,
                SUM(bid_requests) as bid_requests
            FROM rtb_publisher_daily
            WHERE {" AND ".join(where)}
            GROUP BY publisher_id, publisher_name
            ORDER BY SUM(reached_queries) DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_publisher_count(
        self,
        days: int,
        buyer_id: Optional[str] = None,
    ) -> int:
        """Get distinct publisher count."""
        where = [
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
            "publisher_id != ''",
        ]
        params: list = [days]

        if buyer_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_id)

        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT publisher_id) as cnt
            FROM rtb_publisher_daily
            WHERE {" AND ".join(where)}
            """,
            tuple(params),
        )
        return row["cnt"] or 0 if row else 0

    # =========================================================================
    # Geo Breakdown
    # =========================================================================

    async def get_geo_breakdown(
        self,
        days: int,
        buyer_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get geo breakdown from rtb_geo_daily."""
        where = [
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
            "country != ''",
        ]
        params: list = [days]

        if buyer_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_id)

        params.append(limit)

        return await pg_query(
            f"""
            SELECT
                country,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(bids) as total_bids,
                SUM(auctions_won) as auctions_won,
                SUM(successful_responses) as successful_responses,
                SUM(bid_requests) as bid_requests
            FROM rtb_geo_daily
            WHERE {" AND ".join(where)}
            GROUP BY country
            ORDER BY SUM(reached_queries) DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_country_count(
        self,
        days: int,
        buyer_id: Optional[str] = None,
    ) -> int:
        """Get distinct country count."""
        where = [
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
            "country != ''",
        ]
        params: list = [days]

        if buyer_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_id)

        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT country) as cnt
            FROM rtb_geo_daily
            WHERE {" AND ".join(where)}
            """,
            tuple(params),
        )
        return row["cnt"] or 0 if row else 0

    # =========================================================================
    # Config Performance (by billing_id)
    # =========================================================================

    async def get_config_size_data(
        self,
        days: int,
        buyer_id: Optional[str] = None,
        valid_billing_ids: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get config performance by billing_id and size from config_size_daily."""
        where = ["metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')"]
        params: list = [days]

        if buyer_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_id)

        if valid_billing_ids:
            where.append("billing_id = ANY(%s)")
            params.append(valid_billing_ids)

        return await pg_query(
            f"""
            SELECT
                billing_id,
                creative_size,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions
            FROM config_size_daily
            WHERE {" AND ".join(where)}
            GROUP BY billing_id, creative_size
            ORDER BY SUM(reached_queries) DESC
            """,
            tuple(params),
        )

    async def get_config_geo_data(
        self,
        days: int,
        buyer_id: Optional[str] = None,
        valid_billing_ids: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get config geo data for country lists from canonical facts."""
        if not await self.table_exists("fact_delivery_daily"):
            return []

        where = ["metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')"]
        params: list = [days]

        if buyer_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_id)

        if valid_billing_ids:
            where.append("billing_id = ANY(%s)")
            params.append(valid_billing_ids)
        where.append("country != ''")
        where.append("data_scope = 'billing'")

        return await pg_query(
            f"""
            SELECT billing_id, country
            FROM fact_delivery_daily
            WHERE {" AND ".join(where)}
            """,
            tuple(params),
        )

    # =========================================================================
    # Config Breakdown (by type: size/geo/publisher/creative)
    # =========================================================================

    async def get_config_breakdown_geo(
        self,
        billing_id: str,
        days: int,
        buyer_account_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get geo breakdown for a config with canonical fallback."""
        if not await self.table_exists("fact_delivery_daily"):
            return []

        primary_where = [
            "billing_id = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
            "country != ''",
            "data_scope = 'billing'",
        ]
        primary_params: list = [billing_id, days]
        if buyer_account_id:
            primary_where.append("buyer_account_id = %s")
            primary_params.append(buyer_account_id)
        primary_params.append(limit)

        rows = await pg_query(
            f"""
            SELECT
                country as name,
                COALESCE(SUM(reached_queries), 0) as total_reached,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros,
                'billing' as data_scope,
                source_used as data_source
            FROM fact_delivery_daily
            WHERE {" AND ".join(primary_where)}
            GROUP BY country, source_used
            ORDER BY SUM(reached_queries) DESC
            LIMIT %s
            """,
            tuple(primary_params),
        )
        if rows or not buyer_account_id:
            return rows

        # Buyer-scope fallback when billing-scoped geo dimensions are unavailable.
        return await pg_query(
            """
            SELECT
                country as name,
                COALESCE(SUM(reached_queries), 0) as total_reached,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros,
                'buyer_fallback' as data_scope,
                source_used as data_source
            FROM fact_delivery_daily
            WHERE buyer_account_id = %s
              AND metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')
              AND data_scope = 'buyer_fallback'
              AND billing_id = ''
              AND country != ''
            GROUP BY country, source_used
            ORDER BY SUM(reached_queries) DESC
            LIMIT %s
            """,
            (buyer_account_id, days, limit),
        )

    async def get_config_breakdown_publisher(
        self,
        billing_id: str,
        days: int,
        buyer_account_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get publisher breakdown for a config with canonical fallback."""
        if not await self.table_exists("fact_delivery_daily"):
            return []

        primary_where = [
            "billing_id = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
            "publisher_id != ''",
            "data_scope = 'billing'",
        ]
        primary_params: list = [billing_id, days]
        if buyer_account_id:
            primary_where.append("buyer_account_id = %s")
            primary_params.append(buyer_account_id)
        primary_params.append(limit)

        rows = await pg_query(
            f"""
            SELECT
                COALESCE(NULLIF(publisher_name, ''), publisher_id) as name,
                COALESCE(SUM(reached_queries), 0) as total_reached,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros,
                'billing' as data_scope,
                source_used as data_source
            FROM fact_delivery_daily
            WHERE {" AND ".join(primary_where)}
            GROUP BY COALESCE(NULLIF(publisher_name, ''), publisher_id), source_used
            ORDER BY SUM(reached_queries) DESC
            LIMIT %s
            """,
            tuple(primary_params),
        )
        if rows or not buyer_account_id:
            return rows

        return await pg_query(
            """
            SELECT
                COALESCE(NULLIF(publisher_name, ''), publisher_id) as name,
                COALESCE(SUM(reached_queries), 0) as total_reached,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros,
                'buyer_fallback' as data_scope,
                source_used as data_source
            FROM fact_delivery_daily
            WHERE buyer_account_id = %s
              AND metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')
              AND data_scope = 'buyer_fallback'
              AND billing_id = ''
              AND publisher_id != ''
            GROUP BY COALESCE(NULLIF(publisher_name, ''), publisher_id), source_used
            ORDER BY SUM(reached_queries) DESC
            LIMIT %s
            """,
            (buyer_account_id, days, limit),
        )

    async def get_config_breakdown_creative(
        self,
        billing_id: str,
        days: int,
        buyer_account_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get creative breakdown for a specific config with language info."""
        where = [
            "d.billing_id = %s",
            "d.metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
        ]
        params: list = [billing_id, days]

        if buyer_account_id:
            where.append("d.buyer_account_id = %s")
            params.append(buyer_account_id)

        params.append(limit)

        return await pg_query(
            f"""
            SELECT
                d.creative_id as name,
                COALESCE(SUM(d.reached_queries), 0) as total_reached,
                COALESCE(SUM(d.impressions), 0) as total_impressions,
                COALESCE(SUM(d.spend_micros), 0) as total_spend_micros,
                MAX(c.detected_language) as detected_language,
                MAX(c.detected_language_code) as detected_language_code
            FROM config_creative_daily d
            LEFT JOIN creatives c ON c.id = d.creative_id
            WHERE {" AND ".join(where)}
            GROUP BY d.creative_id
            ORDER BY SUM(d.reached_queries) DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_config_breakdown_size(
        self,
        billing_id: str,
        days: int,
        buyer_account_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get size breakdown for a specific config."""
        where = [
            "billing_id = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
        ]
        params: list = [billing_id, days]

        if buyer_account_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_account_id)

        params.append(limit)

        return await pg_query(
            f"""
            SELECT
                creative_size as name,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros
            FROM config_size_daily
            WHERE {" AND ".join(where)}
            GROUP BY creative_size
            ORDER BY SUM(reached_queries) DESC
            LIMIT %s
            """,
            tuple(params),
        )

    # =========================================================================
    # Config Creatives
    # =========================================================================

    async def get_config_creative_ids(
        self,
        billing_id: str,
        days: int,
        buyer_account_id: Optional[str] = None,
        size: Optional[str] = None,
        limit: int = 200,
    ) -> list[str]:
        """Get distinct creative IDs for a config."""
        where = [
            "billing_id = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
            "creative_id IS NOT NULL",
            "creative_id != ''",
        ]
        params: list = [billing_id, days]

        if size:
            where.append("creative_size = %s")
            params.append(size)

        if buyer_account_id:
            where.append("buyer_account_id = %s")
            params.append(buyer_account_id)

        params.append(limit)

        rows = await pg_query(
            f"""
            SELECT DISTINCT creative_id
            FROM config_creative_daily
            WHERE {" AND ".join(where)}
            LIMIT %s
            """,
            tuple(params),
        )
        return [row["creative_id"] for row in rows if row["creative_id"]]

    async def get_creatives_by_ids(
        self,
        creative_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Get creative details by IDs."""
        if not creative_ids:
            return []

        return await pg_query(
            """
            SELECT id, name, format, width, height
            FROM creatives
            WHERE id = ANY(%s)
            """,
            (creative_ids,),
        )

    # =========================================================================
    # Pretargeting Config Lookup
    # =========================================================================

    async def get_pretargeting_config_geos(
        self,
        billing_id: str,
    ) -> Optional[str]:
        """Get included_geos JSON for a pretargeting config."""
        row = await pg_query_one(
            """
            SELECT included_geos
            FROM pretargeting_configs
            WHERE billing_id = %s
            LIMIT 1
            """,
            (billing_id,),
        )
        return row["included_geos"] if row and "included_geos" in row else None

    async def get_country_codes_for_geo_ids(
        self,
        geo_ids: list[str],
    ) -> list[str]:
        """Get country codes for Google geo IDs."""
        if not geo_ids:
            return []

        rows = await pg_query(
            """
            SELECT google_geo_id, country_code
            FROM geographies
            WHERE google_geo_id = ANY(%s)
            """,
            (geo_ids,),
        )
        return sorted({row["country_code"] for row in rows if row.get("country_code")})

    # =========================================================================
    # Billing ID Lookup
    # =========================================================================

    async def get_current_bidder_id(self) -> Optional[str]:
        """Get the most recently synced bidder_id."""
        row = await pg_query_one(
            """
            SELECT bidder_id FROM pretargeting_configs
            WHERE bidder_id IS NOT NULL
            ORDER BY synced_at DESC
            LIMIT 1
            """
        )
        return row["bidder_id"] if row else None

    async def get_billing_ids_for_bidder(
        self,
        bidder_id: Optional[str] = None,
    ) -> list[str]:
        """Get billing IDs for a bidder (or all if not specified)."""
        if bidder_id:
            rows = await pg_query(
                """
                SELECT DISTINCT TRIM(billing_id) as billing_id
                FROM pretargeting_configs
                WHERE billing_id IS NOT NULL AND bidder_id = %s
                """,
                (bidder_id,),
            )
        else:
            rows = await pg_query(
                """
                SELECT DISTINCT TRIM(billing_id) as billing_id
                FROM pretargeting_configs
                WHERE billing_id IS NOT NULL
                """
            )
        return [row["billing_id"] for row in rows]

    async def get_bidder_id_for_buyer(
        self,
        buyer_id: str,
    ) -> Optional[str]:
        """Get bidder_id for a buyer seat."""
        row = await pg_query_one(
            """
            SELECT bidder_id FROM buyer_seats WHERE buyer_id = %s
            """,
            (buyer_id,),
        )
        return row["bidder_id"] if row and row["bidder_id"] else None

    # =========================================================================
    # App Drilldown
    # =========================================================================

    async def get_app_summary(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get app summary from rtb_app_daily."""
        where = [
            "app_name = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
        ]
        params: list = [app_name, days]

        if billing_id:
            where.append("billing_id = %s")
            params.append(billing_id)

        return await pg_query_one(
            f"""
            SELECT
                app_name,
                MAX(app_id) as app_id,
                COUNT(DISTINCT metric_date) as days_with_data,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                SUM(spend_micros) as total_spend_micros
            FROM rtb_app_daily
            WHERE {" AND ".join(where)}
            GROUP BY app_name
            """,
            tuple(params),
        )

    async def get_app_creative_count(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str] = None,
    ) -> int:
        """Get distinct creative count for an app."""
        where = [
            "app_name = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
        ]
        params: list = [app_name, days]

        if billing_id:
            where.append("billing_id = %s")
            params.append(billing_id)

        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT creative_id) as creative_count
            FROM rtb_app_creative_daily
            WHERE {" AND ".join(where)}
            """,
            tuple(params),
        )
        return row["creative_count"] if row else 0

    async def get_app_country_count(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str] = None,
    ) -> int:
        """Get distinct country count for an app."""
        where = [
            "app_name = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
        ]
        params: list = [app_name, days]

        if billing_id:
            where.append("billing_id = %s")
            params.append(billing_id)

        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT country) as country_count
            FROM rtb_app_country_daily
            WHERE {" AND ".join(where)}
            """,
            tuple(params),
        )
        return row["country_count"] if row else 0

    async def get_app_size_breakdown(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get size breakdown for an app."""
        where = [
            "app_name = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
        ]
        params: list = [app_name, days]

        if billing_id:
            where.append("billing_id = %s")
            params.append(billing_id)

        return await pg_query(
            f"""
            SELECT
                creative_size,
                creative_format,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_app_size_daily
            WHERE {" AND ".join(where)}
            GROUP BY creative_size, creative_format
            ORDER BY SUM(reached_queries) DESC
            """,
            tuple(params),
        )

    async def get_app_country_breakdown(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get country breakdown for an app."""
        where = [
            "app_name = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
        ]
        params: list = [app_name, days]

        if billing_id:
            where.append("billing_id = %s")
            params.append(billing_id)

        return await pg_query(
            f"""
            SELECT
                country,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_app_country_daily
            WHERE {" AND ".join(where)}
            GROUP BY country
            ORDER BY SUM(reached_queries) DESC
            """,
            tuple(params),
        )

    async def get_app_creative_breakdown(
        self,
        app_name: str,
        days: int,
        billing_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get creative breakdown for an app."""
        where = [
            "app_name = %s",
            "metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')",
        ]
        params: list = [app_name, days]

        if billing_id:
            where.append("billing_id = %s")
            params.append(billing_id)

        params.append(limit)

        return await pg_query(
            f"""
            SELECT
                creative_id,
                creative_size,
                creative_format,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(clicks) as clicks,
                SUM(spend_micros) as spend_micros
            FROM rtb_app_creative_daily
            WHERE {" AND ".join(where)}
            GROUP BY creative_id, creative_size, creative_format
            ORDER BY SUM(reached_queries) DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_bid_filtering_for_creatives(
        self,
        creative_ids: list[str],
        days: int,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get bid filtering data for creatives."""
        if not creative_ids:
            return []

        return await pg_query(
            """
            SELECT
                filtering_reason,
                SUM(bids) as total_bids,
                SUM(bids_in_auction) as bids_passed,
                SUM(opportunity_cost_micros) as opportunity_cost_micros
            FROM rtb_bid_filtering
            WHERE creative_id = ANY(%s)
              AND metric_date::date >= (CURRENT_DATE - %s * INTERVAL '1 day')
            GROUP BY filtering_reason
            ORDER BY SUM(bids) DESC
            LIMIT %s
            """,
            (creative_ids, days, limit),
        )
