"""Conversion aggregates and health service."""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Any, Optional

from storage.postgres_database import pg_execute, pg_query, pg_query_one


def _to_date(value: str) -> date:
    return date.fromisoformat(value)


def _resolve_window(
    *,
    days: int,
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[date, date]:
    if start_date and end_date:
        return _to_date(start_date), _to_date(end_date)
    end = date.today()
    start = end - timedelta(days=max(days, 1) - 1)
    if start_date:
        start = _to_date(start_date)
    if end_date:
        end = _to_date(end_date)
    return start, end


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


class ConversionsService:
    """Service for conversion aggregate refresh/query and lag health."""

    async def refresh_aggregates(
        self,
        *,
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        start, end = _resolve_window(days=days, start_date=start_date, end_date=end_date)

        delete_sql = """
            DELETE FROM conversion_aggregates_daily
            WHERE agg_date BETWEEN %s::date AND %s::date
        """
        delete_params: list[Any] = [start.isoformat(), end.isoformat()]
        if buyer_id:
            delete_sql += " AND buyer_id = %s"
            delete_params.append(buyer_id)

        deleted_rows = await pg_execute(delete_sql, tuple(delete_params))

        buyer_clause = ""
        buyer_params: list[Any] = [start.isoformat(), end.isoformat()]
        if buyer_id:
            buyer_clause = " AND e.buyer_id = %s"
            buyer_params.append(buyer_id)

        rtb_buyer_clause = ""
        rtb_params: list[Any] = [start.isoformat(), end.isoformat()]
        if buyer_id:
            rtb_buyer_clause = " AND buyer_account_id = %s"
            rtb_params.append(buyer_id)

        insert_sql = f"""
            WITH conv AS (
                SELECT
                    event_ts::date AS agg_date,
                    e.buyer_id,
                    COALESCE(NULLIF(BTRIM(e.billing_id), ''), aj.matched_billing_id, '') AS billing_id,
                    COALESCE(NULLIF(BTRIM(e.country), ''), aj.matched_country, '') AS country,
                    COALESCE(NULLIF(BTRIM(e.publisher_id), ''), aj.matched_publisher_id, '') AS publisher_id,
                    COALESCE(NULLIF(BTRIM(e.creative_id), ''), aj.matched_creative_id, '') AS creative_id,
                    COALESCE(NULLIF(BTRIM(e.app_id), ''), aj.matched_app_id, '') AS app_id,
                    e.source_type,
                    e.event_type,
                    COUNT(*)::bigint AS event_count,
                    COALESCE(SUM(e.event_value), 0)::numeric(18,6) AS event_value_total
                FROM conversion_events e
                LEFT JOIN LATERAL (
                    SELECT
                        NULLIF(BTRIM(COALESCE(j.matched_billing_id, '')), '') AS matched_billing_id,
                        NULLIF(BTRIM(COALESCE(j.matched_country, '')), '') AS matched_country,
                        NULLIF(BTRIM(COALESCE(j.matched_publisher_id, '')), '') AS matched_publisher_id,
                        NULLIF(BTRIM(COALESCE(j.matched_creative_id, '')), '') AS matched_creative_id,
                        NULLIF(BTRIM(COALESCE(j.matched_app_id, '')), '') AS matched_app_id
                    FROM conversion_attribution_joins j
                    WHERE j.conversion_event_id = e.id
                      AND j.join_status = 'matched'
                    ORDER BY
                        CASE j.join_mode
                            WHEN 'exact_clickid' THEN 0
                            WHEN 'fallback_creative_time' THEN 1
                            ELSE 2
                        END,
                        COALESCE(j.confidence, 0) DESC,
                        j.updated_at DESC NULLS LAST,
                        j.id DESC
                    LIMIT 1
                ) aj ON TRUE
                WHERE e.event_ts::date BETWEEN %s::date AND %s::date
                    {buyer_clause}
                GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
            ),
            rtb AS (
                SELECT
                    metric_date::date AS agg_date,
                    buyer_account_id AS buyer_id,
                    COALESCE(billing_id, '') AS billing_id,
                    COALESCE(country, '') AS country,
                    COALESCE(publisher_id, '') AS publisher_id,
                    COALESCE(creative_id, '') AS creative_id,
                    COALESCE(app_id, '') AS app_id,
                    COALESCE(SUM(impressions), 0)::bigint AS impressions,
                    COALESCE(SUM(clicks), 0)::bigint AS clicks,
                    (COALESCE(SUM(spend_micros), 0)::numeric / 1000000.0)::numeric(18,6) AS spend_usd
                FROM rtb_daily
                WHERE metric_date::date BETWEEN %s::date AND %s::date
                    {rtb_buyer_clause}
                GROUP BY
                    metric_date::date,
                    buyer_account_id,
                    COALESCE(billing_id, ''),
                    COALESCE(country, ''),
                    COALESCE(publisher_id, ''),
                    COALESCE(creative_id, ''),
                    COALESCE(app_id, '')
            )
            INSERT INTO conversion_aggregates_daily (
                agg_date,
                buyer_id,
                billing_id,
                country,
                publisher_id,
                creative_id,
                app_id,
                source_type,
                event_type,
                event_count,
                event_value_total,
                impressions,
                clicks,
                spend_usd,
                cost_per_event,
                event_rate_pct,
                created_at,
                updated_at
            )
            SELECT
                c.agg_date,
                c.buyer_id,
                c.billing_id,
                c.country,
                c.publisher_id,
                c.creative_id,
                c.app_id,
                c.source_type,
                c.event_type,
                c.event_count,
                c.event_value_total,
                COALESCE(r.impressions, 0),
                COALESCE(r.clicks, 0),
                COALESCE(r.spend_usd, 0),
                CASE WHEN c.event_count > 0 THEN (COALESCE(r.spend_usd, 0) / c.event_count) ELSE NULL END,
                CASE WHEN COALESCE(r.clicks, 0) > 0 THEN (c.event_count::numeric * 100.0 / r.clicks::numeric) ELSE NULL END,
                NOW(),
                NOW()
            FROM conv c
            LEFT JOIN rtb r
                ON r.agg_date = c.agg_date
                AND r.buyer_id = c.buyer_id
                AND r.billing_id = c.billing_id
                AND r.country = c.country
                AND r.publisher_id = c.publisher_id
                AND r.creative_id = c.creative_id
                AND r.app_id = c.app_id
            ON CONFLICT (
                agg_date,
                buyer_id,
                billing_id,
                country,
                publisher_id,
                creative_id,
                app_id,
                source_type,
                event_type
            )
            DO UPDATE SET
                event_count = EXCLUDED.event_count,
                event_value_total = EXCLUDED.event_value_total,
                impressions = EXCLUDED.impressions,
                clicks = EXCLUDED.clicks,
                spend_usd = EXCLUDED.spend_usd,
                cost_per_event = EXCLUDED.cost_per_event,
                event_rate_pct = EXCLUDED.event_rate_pct,
                updated_at = NOW()
        """
        inserted_rows = await pg_execute(
            insert_sql,
            tuple([*buyer_params, *rtb_params]),
        )

        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "buyer_id": buyer_id,
            "deleted_rows": int(deleted_rows or 0),
            "upserted_rows": int(inserted_rows or 0),
        }

    async def get_aggregates(
        self,
        *,
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        buyer_id: Optional[str] = None,
        billing_id: Optional[str] = None,
        country: Optional[str] = None,
        publisher_id: Optional[str] = None,
        creative_id: Optional[str] = None,
        app_id: Optional[str] = None,
        source_type: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        start, end = _resolve_window(days=days, start_date=start_date, end_date=end_date)
        clauses = ["agg_date BETWEEN %s::date AND %s::date"]
        params: list[Any] = [start.isoformat(), end.isoformat()]

        if buyer_id:
            clauses.append("buyer_id = %s")
            params.append(buyer_id)
        if billing_id:
            clauses.append("billing_id = %s")
            params.append(billing_id)
        if country:
            clauses.append("country = %s")
            params.append(country)
        if publisher_id:
            clauses.append("publisher_id = %s")
            params.append(publisher_id)
        if creative_id:
            clauses.append("creative_id = %s")
            params.append(creative_id)
        if app_id:
            clauses.append("app_id = %s")
            params.append(app_id)
        if source_type:
            clauses.append("source_type = %s")
            params.append(source_type)
        if event_type:
            clauses.append("event_type = %s")
            params.append(event_type)

        where_sql = " AND ".join(clauses)
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        rows = await pg_query(
            f"""
            SELECT
                agg_date,
                buyer_id,
                billing_id,
                country,
                publisher_id,
                creative_id,
                app_id,
                source_type,
                event_type,
                event_count,
                event_value_total,
                impressions,
                clicks,
                spend_usd,
                cost_per_event,
                event_rate_pct,
                created_at,
                updated_at
            FROM conversion_aggregates_daily
            WHERE {where_sql}
            ORDER BY agg_date DESC, event_count DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*params, safe_limit, safe_offset]),
        )

        count_row = await pg_query_one(
            f"""
            SELECT COUNT(*) AS total_rows
            FROM conversion_aggregates_daily
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int((count_row or {}).get("total_rows") or 0)

        normalized = [
            {
                "agg_date": _to_iso(row.get("agg_date")),
                "buyer_id": str(row.get("buyer_id") or ""),
                "billing_id": str(row.get("billing_id") or ""),
                "country": str(row.get("country") or ""),
                "publisher_id": str(row.get("publisher_id") or ""),
                "creative_id": str(row.get("creative_id") or ""),
                "app_id": str(row.get("app_id") or ""),
                "source_type": str(row.get("source_type") or ""),
                "event_type": str(row.get("event_type") or ""),
                "event_count": int(row.get("event_count") or 0),
                "event_value_total": float(row.get("event_value_total") or 0.0),
                "impressions": int(row.get("impressions") or 0),
                "clicks": int(row.get("clicks") or 0),
                "spend_usd": float(row.get("spend_usd") or 0.0),
                "cost_per_event": (
                    float(row.get("cost_per_event"))
                    if row.get("cost_per_event") is not None
                    else None
                ),
                "event_rate_pct": (
                    float(row.get("event_rate_pct"))
                    if row.get("event_rate_pct") is not None
                    else None
                ),
                "created_at": _to_iso(row.get("created_at")),
                "updated_at": _to_iso(row.get("updated_at")),
            }
            for row in rows
        ]

        return {
            "rows": normalized,
            "meta": {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "total": total,
                "returned": len(normalized),
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": safe_offset + len(normalized) < total,
            },
        }

    async def get_health(self, *, buyer_id: Optional[str] = None) -> dict[str, Any]:
        buyer_clause = ""
        params: list[Any] = []
        if buyer_id:
            buyer_clause = " WHERE buyer_id = %s"
            params.append(buyer_id)

        ingestion = await pg_query_one(
            f"""
            SELECT
                COUNT(*) AS total_events,
                MAX(event_ts) AS max_event_ts,
                MAX(created_at) AS last_ingested_at
            FROM conversion_events
            {buyer_clause}
            """,
            tuple(params),
        )

        aggregate = await pg_query_one(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                MAX(agg_date) AS max_agg_date,
                MAX(updated_at) AS last_aggregated_at
            FROM conversion_aggregates_daily
            {buyer_clause}
            """,
            tuple(params),
        )

        now = datetime.now(timezone.utc)
        max_event_ts = ingestion.get("max_event_ts") if ingestion else None
        max_agg_date = aggregate.get("max_agg_date") if aggregate else None

        ingestion_lag_hours = None
        if isinstance(max_event_ts, datetime):
            if max_event_ts.tzinfo is None:
                max_event_ts = max_event_ts.replace(tzinfo=timezone.utc)
            ingestion_lag_hours = round((now - max_event_ts).total_seconds() / 3600.0, 2)

        aggregation_lag_days = None
        if isinstance(max_agg_date, date):
            aggregation_lag_days = (date.today() - max_agg_date).days

        state = "healthy"
        if int((ingestion or {}).get("total_events") or 0) == 0:
            state = "unavailable"
        elif ingestion_lag_hours is not None and ingestion_lag_hours > 72:
            state = "stale"
        elif aggregation_lag_days is not None and aggregation_lag_days > 7:
            state = "stale"
        elif (
            ingestion_lag_hours is not None and ingestion_lag_hours > 24
        ) or (
            aggregation_lag_days is not None and aggregation_lag_days > 2
        ):
            state = "degraded"

        return {
            "state": state,
            "buyer_id": buyer_id,
            "ingestion": {
                "total_events": int((ingestion or {}).get("total_events") or 0),
                "max_event_ts": _to_iso((ingestion or {}).get("max_event_ts")),
                "last_ingested_at": _to_iso((ingestion or {}).get("last_ingested_at")),
                "lag_hours": ingestion_lag_hours,
            },
            "aggregation": {
                "total_rows": int((aggregate or {}).get("total_rows") or 0),
                "max_agg_date": _to_iso((aggregate or {}).get("max_agg_date")),
                "last_aggregated_at": _to_iso((aggregate or {}).get("last_aggregated_at")),
                "lag_days": aggregation_lag_days,
            },
            "checked_at": now.isoformat(),
        }
