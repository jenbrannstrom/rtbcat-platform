"""Attribution join service for conversion-to-RTB evidence and confidence."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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


class ConversionAttributionService:
    """Build and query attribution join evidence rows."""

    async def refresh_joins(
        self,
        *,
        buyer_id: str,
        source_type: str = "appsflyer",
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fallback_window_days: int = 1,
    ) -> dict[str, Any]:
        start, end = _resolve_window(days=days, start_date=start_date, end_date=end_date)
        safe_fallback_window_days = max(0, min(fallback_window_days, 7))

        deleted = await pg_execute(
            """
            DELETE FROM conversion_attribution_joins j
            USING conversion_events e
            WHERE j.conversion_event_id = e.id
              AND e.buyer_id = %s
              AND e.source_type = %s
              AND e.event_ts::date BETWEEN %s::date AND %s::date
            """,
            (buyer_id, source_type, start.isoformat(), end.isoformat()),
        )

        exact_inserted = await pg_execute(
            """
            INSERT INTO conversion_attribution_joins (
                conversion_event_id,
                conversion_event_ts,
                buyer_id,
                source_type,
                join_mode,
                join_status,
                confidence,
                reason,
                matched_metric_date,
                fallback_window_days,
                fallback_candidate_count,
                created_at,
                updated_at
            )
            SELECT
                e.id,
                e.event_ts,
                e.buyer_id,
                e.source_type,
                'exact_clickid',
                CASE
                    WHEN COALESCE(e.click_id, '') = '' THEN 'unmatched'
                    ELSE 'blocked'
                END,
                0::numeric(8,6),
                CASE
                    WHEN COALESCE(e.click_id, '') = '' THEN 'missing_click_id_in_conversion_event'
                    ELSE 'rtb_clickid_dimension_not_ingested'
                END,
                e.event_ts::date,
                %s,
                0,
                NOW(),
                NOW()
            FROM conversion_events e
            WHERE e.buyer_id = %s
              AND e.source_type = %s
              AND e.event_ts::date BETWEEN %s::date AND %s::date
            ON CONFLICT (conversion_event_id, join_mode) DO UPDATE SET
                join_status = EXCLUDED.join_status,
                confidence = EXCLUDED.confidence,
                reason = EXCLUDED.reason,
                matched_metric_date = EXCLUDED.matched_metric_date,
                fallback_window_days = EXCLUDED.fallback_window_days,
                fallback_candidate_count = EXCLUDED.fallback_candidate_count,
                updated_at = NOW()
            """,
            (
                safe_fallback_window_days,
                buyer_id,
                source_type,
                start.isoformat(),
                end.isoformat(),
            ),
        )

        fallback_inserted = await pg_execute(
            """
            WITH conv AS (
                SELECT
                    e.id AS conversion_event_id,
                    e.event_ts,
                    e.event_ts::date AS event_date,
                    e.buyer_id,
                    e.source_type,
                    COALESCE(e.creative_id, '') AS creative_id,
                    COALESCE(e.billing_id, '') AS billing_id,
                    COALESCE(e.app_id, '') AS app_id,
                    COALESCE(e.country, '') AS country
                FROM conversion_events e
                WHERE e.buyer_id = %s
                  AND e.source_type = %s
                  AND e.event_ts::date BETWEEN %s::date AND %s::date
            ),
            cand AS (
                SELECT
                    c.conversion_event_id,
                    r.metric_date,
                    COALESCE(r.billing_id, '') AS matched_billing_id,
                    COALESCE(r.creative_id, '') AS matched_creative_id,
                    COALESCE(r.app_id, '') AS matched_app_id,
                    COALESCE(r.country, '') AS matched_country,
                    COALESCE(r.publisher_id, '') AS matched_publisher_id,
                    COALESCE(SUM(r.impressions), 0)::bigint AS matched_impressions,
                    COALESCE(SUM(r.clicks), 0)::bigint AS matched_clicks,
                    (COALESCE(SUM(r.spend_micros), 0)::numeric / 1000000.0)::numeric(18,6) AS matched_spend_usd,
                    CASE WHEN r.metric_date = c.event_date THEN 1 ELSE 0 END AS same_day_rank,
                    CASE WHEN c.app_id <> '' AND r.app_id = c.app_id THEN 1 ELSE 0 END AS app_rank,
                    CASE WHEN c.country <> '' AND r.country = c.country THEN 1 ELSE 0 END AS country_rank,
                    CASE WHEN c.billing_id <> '' AND r.billing_id = c.billing_id THEN 1 ELSE 0 END AS billing_rank
                FROM conv c
                JOIN rtb_daily r
                  ON r.buyer_account_id = c.buyer_id
                 AND c.creative_id <> ''
                 AND r.creative_id = c.creative_id
                 AND r.metric_date BETWEEN (c.event_date - %s::int) AND (c.event_date + %s::int)
                GROUP BY
                    c.conversion_event_id,
                    r.metric_date,
                    COALESCE(r.billing_id, ''),
                    COALESCE(r.creative_id, ''),
                    COALESCE(r.app_id, ''),
                    COALESCE(r.country, ''),
                    COALESCE(r.publisher_id, ''),
                    same_day_rank,
                    app_rank,
                    country_rank,
                    billing_rank
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY conversion_event_id
                        ORDER BY
                            same_day_rank DESC,
                            app_rank DESC,
                            country_rank DESC,
                            billing_rank DESC,
                            matched_impressions DESC,
                            matched_spend_usd DESC
                    ) AS rn
                FROM cand
            ),
            chosen AS (
                SELECT * FROM ranked WHERE rn = 1
            )
            INSERT INTO conversion_attribution_joins (
                conversion_event_id,
                conversion_event_ts,
                buyer_id,
                source_type,
                join_mode,
                join_status,
                confidence,
                reason,
                matched_metric_date,
                matched_billing_id,
                matched_creative_id,
                matched_app_id,
                matched_country,
                matched_publisher_id,
                matched_impressions,
                matched_clicks,
                matched_spend_usd,
                fallback_window_days,
                fallback_candidate_count,
                created_at,
                updated_at
            )
            SELECT
                c.conversion_event_id,
                c.event_ts,
                c.buyer_id,
                c.source_type,
                'fallback_creative_time',
                CASE
                    WHEN c.creative_id = '' THEN 'unmatched'
                    WHEN ch.conversion_event_id IS NULL THEN 'unmatched'
                    ELSE 'matched'
                END,
                CASE
                    WHEN c.creative_id = '' OR ch.conversion_event_id IS NULL THEN 0::numeric(8,6)
                    ELSE LEAST(
                        0.95::numeric(8,6),
                        (
                            0.45
                            + CASE WHEN ch.same_day_rank = 1 THEN 0.25 ELSE 0 END
                            + CASE WHEN ch.app_rank = 1 THEN 0.15 ELSE 0 END
                            + CASE WHEN ch.country_rank = 1 THEN 0.10 ELSE 0 END
                            + CASE WHEN ch.billing_rank = 1 THEN 0.05 ELSE 0 END
                        )::numeric(8,6)
                    )
                END,
                CASE
                    WHEN c.creative_id = '' THEN 'missing_creative_id_in_conversion_event'
                    WHEN ch.conversion_event_id IS NULL THEN 'no_matching_rtb_daily_rows_in_window'
                    ELSE 'matched_by_creative_and_time_window'
                END,
                COALESCE(ch.metric_date, c.event_date),
                NULLIF(ch.matched_billing_id, ''),
                NULLIF(ch.matched_creative_id, ''),
                NULLIF(ch.matched_app_id, ''),
                NULLIF(ch.matched_country, ''),
                NULLIF(ch.matched_publisher_id, ''),
                COALESCE(ch.matched_impressions, 0),
                COALESCE(ch.matched_clicks, 0),
                COALESCE(ch.matched_spend_usd, 0)::numeric(18,6),
                %s,
                CASE WHEN ch.conversion_event_id IS NULL THEN 0 ELSE 1 END,
                NOW(),
                NOW()
            FROM conv c
            LEFT JOIN chosen ch
              ON ch.conversion_event_id = c.conversion_event_id
            ON CONFLICT (conversion_event_id, join_mode) DO UPDATE SET
                join_status = EXCLUDED.join_status,
                confidence = EXCLUDED.confidence,
                reason = EXCLUDED.reason,
                matched_metric_date = EXCLUDED.matched_metric_date,
                matched_billing_id = EXCLUDED.matched_billing_id,
                matched_creative_id = EXCLUDED.matched_creative_id,
                matched_app_id = EXCLUDED.matched_app_id,
                matched_country = EXCLUDED.matched_country,
                matched_publisher_id = EXCLUDED.matched_publisher_id,
                matched_impressions = EXCLUDED.matched_impressions,
                matched_clicks = EXCLUDED.matched_clicks,
                matched_spend_usd = EXCLUDED.matched_spend_usd,
                fallback_window_days = EXCLUDED.fallback_window_days,
                fallback_candidate_count = EXCLUDED.fallback_candidate_count,
                updated_at = NOW()
            """,
            (
                buyer_id,
                source_type,
                start.isoformat(),
                end.isoformat(),
                safe_fallback_window_days,
                safe_fallback_window_days,
                safe_fallback_window_days,
            ),
        )

        summary = await self.get_summary(
            buyer_id=buyer_id,
            source_type=source_type,
            days=days,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "buyer_id": buyer_id,
            "source_type": source_type,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "deleted_rows": int(deleted or 0),
            "exact_rows_upserted": int(exact_inserted or 0),
            "fallback_rows_upserted": int(fallback_inserted or 0),
            "fallback_window_days": safe_fallback_window_days,
            "summary": summary,
        }

    async def get_summary(
        self,
        *,
        buyer_id: str,
        source_type: str = "appsflyer",
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        start, end = _resolve_window(days=days, start_date=start_date, end_date=end_date)
        params = (buyer_id, source_type, start.isoformat(), end.isoformat())

        total_events_row = await pg_query_one(
            """
            SELECT COUNT(*) AS total_events
            FROM conversion_events
            WHERE buyer_id = %s
              AND source_type = %s
              AND event_ts::date BETWEEN %s::date AND %s::date
            """,
            params,
        )
        total_events = int((total_events_row or {}).get("total_events") or 0)

        rows = await pg_query(
            """
            SELECT
                join_mode,
                join_status,
                COUNT(*)::bigint AS row_count,
                AVG(confidence)::numeric(8,6) AS avg_confidence,
                SUM(CASE WHEN confidence >= 0.80 THEN 1 ELSE 0 END)::bigint AS high_confidence_count
            FROM conversion_attribution_joins
            WHERE buyer_id = %s
              AND source_type = %s
              AND conversion_event_ts::date BETWEEN %s::date AND %s::date
            GROUP BY join_mode, join_status
            ORDER BY join_mode, join_status
            """,
            params,
        )

        per_mode: dict[str, dict[str, Any]] = {}
        for row in rows:
            mode = str(row.get("join_mode") or "")
            status = str(row.get("join_status") or "")
            mode_bucket = per_mode.setdefault(
                mode,
                {
                    "mode": mode,
                    "matched": 0,
                    "unmatched": 0,
                    "blocked": 0,
                    "avg_confidence": 0.0,
                    "high_confidence_count": 0,
                    "_confidence_weighted_sum": 0.0,
                },
            )
            count = int(row.get("row_count") or 0)
            avg_conf = float(row.get("avg_confidence") or 0.0)
            mode_bucket[status] = count
            mode_bucket["high_confidence_count"] += int(row.get("high_confidence_count") or 0)
            mode_bucket["_confidence_weighted_sum"] += avg_conf * count

        mode_rows: list[dict[str, Any]] = []
        for mode_name, bucket in per_mode.items():
            mode_total = int(bucket.get("matched", 0)) + int(bucket.get("unmatched", 0)) + int(bucket.get("blocked", 0))
            avg_confidence = (
                float(bucket["_confidence_weighted_sum"]) / mode_total if mode_total > 0 else 0.0
            )
            mode_rows.append(
                {
                    "mode": mode_name,
                    "matched": int(bucket.get("matched", 0)),
                    "unmatched": int(bucket.get("unmatched", 0)),
                    "blocked": int(bucket.get("blocked", 0)),
                    "total": mode_total,
                    "match_rate_pct": round((int(bucket.get("matched", 0)) * 100.0 / mode_total), 2)
                    if mode_total > 0
                    else 0.0,
                    "avg_confidence": round(avg_confidence, 6),
                    "high_confidence_count": int(bucket.get("high_confidence_count", 0)),
                }
            )
        mode_rows.sort(key=lambda row: row["mode"])

        return {
            "buyer_id": buyer_id,
            "source_type": source_type,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "total_events": total_events,
            "modes": mode_rows,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def list_joins(
        self,
        *,
        buyer_id: str,
        source_type: str = "appsflyer",
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        join_mode: Optional[str] = None,
        join_status: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        start, end = _resolve_window(days=days, start_date=start_date, end_date=end_date)
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        clauses = [
            "buyer_id = %s",
            "source_type = %s",
            "conversion_event_ts::date BETWEEN %s::date AND %s::date",
        ]
        params: list[Any] = [buyer_id, source_type, start.isoformat(), end.isoformat()]

        if join_mode:
            clauses.append("join_mode = %s")
            params.append(join_mode)
        if join_status:
            clauses.append("join_status = %s")
            params.append(join_status)
        if min_confidence is not None:
            clauses.append("confidence >= %s")
            params.append(max(0.0, min(float(min_confidence), 1.0)))

        where_sql = " AND ".join(clauses)

        rows = await pg_query(
            f"""
            SELECT
                id,
                conversion_event_id,
                conversion_event_ts,
                buyer_id,
                source_type,
                join_mode,
                join_status,
                confidence,
                reason,
                matched_metric_date,
                matched_billing_id,
                matched_creative_id,
                matched_app_id,
                matched_country,
                matched_publisher_id,
                matched_impressions,
                matched_clicks,
                matched_spend_usd,
                fallback_window_days,
                fallback_candidate_count,
                created_at,
                updated_at
            FROM conversion_attribution_joins
            WHERE {where_sql}
            ORDER BY conversion_event_ts DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*params, safe_limit, safe_offset]),
        )

        count_row = await pg_query_one(
            f"""
            SELECT COUNT(*) AS total_rows
            FROM conversion_attribution_joins
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int((count_row or {}).get("total_rows") or 0)

        normalized = [
            {
                "id": int(row.get("id") or 0),
                "conversion_event_id": int(row.get("conversion_event_id") or 0),
                "conversion_event_ts": _to_iso(row.get("conversion_event_ts")),
                "buyer_id": str(row.get("buyer_id") or ""),
                "source_type": str(row.get("source_type") or ""),
                "join_mode": str(row.get("join_mode") or ""),
                "join_status": str(row.get("join_status") or ""),
                "confidence": float(row.get("confidence") or 0.0),
                "reason": str(row.get("reason") or ""),
                "matched_metric_date": _to_iso(row.get("matched_metric_date")),
                "matched_billing_id": str(row.get("matched_billing_id") or ""),
                "matched_creative_id": str(row.get("matched_creative_id") or ""),
                "matched_app_id": str(row.get("matched_app_id") or ""),
                "matched_country": str(row.get("matched_country") or ""),
                "matched_publisher_id": str(row.get("matched_publisher_id") or ""),
                "matched_impressions": int(row.get("matched_impressions") or 0),
                "matched_clicks": int(row.get("matched_clicks") or 0),
                "matched_spend_usd": float(row.get("matched_spend_usd") or 0.0),
                "fallback_window_days": int(row.get("fallback_window_days") or 0),
                "fallback_candidate_count": int(row.get("fallback_candidate_count") or 0),
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
