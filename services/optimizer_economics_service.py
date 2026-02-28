"""Economics metrics for optimizer context (effective/all-in CPM)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from storage.postgres_database import pg_query_one


_MONTHLY_HOSTING_COST_KEY = "optimizer_monthly_hosting_cost_usd"


def _parse_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _round_or_none(value: Optional[float], places: int = 6) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), places)


class OptimizerEconomicsService:
    """Computes spend + infra cost context for optimizer decisions."""

    async def get_effective_cpm(
        self,
        *,
        buyer_id: str,
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        billing_id: Optional[str] = None,
    ) -> dict[str, Any]:
        start, end = self._resolve_date_range(days=days, start_date=start_date, end_date=end_date)
        num_days = (end - start).days + 1

        clauses = ["metric_date BETWEEN %s AND %s", "buyer_account_id = %s"]
        params: list[Any] = [start, end, buyer_id]
        if billing_id:
            clauses.append("billing_id = %s")
            params.append(billing_id)
        where_sql = " AND ".join(clauses)

        row = await pg_query_one(
            f"""
            SELECT
                COALESCE(SUM(spend_micros), 0)::bigint AS spend_micros,
                COALESCE(SUM(impressions), 0)::bigint AS impressions
            FROM rtb_daily
            WHERE {where_sql}
            """,
            tuple(params),
        )
        spend_micros = int((row or {}).get("spend_micros") or 0)
        impressions = int((row or {}).get("impressions") or 0)
        media_spend_usd = spend_micros / 1_000_000.0

        setting_row = await pg_query_one(
            "SELECT value FROM system_settings WHERE key = %s",
            (_MONTHLY_HOSTING_COST_KEY,),
        )
        monthly_hosting_cost_usd = None
        if setting_row and setting_row.get("value") not in (None, ""):
            try:
                monthly_hosting_cost_usd = float(setting_row.get("value"))
            except (TypeError, ValueError):
                monthly_hosting_cost_usd = None

        infra_cost_period_usd = None
        media_cpm_usd = None
        infra_cpm_usd = None
        effective_cpm_usd = None

        if impressions > 0:
            media_cpm_usd = (media_spend_usd / impressions) * 1000.0

        if monthly_hosting_cost_usd is not None:
            daily_hosting_cost = monthly_hosting_cost_usd / 30.4375
            infra_cost_period_usd = daily_hosting_cost * num_days
            if impressions > 0:
                infra_cpm_usd = (infra_cost_period_usd / impressions) * 1000.0
                effective_cpm_usd = ((media_spend_usd + infra_cost_period_usd) / impressions) * 1000.0

        return {
            "buyer_id": buyer_id,
            "billing_id": billing_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": num_days,
            "impressions": impressions,
            "media_spend_usd": _round_or_none(media_spend_usd, 6) or 0.0,
            "monthly_hosting_cost_usd": _round_or_none(monthly_hosting_cost_usd, 6),
            "infra_cost_period_usd": _round_or_none(infra_cost_period_usd, 6),
            "media_cpm_usd": _round_or_none(media_cpm_usd, 6),
            "infra_cpm_usd": _round_or_none(infra_cpm_usd, 6),
            "effective_cpm_usd": _round_or_none(effective_cpm_usd, 6),
            "cost_context_ready": monthly_hosting_cost_usd is not None,
        }

    async def get_assumed_value(
        self,
        *,
        buyer_id: str,
        days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        billing_id: Optional[str] = None,
    ) -> dict[str, Any]:
        start, end = self._resolve_date_range(days=days, start_date=start_date, end_date=end_date)
        num_days = (end - start).days + 1

        clauses = ["metric_date BETWEEN %s AND %s", "buyer_account_id = %s"]
        params: list[Any] = [start, end, buyer_id]
        if billing_id:
            clauses.append("billing_id = %s")
            params.append(billing_id)
        where_sql = " AND ".join(clauses)

        totals = await pg_query_one(
            f"""
            SELECT
                COALESCE(SUM(spend_micros), 0)::bigint AS spend_micros,
                COALESCE(SUM(impressions), 0)::bigint AS impressions,
                COALESCE(SUM(clicks), 0)::bigint AS clicks,
                COALESCE(SUM(reached_queries), 0)::bigint AS reached_queries,
                COALESCE(SUM(bids_in_auction), 0)::bigint AS bids_in_auction,
                COALESCE(SUM(auctions_won), 0)::bigint AS auctions_won
            FROM rtb_daily
            WHERE {where_sql}
            """,
            tuple(params),
        ) or {}

        recent_days = min(7, num_days)
        recent_start = end - timedelta(days=recent_days - 1)
        previous_end = recent_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=recent_days - 1)

        trend_case_params: list[Any] = [recent_start, end, previous_start, previous_end]
        trend_where_params: list[Any] = [previous_start, end, buyer_id]
        trend_clauses = ["metric_date BETWEEN %s AND %s", "buyer_account_id = %s"]
        if billing_id:
            trend_clauses.append("billing_id = %s")
            trend_where_params.append(billing_id)
        trend_where_sql = " AND ".join(trend_clauses)
        trend = await pg_query_one(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN metric_date BETWEEN %s AND %s THEN spend_micros ELSE 0 END), 0)::bigint AS recent_spend_micros,
                COALESCE(SUM(CASE WHEN metric_date BETWEEN %s AND %s THEN spend_micros ELSE 0 END), 0)::bigint AS previous_spend_micros
            FROM rtb_daily
            WHERE {trend_where_sql}
            """,
            tuple([*trend_case_params, *trend_where_params]),
        ) or {}

        age_clauses = ["buyer_account_id = %s"]
        age_params: list[Any] = [buyer_id]
        if billing_id:
            age_clauses.append("billing_id = %s")
            age_params.append(billing_id)
        age_where_sql = " AND ".join(age_clauses)
        age_row = await pg_query_one(
            f"""
            SELECT MIN(metric_date) AS first_metric_date
            FROM rtb_daily
            WHERE {age_where_sql}
            """,
            tuple(age_params),
        ) or {}

        quality_clauses = ["metric_date BETWEEN %s AND %s", "buyer_account_id = %s"]
        quality_params: list[Any] = [start, end, buyer_id]
        quality = await pg_query_one(
            f"""
            SELECT
                COALESCE(SUM(viewable_impressions), 0)::bigint AS viewable_impressions,
                COALESCE(SUM(measurable_impressions), 0)::bigint AS measurable_impressions
            FROM rtb_quality
            WHERE {" AND ".join(quality_clauses)}
            """,
            tuple(quality_params),
        ) or {}

        spend_usd = int(totals.get("spend_micros") or 0) / 1_000_000.0
        avg_daily_spend = spend_usd / max(num_days, 1)
        impressions = int(totals.get("impressions") or 0)
        clicks = int(totals.get("clicks") or 0)
        reached_queries = int(totals.get("reached_queries") or 0)
        bids_in_auction = int(totals.get("bids_in_auction") or 0)
        auctions_won = int(totals.get("auctions_won") or 0)

        recent_spend = int(trend.get("recent_spend_micros") or 0) / 1_000_000.0
        previous_spend = int(trend.get("previous_spend_micros") or 0) / 1_000_000.0

        bid_rate = (bids_in_auction / reached_queries) if reached_queries > 0 else 0.0
        win_rate = (auctions_won / bids_in_auction) if bids_in_auction > 0 else 0.0
        ctr = (clicks / impressions) if impressions > 0 else 0.0
        viewable = int(quality.get("viewable_impressions") or 0)
        measurable = int(quality.get("measurable_impressions") or 0)
        viewability = (viewable / measurable) if measurable > 0 else None

        first_metric_date = age_row.get("first_metric_date")
        if isinstance(first_metric_date, datetime):
            first_metric_date = first_metric_date.date()
        account_age_days = (
            (end - first_metric_date).days + 1
            if isinstance(first_metric_date, date)
            else 0
        )
        account_age_months = max(account_age_days / 30.4375, 0.0)

        spend_level_score = self._spend_level_tier(avg_daily_spend)
        spend_trend_score = self._spend_trend_score(recent_spend, previous_spend)
        bid_rate_score = min(max(bid_rate, 0.0), 1.0)
        win_rate_score = min(max(win_rate, 0.0), 1.0)
        ctr_score = min(max(ctr / 0.05, 0.0), 1.0)
        age_score = min(max(account_age_months / 6.0, 0.0), 1.0)
        viewability_score = 0.5 if viewability is None else min(max(viewability / 0.7, 0.0), 1.0)

        assumed_value_score = (
            spend_level_score * 0.25
            + spend_trend_score * 0.20
            + bid_rate_score * 0.15
            + win_rate_score * 0.15
            + ctr_score * 0.10
            + age_score * 0.10
            + viewability_score * 0.05
        )

        return {
            "buyer_id": buyer_id,
            "billing_id": billing_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": num_days,
            "assumed_value_score": round(assumed_value_score, 6),
            "components": {
                "spend_level_score": round(spend_level_score, 6),
                "spend_trend_score": round(spend_trend_score, 6),
                "bid_rate_score": round(bid_rate_score, 6),
                "win_rate_score": round(win_rate_score, 6),
                "ctr_score": round(ctr_score, 6),
                "age_score": round(age_score, 6),
                "viewability_score": round(viewability_score, 6),
            },
            "metrics": {
                "spend_usd": round(spend_usd, 6),
                "avg_daily_spend_usd": round(avg_daily_spend, 6),
                "recent_spend_usd": round(recent_spend, 6),
                "previous_spend_usd": round(previous_spend, 6),
                "impressions": impressions,
                "clicks": clicks,
                "reached_queries": reached_queries,
                "bids_in_auction": bids_in_auction,
                "auctions_won": auctions_won,
                "bid_rate": round(bid_rate, 6),
                "win_rate": round(win_rate, 6),
                "ctr": round(ctr, 6),
                "viewability": round(viewability, 6) if viewability is not None else None,
                "account_age_months": round(account_age_months, 3),
            },
        }

    def _spend_level_tier(self, avg_daily_spend: float) -> float:
        if avg_daily_spend < 100:
            return 0.1
        if avg_daily_spend < 1000:
            return 0.4
        if avg_daily_spend < 10000:
            return 0.7
        return 1.0

    def _spend_trend_score(self, recent_spend: float, previous_spend: float) -> float:
        if previous_spend <= 0 and recent_spend > 0:
            return 1.0
        if previous_spend <= 0 and recent_spend <= 0:
            return 0.5
        trend_ratio = (recent_spend - previous_spend) / max(previous_spend, 1e-9)
        normalized = max(-1.0, min(trend_ratio, 1.0))
        return (normalized + 1.0) / 2.0

    def _resolve_date_range(
        self,
        *,
        days: int,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> tuple[date, date]:
        if start_date and end_date:
            start = _parse_date(start_date, "start_date")
            end = _parse_date(end_date, "end_date")
            if end < start:
                raise ValueError("end_date must be >= start_date")
            return start, end

        safe_days = max(1, min(days, 365))
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=safe_days - 1)
        return start, end
