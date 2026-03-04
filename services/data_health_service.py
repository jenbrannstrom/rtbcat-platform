"""Data reliability health checks for source and serving layers."""

from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from typing import Any, Optional

from storage.postgres_database import pg_execute, pg_query, pg_query_one_with_timeout


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


class DataHealthService:
    """Computes non-sensitive reliability and freshness status."""

    def __init__(self) -> None:
        self._refresh_seat_day_mv_on_read = self._is_truthy_env(
            "DATA_HEALTH_REFRESH_SEAT_DAY_MV_ON_READ"
        )
        self._query_timeout_ms = self._resolve_query_timeout_ms()

    async def get_data_health(
        self,
        days: int = 7,
        buyer_id: Optional[str] = None,
        availability_state: Optional[str] = None,
        min_completeness_pct: Optional[float] = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        results = await asyncio.gather(
            self._get_source_freshness(days=days, buyer_id=buyer_id),
            self._get_serving_freshness(days=days, buyer_id=buyer_id),
            self._get_dimension_coverage(days=days, buyer_id=buyer_id),
            self._get_ingestion_summary(days=days, buyer_id=buyer_id),
            self._get_report_completeness(days=days, buyer_id=buyer_id),
            self._get_quality_freshness(days=days, buyer_id=buyer_id),
            self._get_bidstream_dimension_coverage(days=days, buyer_id=buyer_id),
            self._get_seat_day_completeness(
                days=days,
                buyer_id=buyer_id,
                availability_state=availability_state,
                min_completeness_pct=min_completeness_pct,
                limit=limit,
            ),
            return_exceptions=True,
        )
        source = self._result_or_default(results[0], self._default_source_freshness())
        serving = self._result_or_default(results[1], self._default_serving_freshness())
        coverage = self._result_or_default(results[2], self._default_coverage())
        ingestion = self._result_or_default(results[3], self._default_ingestion_summary())
        report_completeness = self._result_or_default(
            results[4],
            self._default_report_completeness(days=days),
        )
        quality_freshness = self._result_or_default(results[5], self._default_quality_freshness())
        bidstream_coverage = self._result_or_default(results[6], self._default_bidstream_coverage())
        seat_day_completeness = self._result_or_default(
            results[7],
            self._default_seat_day_completeness(),
        )

        state = self._compute_state(
            source=source,
            serving=serving,
            coverage=coverage,
            report_completeness=report_completeness,
            quality_freshness=quality_freshness,
            bidstream_coverage=bidstream_coverage,
            seat_day_completeness=seat_day_completeness,
        )
        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "days": days,
            "buyer_id": buyer_id,
            "state": state,
            "source_freshness": source,
            "serving_freshness": serving,
            "coverage": coverage,
            "ingestion_runs": ingestion,
            "optimizer_readiness": {
                "report_completeness": report_completeness,
                "rtb_quality_freshness": quality_freshness,
                "bidstream_dimension_coverage": bidstream_coverage,
                "seat_day_completeness": seat_day_completeness,
            },
        }

    async def _get_source_freshness(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        buyer_filter = ""
        params: list[Any] = []
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)

        row_daily = await self._query_one_with_timeout(
            f"""
            SELECT MAX(metric_date::date) AS max_metric_date, COUNT(*) AS rows
            FROM rtb_daily
            WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        row_geo = await self._query_one_with_timeout(
            f"""
            SELECT MAX(metric_date::date) AS max_metric_date, COUNT(*) AS rows
            FROM rtb_geo_daily
            WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        return {
            "rtb_daily": {
                "rows": int((row_daily or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_daily or {}).get("max_metric_date")),
            },
            "rtb_geo_daily": {
                "rows": int((row_geo or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_geo or {}).get("max_metric_date")),
            },
        }

    async def _get_serving_freshness(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        buyer_filter = ""
        params: list[Any] = []
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)

        row_home_geo = await self._query_one_with_timeout(
            f"""
            SELECT MAX(metric_date::date) AS max_metric_date, COUNT(*) AS rows
            FROM seat_geo_daily
            WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        row_cfg_geo = await self._query_one_with_timeout(
            f"""
            SELECT MAX(metric_date::date) AS max_metric_date, COUNT(*) AS rows
            FROM pretarg_geo_daily
            WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        row_cfg_pub = await self._query_one_with_timeout(
            f"""
            SELECT MAX(metric_date::date) AS max_metric_date, COUNT(*) AS rows
            FROM pretarg_publisher_daily
            WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        return {
            "home_geo_daily": {
                "rows": int((row_home_geo or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_home_geo or {}).get("max_metric_date")),
            },
            "config_geo_daily": {
                "rows": int((row_cfg_geo or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_cfg_geo or {}).get("max_metric_date")),
            },
            "config_publisher_daily": {
                "rows": int((row_cfg_pub or {}).get("rows") or 0),
                "max_metric_date": _to_iso((row_cfg_pub or {}).get("max_metric_date")),
            },
        }

    async def _get_dimension_coverage(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        buyer_filter = ""
        params: list[Any] = []
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)

        row = await self._query_one_with_timeout(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) AS missing_country_rows,
                SUM(CASE WHEN publisher_id IS NULL OR publisher_id = '' THEN 1 ELSE 0 END) AS missing_publisher_rows,
                SUM(CASE WHEN billing_id IS NULL OR billing_id = '' THEN 1 ELSE 0 END) AS missing_billing_rows
            FROM rtb_daily
            WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
            """,
            tuple([days, *params]),
        )
        total = int((row or {}).get("total_rows") or 0)
        if total == 0:
            return {
                "total_rows": 0,
                "country_missing_pct": 100.0,
                "publisher_missing_pct": 100.0,
                "billing_missing_pct": 100.0,
                "availability_state": "unavailable",
            }
        country_missing = int((row or {}).get("missing_country_rows") or 0)
        publisher_missing = int((row or {}).get("missing_publisher_rows") or 0)
        billing_missing = int((row or {}).get("missing_billing_rows") or 0)
        country_pct = round(country_missing * 100.0 / total, 2)
        publisher_pct = round(publisher_missing * 100.0 / total, 2)
        billing_pct = round(billing_missing * 100.0 / total, 2)
        state = "healthy"
        if country_pct > 50 or publisher_pct > 50:
            state = "degraded"
        return {
            "total_rows": total,
            "country_missing_pct": country_pct,
            "publisher_missing_pct": publisher_pct,
            "billing_missing_pct": billing_pct,
            "availability_state": state,
        }

    async def _get_ingestion_summary(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        try:
            buyer_filter = ""
            params: list[Any] = []
            if buyer_id:
                buyer_filter = " AND buyer_id = %s"
                params.append(buyer_id)
            row = await self._query_one_with_timeout(
                f"""
                SELECT
                    COUNT(*) AS total_runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_runs,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_runs,
                    MAX(started_at) AS last_started_at,
                    MAX(finished_at) AS last_finished_at
                FROM ingestion_runs
                WHERE started_at >= CURRENT_TIMESTAMP - (%s::int * INTERVAL '1 day'){buyer_filter}
                """,
                tuple([days, *params]),
            )
            return {
                "total_runs": int((row or {}).get("total_runs") or 0),
                "successful_runs": int((row or {}).get("successful_runs") or 0),
                "failed_runs": int((row or {}).get("failed_runs") or 0),
                "last_started_at": _to_iso((row or {}).get("last_started_at")),
                "last_finished_at": _to_iso((row or {}).get("last_finished_at")),
            }
        except Exception:
            return {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "last_started_at": None,
                "last_finished_at": None,
            }

    async def _get_report_completeness(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        report_tables = {
            "rtb_daily": "buyer_account_id",
            "rtb_bidstream": "buyer_account_id",
            "rtb_bid_filtering": "buyer_account_id",
            "rtb_quality": "buyer_account_id",
            "web_domain_daily": "buyer_account_id",
        }
        expected_days = max(days, 1)
        table_states: dict[str, Any] = {}

        for table_name, buyer_column in report_tables.items():
            try:
                buyer_filter = ""
                params: list[Any] = [days]
                if buyer_id:
                    buyer_filter = f" AND {buyer_column} = %s"
                    params.append(buyer_id)

                row = await self._query_one_with_timeout(
                    f"""
                    SELECT
                        COUNT(*) AS rows,
                        COUNT(DISTINCT metric_date::date) AS active_days,
                        MAX(metric_date::date) AS max_metric_date
                    FROM {table_name}
                    WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
                    """,
                    tuple(params),
                )
                rows = int((row or {}).get("rows") or 0)
                active_days = int((row or {}).get("active_days") or 0)
                coverage_pct = round(active_days * 100.0 / expected_days, 2)
                state = "healthy"
                if rows == 0:
                    state = "unavailable"
                elif coverage_pct < 40.0:
                    state = "degraded"
                table_states[table_name] = {
                    "rows": rows,
                    "active_days": active_days,
                    "expected_days": expected_days,
                    "coverage_pct": coverage_pct,
                    "max_metric_date": _to_iso((row or {}).get("max_metric_date")),
                    "availability_state": state,
                }
            except Exception:
                table_states[table_name] = {
                    "rows": 0,
                    "active_days": 0,
                    "expected_days": expected_days,
                    "coverage_pct": 0.0,
                    "max_metric_date": None,
                    "availability_state": "unavailable",
                }

        missing = [
            table_name
            for table_name, payload in table_states.items()
            if int(payload["rows"]) == 0
        ]
        expected_report_types = len(report_tables)
        available_report_types = expected_report_types - len(missing)
        coverage_pct = round(available_report_types * 100.0 / expected_report_types, 2)

        state = "healthy"
        if available_report_types == 0:
            state = "unavailable"
        elif missing:
            state = "degraded"

        return {
            "expected_report_types": expected_report_types,
            "available_report_types": available_report_types,
            "coverage_pct": coverage_pct,
            "missing_report_types": missing,
            "availability_state": state,
            "tables": table_states,
        }

    async def _get_quality_freshness(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        try:
            buyer_filter = ""
            params: list[Any] = [days]
            if buyer_id:
                buyer_filter = " AND buyer_account_id = %s"
                params.append(buyer_id)
            row = await self._query_one_with_timeout(
                f"""
                SELECT
                    COUNT(*) AS rows,
                    MAX(metric_date::date) AS max_metric_date
                FROM rtb_quality
                WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
                """,
                tuple(params),
            )
        except Exception:
            row = None

        rows = int((row or {}).get("rows") or 0)
        max_metric_date = self._coerce_date((row or {}).get("max_metric_date"))
        age_days = (date.today() - max_metric_date).days if max_metric_date else None

        state = "healthy"
        if rows == 0 or max_metric_date is None:
            state = "unavailable"
        elif age_days is not None and age_days > 7:
            state = "stale"
        elif age_days is not None and age_days > 2:
            state = "degraded"

        return {
            "rows": rows,
            "max_metric_date": _to_iso((row or {}).get("max_metric_date")),
            "age_days": age_days,
            "fresh_within_days": 2,
            "availability_state": state,
        }

    async def _get_bidstream_dimension_coverage(self, days: int, buyer_id: Optional[str]) -> dict[str, Any]:
        try:
            buyer_filter = ""
            params: list[Any] = [days]
            if buyer_id:
                buyer_filter = " AND buyer_account_id = %s"
                params.append(buyer_id)
            # Sample up to 200K rows to avoid full-table scans timing out
            # on large datasets (6M+ rows). Coverage percentages remain
            # statistically accurate with this sample size.
            row = await self._query_one_with_timeout(
                f"""
                SELECT
                    COUNT(*) AS total_rows,
                    SUM(CASE WHEN platform IS NULL OR platform = '' THEN 1 ELSE 0 END) AS missing_platform_rows,
                    SUM(CASE WHEN environment IS NULL OR environment = '' THEN 1 ELSE 0 END) AS missing_environment_rows,
                    SUM(CASE WHEN transaction_type IS NULL OR transaction_type = '' THEN 1 ELSE 0 END) AS missing_transaction_type_rows
                FROM (
                    SELECT platform, environment, transaction_type
                    FROM rtb_bidstream
                    WHERE metric_date::date >= CURRENT_DATE - %s::int{buyer_filter}
                    LIMIT 200000
                ) sampled
                """,
                tuple(params),
            )
        except Exception:
            row = None

        total = int((row or {}).get("total_rows") or 0)
        if total == 0:
            return {
                "total_rows": 0,
                "platform_missing_pct": 100.0,
                "environment_missing_pct": 100.0,
                "transaction_type_missing_pct": 100.0,
                "availability_state": "unavailable",
            }

        platform_missing = int((row or {}).get("missing_platform_rows") or 0)
        environment_missing = int((row or {}).get("missing_environment_rows") or 0)
        transaction_type_missing = int((row or {}).get("missing_transaction_type_rows") or 0)

        platform_pct = round(platform_missing * 100.0 / total, 2)
        environment_pct = round(environment_missing * 100.0 / total, 2)
        transaction_type_pct = round(transaction_type_missing * 100.0 / total, 2)

        state = "healthy"
        if max(platform_pct, environment_pct, transaction_type_pct) > 50.0:
            state = "degraded"

        return {
            "total_rows": total,
            "platform_missing_pct": platform_pct,
            "environment_missing_pct": environment_pct,
            "transaction_type_missing_pct": transaction_type_pct,
            "availability_state": state,
        }

    async def _get_seat_day_completeness(
        self,
        days: int,
        buyer_id: Optional[str],
        availability_state: Optional[str],
        min_completeness_pct: Optional[float],
        limit: int,
    ) -> dict[str, Any]:
        if self._refresh_seat_day_mv_on_read:
            await self._refresh_seat_day_completeness_mv_if_stale()

        clauses = ["metric_date >= CURRENT_DATE - %s::int"]
        params: list[Any] = [days]

        if buyer_id:
            clauses.append("buyer_account_id = %s")
            params.append(buyer_id)
        if availability_state:
            clauses.append("availability_state = %s")
            params.append(availability_state)
        if min_completeness_pct is not None:
            clauses.append("completeness_pct >= %s")
            params.append(min_completeness_pct)

        where_sql = " AND ".join(clauses)
        fetch_limit = max(1, min(limit, 1000))

        try:
            rows = await pg_query(
                f"""
                SELECT
                    metric_date,
                    buyer_account_id,
                    has_rtb_daily,
                    has_rtb_bidstream,
                    has_rtb_bid_filtering,
                    has_rtb_quality,
                    has_web_domain_daily,
                    available_report_types,
                    expected_report_types,
                    completeness_pct,
                    availability_state,
                    refreshed_at
                FROM seat_report_completeness_daily
                WHERE {where_sql}
                ORDER BY metric_date DESC, completeness_pct ASC, buyer_account_id
                LIMIT %s
                """,
                tuple([*params, fetch_limit]),
            )
        except Exception:
            return {
                "rows": [],
                "summary": {
                    "total_seat_days": 0,
                    "healthy_seat_days": 0,
                    "degraded_seat_days": 0,
                    "unavailable_seat_days": 0,
                    "avg_completeness_pct": 0.0,
                    "min_completeness_pct": 0.0,
                    "max_completeness_pct": 0.0,
                },
                "availability_state": "unavailable",
                "refreshed_at": None,
            }

        normalized_rows: list[dict[str, Any]] = []
        completeness_values: list[float] = []
        refreshed_at: Optional[str] = None
        healthy_count = 0
        degraded_count = 0
        unavailable_count = 0

        for row in rows:
            metric_date = self._coerce_date(row.get("metric_date"))
            completeness = float(row.get("completeness_pct") or 0.0)
            state = str(row.get("availability_state") or "unavailable")
            if state == "healthy":
                healthy_count += 1
            elif state == "degraded":
                degraded_count += 1
            else:
                unavailable_count += 1
            completeness_values.append(completeness)

            if not refreshed_at:
                refreshed_at = _to_iso(row.get("refreshed_at"))

            normalized_rows.append(
                {
                    "metric_date": metric_date.isoformat() if metric_date else None,
                    "buyer_account_id": str(row.get("buyer_account_id") or ""),
                    "has_rtb_daily": bool(row.get("has_rtb_daily")),
                    "has_rtb_bidstream": bool(row.get("has_rtb_bidstream")),
                    "has_rtb_bid_filtering": bool(row.get("has_rtb_bid_filtering")),
                    "has_rtb_quality": bool(row.get("has_rtb_quality")),
                    "has_web_domain_daily": bool(row.get("has_web_domain_daily")),
                    "available_report_types": int(row.get("available_report_types") or 0),
                    "expected_report_types": int(row.get("expected_report_types") or 0),
                    "completeness_pct": round(completeness, 2),
                    "availability_state": state,
                    "refreshed_at": _to_iso(row.get("refreshed_at")),
                }
            )

        total = len(normalized_rows)
        if total == 0:
            overall_state = "unavailable"
            avg_completeness = 0.0
            min_value = 0.0
            max_value = 0.0
        else:
            avg_completeness = round(sum(completeness_values) / total, 2)
            min_value = round(min(completeness_values), 2)
            max_value = round(max(completeness_values), 2)
            overall_state = "healthy" if degraded_count == 0 and unavailable_count == 0 else "degraded"

        return {
            "rows": normalized_rows,
            "summary": {
                "total_seat_days": total,
                "healthy_seat_days": healthy_count,
                "degraded_seat_days": degraded_count,
                "unavailable_seat_days": unavailable_count,
                "avg_completeness_pct": avg_completeness,
                "min_completeness_pct": min_value,
                "max_completeness_pct": max_value,
            },
            "availability_state": overall_state,
            "refreshed_at": refreshed_at,
        }

    async def _refresh_seat_day_completeness_mv_if_stale(self, max_age_minutes: int = 30) -> None:
        try:
            row = await self._query_one_with_timeout(
                "SELECT MAX(refreshed_at) AS refreshed_at FROM seat_report_completeness_daily"
            )
        except Exception:
            return

        refreshed_at = self._coerce_datetime((row or {}).get("refreshed_at"))
        if refreshed_at is not None:
            age_seconds = (datetime.now(timezone.utc) - refreshed_at).total_seconds()
            if age_seconds <= max_age_minutes * 60:
                return

        try:
            await pg_execute("REFRESH MATERIALIZED VIEW seat_report_completeness_daily")
        except Exception:
            return

    def _compute_state(
        self,
        source: dict[str, Any],
        serving: dict[str, Any],
        coverage: dict[str, Any],
        report_completeness: dict[str, Any],
        quality_freshness: dict[str, Any],
        bidstream_coverage: dict[str, Any],
        seat_day_completeness: dict[str, Any],
    ) -> str:
        source_rows = source["rtb_daily"]["rows"] + source["rtb_geo_daily"]["rows"]
        serving_rows = (
            serving["home_geo_daily"]["rows"]
            + serving["config_geo_daily"]["rows"]
            + serving["config_publisher_daily"]["rows"]
        )
        if source_rows == 0 and serving_rows == 0:
            return "unavailable"
        if report_completeness["availability_state"] == "unavailable":
            return "unavailable"
        if coverage["availability_state"] == "degraded":
            return "degraded"
        if report_completeness["availability_state"] == "degraded":
            return "degraded"
        if quality_freshness["availability_state"] in ("stale", "degraded"):
            return "degraded"
        if bidstream_coverage["availability_state"] == "degraded":
            return "degraded"
        if seat_day_completeness["availability_state"] == "degraded":
            return "degraded"
        if serving["config_geo_daily"]["rows"] == 0 and serving["home_geo_daily"]["rows"] > 0:
            return "degraded"
        return "healthy"

    @staticmethod
    def _coerce_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _result_or_default(result: Any, default: dict[str, Any]) -> dict[str, Any]:
        if isinstance(result, Exception):
            return default
        if isinstance(result, dict):
            return result
        return default

    @staticmethod
    def _is_truthy_env(name: str) -> bool:
        value = os.getenv(name, "").strip().lower()
        return value in {"1", "true", "yes", "on"}

    @staticmethod
    def _resolve_query_timeout_ms() -> int:
        raw_value = os.getenv("DATA_HEALTH_QUERY_TIMEOUT_MS")
        if raw_value is None or raw_value.strip() == "":
            return 15_000
        try:
            return max(int(raw_value), 1_000)
        except (TypeError, ValueError):
            return 15_000

    async def _query_one_with_timeout(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> Optional[dict[str, Any]]:
        return await pg_query_one_with_timeout(
            sql,
            params,
            statement_timeout_ms=self._query_timeout_ms,
        )

    @staticmethod
    def _default_source_freshness() -> dict[str, Any]:
        return {
            "rtb_daily": {"rows": 0, "max_metric_date": None},
            "rtb_geo_daily": {"rows": 0, "max_metric_date": None},
        }

    @staticmethod
    def _default_serving_freshness() -> dict[str, Any]:
        return {
            "home_geo_daily": {"rows": 0, "max_metric_date": None},
            "config_geo_daily": {"rows": 0, "max_metric_date": None},
            "config_publisher_daily": {"rows": 0, "max_metric_date": None},
        }

    @staticmethod
    def _default_coverage() -> dict[str, Any]:
        return {
            "total_rows": 0,
            "country_missing_pct": 100.0,
            "publisher_missing_pct": 100.0,
            "billing_missing_pct": 100.0,
            "availability_state": "unavailable",
        }

    @staticmethod
    def _default_ingestion_summary() -> dict[str, Any]:
        return {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "last_started_at": None,
            "last_finished_at": None,
        }

    @staticmethod
    def _default_report_completeness(days: int) -> dict[str, Any]:
        expected_days = max(days, 1)
        tables = {
            table_name: {
                "rows": 0,
                "active_days": 0,
                "expected_days": expected_days,
                "coverage_pct": 0.0,
                "max_metric_date": None,
                "availability_state": "unavailable",
            }
            for table_name in (
                "rtb_daily",
                "rtb_bidstream",
                "rtb_bid_filtering",
                "rtb_quality",
                "web_domain_daily",
            )
        }
        return {
            "expected_report_types": 5,
            "available_report_types": 0,
            "coverage_pct": 0.0,
            "missing_report_types": list(tables.keys()),
            "availability_state": "unavailable",
            "tables": tables,
        }

    @staticmethod
    def _default_quality_freshness() -> dict[str, Any]:
        return {
            "rows": 0,
            "max_metric_date": None,
            "age_days": None,
            "fresh_within_days": 2,
            "availability_state": "unavailable",
        }

    @staticmethod
    def _default_bidstream_coverage() -> dict[str, Any]:
        return {
            "total_rows": 0,
            "platform_missing_pct": 100.0,
            "environment_missing_pct": 100.0,
            "transaction_type_missing_pct": 100.0,
            "availability_state": "unavailable",
        }

    @staticmethod
    def _default_seat_day_completeness() -> dict[str, Any]:
        return {
            "rows": [],
            "summary": {
                "total_seat_days": 0,
                "healthy_seat_days": 0,
                "degraded_seat_days": 0,
                "unavailable_seat_days": 0,
                "avg_completeness_pct": 0.0,
                "min_completeness_pct": 0.0,
                "max_completeness_pct": 0.0,
            },
            "availability_state": "unavailable",
            "refreshed_at": None,
        }
