#!/usr/bin/env python3
"""Compare media-buyer read contracts across two CatScan PostgreSQL databases.

The contracts in this module are deliberately close to future MCP tools:
explicit buyer scope, explicit date windows, deterministic ordering, canonical
spend semantics, and read-only/precomputed data sources.

Database URLs are read from environment variables rather than command-line
arguments so credentials do not appear in the process list.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from uuid import UUID


class SmokeError(RuntimeError):
    """Raised when the dual-database smoke run cannot be performed safely."""


class QueryEndpoint(Protocol):
    """Small query interface used by the live runner and unit-test fakes."""

    label: str

    def query(
        self,
        sql: str,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read-only query and return dictionary rows."""

    def close(self) -> None:
        """Close any endpoint resources."""


@dataclass(frozen=True)
class ToolContract:
    """One deterministic database contract intended to become an MCP tool."""

    name: str
    description: str
    key_columns: tuple[str, ...]
    sql: str


@dataclass(frozen=True)
class SmokeContext:
    """Parameters shared by all media-buyer contract queries."""

    buyer_ids: tuple[str, ...]
    start_date: date
    end_date: date
    top_limit: int

    def query_params(self) -> dict[str, Any]:
        return {
            "buyer_ids": list(self.buyer_ids),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "top_limit": self.top_limit,
        }


@dataclass(frozen=True)
class QueryDigest:
    """Non-sensitive evidence for one query result."""

    row_count: int
    sha256: str
    duration_ms: float


@dataclass(frozen=True)
class DifferenceSummary:
    """Safe mismatch summary that omits business metric values."""

    source_only: int
    target_only: int
    changed: int
    samples: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ContractResult:
    """Comparison result for one future MCP tool contract."""

    contract: str
    description: str
    passed: bool
    source: QueryDigest
    target: QueryDigest
    differences: DifferenceSummary


DISCOVER_BUYERS_SQL = """
SELECT buyer_id::text AS buyer_id
FROM public.buyer_seats
ORDER BY buyer_id
"""


DISCOVER_LATEST_SPEND_DATE_SQL = """
SELECT MAX(metric_date) AS latest_metric_date
FROM public.rtb_buyer_spend_daily
"""


TOOL_CONTRACTS: tuple[ToolContract, ...] = (
    ToolContract(
        name="catscan.list_buyers",
        description="List the buyer seats visible to the caller and their reporting currency.",
        key_columns=("buyer_id",),
        sql="""
            SELECT
                bs.buyer_id::text AS buyer_id,
                bs.bidder_id::text AS bidder_id,
                bs.display_name,
                bs.active,
                bs.creative_count,
                NULLIF(to_jsonb(bs)->>'currency_code', '') AS currency
            FROM public.buyer_seats AS bs
            WHERE bs.buyer_id = ANY(%(buyer_ids)s::text[])
            ORDER BY bs.buyer_id
        """,
    ),
    ToolContract(
        name="catscan.get_data_freshness",
        description="Report the available historical range in each compiled buyer dataset.",
        key_columns=("buyer_id", "dataset"),
        sql="""
            WITH freshness AS (
                SELECT
                    buyer_account_id::text AS buyer_id,
                    'buyer_spend'::text AS dataset,
                    MIN(metric_date) AS first_metric_date,
                    MAX(metric_date) AS latest_metric_date,
                    COUNT(*)::bigint AS source_rows
                FROM public.rtb_buyer_spend_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date <= %(end_date)s
                GROUP BY buyer_account_id
                UNION ALL
                SELECT
                    buyer_account_id::text,
                    'seat_funnel'::text,
                    MIN(metric_date),
                    MAX(metric_date),
                    COUNT(*)::bigint
                FROM public.home_seat_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date <= %(end_date)s
                GROUP BY buyer_account_id
                UNION ALL
                SELECT
                    buyer_account_id::text,
                    'geo'::text,
                    MIN(metric_date),
                    MAX(metric_date),
                    COUNT(*)::bigint
                FROM public.home_geo_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date <= %(end_date)s
                GROUP BY buyer_account_id
                UNION ALL
                SELECT
                    buyer_account_id::text,
                    'publisher'::text,
                    MIN(metric_date),
                    MAX(metric_date),
                    COUNT(*)::bigint
                FROM public.home_publisher_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date <= %(end_date)s
                GROUP BY buyer_account_id
                UNION ALL
                SELECT
                    buyer_account_id::text,
                    'config'::text,
                    MIN(metric_date),
                    MAX(metric_date),
                    COUNT(*)::bigint
                FROM public.home_config_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date <= %(end_date)s
                GROUP BY buyer_account_id
            )
            SELECT *
            FROM freshness
            ORDER BY buyer_id, dataset
        """,
    ),
    ToolContract(
        name="catscan.get_daily_spend",
        description="Return date-explicit canonical spend, impressions, clicks, and gaps.",
        key_columns=("buyer_id", "metric_date"),
        sql="""
            WITH requested AS (
                SELECT
                    buyer_id,
                    generate_series(
                        %(start_date)s::date,
                        %(end_date)s::date,
                        interval '1 day'
                    )::date AS metric_date
                FROM unnest(%(buyer_ids)s::text[]) AS buyer_id
            )
            SELECT
                requested.buyer_id,
                requested.metric_date,
                COALESCE(spend.impressions, 0)::bigint AS impressions,
                COALESCE(spend.clicks, 0)::bigint AS clicks,
                COALESCE(spend.spend_micros, 0)::bigint AS spend_micros,
                CASE WHEN spend.metric_date IS NULL THEN 'missing' ELSE 'present' END
                    AS source_status
            FROM requested
            LEFT JOIN public.rtb_buyer_spend_daily AS spend
              ON spend.buyer_account_id = requested.buyer_id
             AND spend.metric_date = requested.metric_date
            ORDER BY requested.buyer_id, requested.metric_date
        """,
    ),
    ToolContract(
        name="catscan.get_monthly_spend",
        description="Reconcile canonical buyer spend by calendar month through the cutoff.",
        key_columns=("buyer_id", "metric_month"),
        sql="""
            SELECT
                spend.buyer_account_id::text AS buyer_id,
                date_trunc('month', spend.metric_date)::date AS metric_month,
                MIN(spend.metric_date) AS first_metric_date,
                MAX(spend.metric_date) AS latest_metric_date,
                COUNT(*)::bigint AS source_days,
                SUM(COALESCE(spend.impressions, 0))::bigint AS impressions,
                SUM(COALESCE(spend.clicks, 0))::bigint AS clicks,
                SUM(COALESCE(spend.spend_micros, 0))::bigint AS spend_micros
            FROM public.rtb_buyer_spend_daily AS spend
            WHERE spend.buyer_account_id = ANY(%(buyer_ids)s::text[])
              AND spend.metric_date <= %(end_date)s
            GROUP BY spend.buyer_account_id, date_trunc('month', spend.metric_date)
            ORDER BY spend.buyer_account_id, metric_month
        """,
    ),
    ToolContract(
        name="catscan.get_all_time_spend",
        description="Reconcile each buyer's complete canonical spend history through the cutoff.",
        key_columns=("buyer_id",),
        sql="""
            WITH buyers AS (
                SELECT unnest(%(buyer_ids)s::text[]) AS buyer_id
            )
            SELECT
                buyers.buyer_id,
                MIN(spend.metric_date) AS first_metric_date,
                MAX(spend.metric_date) AS latest_metric_date,
                COUNT(spend.metric_date)::bigint AS source_days,
                COALESCE(SUM(spend.impressions), 0)::bigint AS impressions,
                COALESCE(SUM(spend.clicks), 0)::bigint AS clicks,
                COALESCE(SUM(spend.spend_micros), 0)::bigint AS spend_micros
            FROM buyers
            LEFT JOIN public.rtb_buyer_spend_daily AS spend
              ON spend.buyer_account_id = buyers.buyer_id
             AND spend.metric_date <= %(end_date)s
            GROUP BY buyers.buyer_id
            ORDER BY buyers.buyer_id
        """,
    ),
    ToolContract(
        name="catscan.get_performance_summary",
        description="Summarize the buyer funnel, canonical spend, and auction outcomes.",
        key_columns=("buyer_id",),
        sql="""
            WITH buyers AS (
                SELECT unnest(%(buyer_ids)s::text[]) AS buyer_id
            ),
            funnel AS (
                SELECT
                    buyer_account_id::text AS buyer_id,
                    SUM(COALESCE(reached_queries, 0))::bigint AS reached_queries,
                    SUM(COALESCE(bid_requests, 0))::bigint AS bid_requests,
                    SUM(COALESCE(successful_responses, 0))::bigint AS successful_responses,
                    SUM(COALESCE(bids, 0))::bigint AS bids,
                    SUM(COALESCE(impressions, 0))::bigint AS impressions,
                    SUM(COALESCE(auctions_won, 0))::bigint AS seat_auctions_won
                FROM public.home_seat_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id
            ),
            spend AS (
                SELECT
                    buyer_account_id::text AS buyer_id,
                    SUM(COALESCE(impressions, 0))::bigint AS spend_impressions,
                    SUM(COALESCE(clicks, 0))::bigint AS clicks,
                    SUM(COALESCE(spend_micros, 0))::bigint AS spend_micros
                FROM public.rtb_buyer_spend_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id
            ),
            auctions AS (
                SELECT
                    buyer_account_id::text AS buyer_id,
                    SUM(COALESCE(bids_in_auction, 0))::bigint AS bids_in_auction,
                    SUM(COALESCE(auctions_won, 0))::bigint AS config_auctions_won
                FROM public.home_config_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id
            )
            SELECT
                buyers.buyer_id,
                COALESCE(funnel.reached_queries, 0)::bigint AS reached_queries,
                COALESCE(funnel.bid_requests, 0)::bigint AS bid_requests,
                COALESCE(funnel.successful_responses, 0)::bigint AS successful_responses,
                COALESCE(funnel.bids, 0)::bigint AS bids,
                COALESCE(funnel.impressions, 0)::bigint AS impressions,
                COALESCE(funnel.seat_auctions_won, 0)::bigint AS seat_auctions_won,
                COALESCE(spend.spend_impressions, 0)::bigint AS spend_impressions,
                COALESCE(spend.clicks, 0)::bigint AS clicks,
                COALESCE(spend.spend_micros, 0)::bigint AS spend_micros,
                COALESCE(auctions.bids_in_auction, 0)::bigint AS bids_in_auction,
                COALESCE(auctions.config_auctions_won, 0)::bigint AS config_auctions_won
            FROM buyers
            LEFT JOIN funnel USING (buyer_id)
            LEFT JOIN spend USING (buyer_id)
            LEFT JOIN auctions USING (buyer_id)
            ORDER BY buyers.buyer_id
        """,
    ),
    ToolContract(
        name="catscan.get_report_completeness",
        description="Identify missing compiled source days before producing a buyer report.",
        key_columns=("buyer_id", "metric_date"),
        sql="""
            WITH requested AS (
                SELECT
                    buyer_id,
                    generate_series(
                        %(start_date)s::date,
                        %(end_date)s::date,
                        interval '1 day'
                    )::date AS metric_date
                FROM unnest(%(buyer_ids)s::text[]) AS buyer_id
            ),
            spend AS (
                SELECT buyer_account_id::text AS buyer_id, metric_date, COUNT(*)::int AS rows
                FROM public.rtb_buyer_spend_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id, metric_date
            ),
            seat AS (
                SELECT buyer_account_id::text AS buyer_id, metric_date, COUNT(*)::int AS rows
                FROM public.home_seat_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id, metric_date
            ),
            geo AS (
                SELECT buyer_account_id::text AS buyer_id, metric_date, COUNT(*)::int AS rows
                FROM public.home_geo_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id, metric_date
            ),
            publisher AS (
                SELECT buyer_account_id::text AS buyer_id, metric_date, COUNT(*)::int AS rows
                FROM public.home_publisher_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id, metric_date
            ),
            config AS (
                SELECT buyer_account_id::text AS buyer_id, metric_date, COUNT(*)::int AS rows
                FROM public.home_config_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id, metric_date
            )
            SELECT
                requested.buyer_id,
                requested.metric_date,
                COALESCE(spend.rows, 0)::int AS spend_rows,
                COALESCE(seat.rows, 0)::int AS seat_rows,
                COALESCE(geo.rows, 0)::int AS geo_rows,
                COALESCE(publisher.rows, 0)::int AS publisher_rows,
                COALESCE(config.rows, 0)::int AS config_rows
            FROM requested
            LEFT JOIN spend USING (buyer_id, metric_date)
            LEFT JOIN seat USING (buyer_id, metric_date)
            LEFT JOIN geo USING (buyer_id, metric_date)
            LEFT JOIN publisher USING (buyer_id, metric_date)
            LEFT JOIN config USING (buyer_id, metric_date)
            ORDER BY requested.buyer_id, requested.metric_date
        """,
    ),
    ToolContract(
        name="catscan.get_top_geos",
        description="Rank countries for each buyer by impressions and reached queries.",
        key_columns=("buyer_id", "rank"),
        sql="""
            WITH totals AS (
                SELECT
                    buyer_account_id::text AS buyer_id,
                    country,
                    SUM(COALESCE(reached_queries, 0))::bigint AS reached_queries,
                    SUM(COALESCE(impressions, 0))::bigint AS impressions,
                    SUM(COALESCE(bids, 0))::bigint AS bids,
                    SUM(COALESCE(auctions_won, 0))::bigint AS auctions_won
                FROM public.home_geo_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id, country
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY buyer_id
                        ORDER BY impressions DESC, reached_queries DESC, country
                    )::int AS rank
                FROM totals
            )
            SELECT buyer_id, rank, country, reached_queries, impressions, bids, auctions_won
            FROM ranked
            WHERE rank <= %(top_limit)s
            ORDER BY buyer_id, rank
        """,
    ),
    ToolContract(
        name="catscan.get_top_publishers",
        description="Rank publishers for each buyer by impressions and reached queries.",
        key_columns=("buyer_id", "rank"),
        sql="""
            WITH totals AS (
                SELECT
                    buyer_account_id::text AS buyer_id,
                    publisher_id,
                    COALESCE(MAX(publisher_name), publisher_id) AS publisher_name,
                    SUM(COALESCE(reached_queries, 0))::bigint AS reached_queries,
                    SUM(COALESCE(impressions, 0))::bigint AS impressions,
                    SUM(COALESCE(bids, 0))::bigint AS bids,
                    SUM(COALESCE(auctions_won, 0))::bigint AS auctions_won
                FROM public.home_publisher_daily
                WHERE buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY buyer_account_id, publisher_id
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY buyer_id
                        ORDER BY impressions DESC, reached_queries DESC, publisher_id
                    )::int AS rank
                FROM totals
            )
            SELECT
                buyer_id,
                rank,
                publisher_id,
                publisher_name,
                reached_queries,
                impressions,
                bids,
                auctions_won
            FROM ranked
            WHERE rank <= %(top_limit)s
            ORDER BY buyer_id, rank
        """,
    ),
    ToolContract(
        name="catscan.get_top_configs",
        description="Rank pretargeting configurations for each buyer by impressions.",
        key_columns=("buyer_id", "rank"),
        sql="""
            WITH totals AS (
                SELECT
                    h.buyer_account_id::text AS buyer_id,
                    h.billing_id,
                    COALESCE(MAX(pc.display_name), h.billing_id) AS display_name,
                    SUM(COALESCE(h.reached_queries, 0))::bigint AS reached_queries,
                    SUM(COALESCE(h.impressions, 0))::bigint AS impressions,
                    SUM(COALESCE(h.bids_in_auction, 0))::bigint AS bids_in_auction,
                    SUM(COALESCE(h.auctions_won, 0))::bigint AS auctions_won
                FROM public.home_config_daily AS h
                LEFT JOIN public.pretargeting_configs AS pc
                  ON pc.billing_id = h.billing_id
                 AND pc.bidder_id = h.buyer_account_id
                WHERE h.buyer_account_id = ANY(%(buyer_ids)s::text[])
                  AND h.metric_date BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY h.buyer_account_id, h.billing_id
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY buyer_id
                        ORDER BY impressions DESC, reached_queries DESC, billing_id
                    )::int AS rank
                FROM totals
            )
            SELECT
                buyer_id,
                rank,
                billing_id,
                display_name,
                reached_queries,
                impressions,
                bids_in_auction,
                auctions_won
            FROM ranked
            WHERE rank <= %(top_limit)s
            ORDER BY buyer_id, rank
        """,
    ),
)


def normalize_value(value: Any) -> Any:
    """Convert psycopg values into stable JSON-compatible values."""

    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return format(value, ".17g")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, Mapping):
        return {
            str(key): normalize_value(nested_value)
            for key, nested_value in sorted(
                value.items(), key=lambda item: str(item[0])
            )
        }
    if isinstance(value, (list, tuple)):
        return [normalize_value(item) for item in value]
    return str(value)


def normalize_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize rows without changing the database's deterministic ordering."""

    return [
        {str(key): normalize_value(value) for key, value in row.items()} for row in rows
    ]


def rows_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    """Hash canonical JSON rows for compact migration evidence."""

    payload = json.dumps(
        normalize_rows(rows),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _key_hash(key: tuple[Any, ...]) -> str:
    payload = json.dumps(normalize_value(key), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compare_rows(
    source_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    *,
    key_columns: Sequence[str],
    sample_limit: int = 5,
) -> DifferenceSummary:
    """Compare keyed rows while keeping metric values out of diagnostics."""

    normalized_source = normalize_rows(source_rows)
    normalized_target = normalize_rows(target_rows)

    def keyed(
        rows: Sequence[Mapping[str, Any]],
    ) -> dict[tuple[Any, ...], Mapping[str, Any]]:
        result: dict[tuple[Any, ...], Mapping[str, Any]] = {}
        for row in rows:
            key = tuple(row.get(column) for column in key_columns)
            if key in result:
                raise SmokeError(
                    f"Contract key {tuple(key_columns)} is not unique "
                    f"(duplicate key hash {_key_hash(key)})."
                )
            result[key] = row
        return result

    source_by_key = keyed(normalized_source)
    target_by_key = keyed(normalized_target)
    source_keys = set(source_by_key)
    target_keys = set(target_by_key)
    source_only_keys = sorted(source_keys - target_keys, key=repr)
    target_only_keys = sorted(target_keys - source_keys, key=repr)
    changed_keys = [
        key
        for key in sorted(source_keys & target_keys, key=repr)
        if source_by_key[key] != target_by_key[key]
    ]

    samples: list[dict[str, Any]] = []
    for side, keys in (
        ("source_only", source_only_keys),
        ("target_only", target_only_keys),
    ):
        for key in keys:
            if len(samples) >= sample_limit:
                break
            samples.append({"kind": side, "key_sha256": _key_hash(key)})
    for key in changed_keys:
        if len(samples) >= sample_limit:
            break
        source_row = source_by_key[key]
        target_row = target_by_key[key]
        columns = sorted(
            column
            for column in set(source_row) | set(target_row)
            if source_row.get(column) != target_row.get(column)
        )
        samples.append(
            {
                "kind": "changed",
                "key_sha256": _key_hash(key),
                "columns": columns,
            }
        )

    return DifferenceSummary(
        source_only=len(source_only_keys),
        target_only=len(target_only_keys),
        changed=len(changed_keys),
        samples=tuple(samples),
    )


def _timed_query(
    endpoint: QueryEndpoint,
    sql: str,
    params: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], QueryDigest]:
    started = time.perf_counter()
    rows = endpoint.query(sql, params)
    elapsed_ms = (time.perf_counter() - started) * 1000
    normalized = normalize_rows(rows)
    return normalized, QueryDigest(
        row_count=len(normalized),
        sha256=rows_sha256(normalized),
        duration_ms=round(elapsed_ms, 2),
    )


def discover_context(
    source: QueryEndpoint,
    target: QueryEndpoint,
    *,
    buyer_ids: Sequence[str] | None = None,
    end_date: date | None = None,
    days: int = 30,
    stable_lag_days: int = 1,
    top_limit: int = 10,
) -> SmokeContext:
    """Choose shared buyers and a closed historical window for exact comparison."""

    if not 1 <= days <= 90:
        raise SmokeError("days must be between 1 and 90")
    if not 0 <= stable_lag_days <= 30:
        raise SmokeError("stable_lag_days must be between 0 and 30")
    if not 1 <= top_limit <= 25:
        raise SmokeError("top_limit must be between 1 and 25")

    source_buyers = {str(row["buyer_id"]) for row in source.query(DISCOVER_BUYERS_SQL)}
    target_buyers = {str(row["buyer_id"]) for row in target.query(DISCOVER_BUYERS_SQL)}
    shared_buyers = source_buyers & target_buyers
    if buyer_ids:
        requested = {str(value) for value in buyer_ids}
        missing = requested - shared_buyers
        if missing:
            raise SmokeError(
                f"{len(missing)} requested buyer(s) are not present in both databases."
            )
        selected_buyers = tuple(sorted(requested))
    else:
        selected_buyers = tuple(sorted(shared_buyers))
    if not selected_buyers:
        raise SmokeError("No shared buyer seats were found.")

    latest_values: list[date] = []
    for endpoint in (source, target):
        rows = endpoint.query(DISCOVER_LATEST_SPEND_DATE_SQL)
        latest = rows[0].get("latest_metric_date") if rows else None
        if isinstance(latest, datetime):
            latest = latest.date()
        elif isinstance(latest, str):
            latest = date.fromisoformat(latest)
        if not isinstance(latest, date):
            raise SmokeError(f"{endpoint.label} has no canonical spend date.")
        latest_values.append(latest)

    selected_end = end_date or (min(latest_values) - timedelta(days=stable_lag_days))
    selected_start = selected_end - timedelta(days=days - 1)
    return SmokeContext(
        buyer_ids=selected_buyers,
        start_date=selected_start,
        end_date=selected_end,
        top_limit=top_limit,
    )


def run_contracts(
    source: QueryEndpoint,
    target: QueryEndpoint,
    context: SmokeContext,
    *,
    contracts: Sequence[ToolContract] = TOOL_CONTRACTS,
) -> list[ContractResult]:
    """Run every contract against both endpoints and compare exact normalized rows."""

    params = context.query_params()
    results: list[ContractResult] = []
    for contract in contracts:
        source_rows, source_digest = _timed_query(source, contract.sql, params)
        target_rows, target_digest = _timed_query(target, contract.sql, params)
        differences = compare_rows(
            source_rows,
            target_rows,
            key_columns=contract.key_columns,
        )
        passed = (
            source_digest.sha256 == target_digest.sha256
            and differences.source_only == 0
            and differences.target_only == 0
            and differences.changed == 0
        )
        results.append(
            ContractResult(
                contract=contract.name,
                description=contract.description,
                passed=passed,
                source=source_digest,
                target=target_digest,
                differences=differences,
            )
        )
    return results


class PsycopgEndpoint:
    """Read-only psycopg endpoint with a hard statement timeout."""

    def __init__(
        self,
        *,
        label: str,
        dsn: str,
        host: str | None = None,
        port: int | None = None,
        dbname: str | None = None,
        statement_timeout_ms: int = 60_000,
        connect_timeout_seconds: int = 15,
    ) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except (
            ImportError
        ) as exc:  # pragma: no cover - exercised only outside project venv
            raise SmokeError(
                "psycopg is required; run with the project virtual environment."
            ) from exc

        self.label = label
        kwargs: dict[str, Any] = {
            "connect_timeout": connect_timeout_seconds,
            "application_name": "catscan_mcp_db_smoke",
            "options": (
                "-c default_transaction_read_only=on "
                f"-c statement_timeout={statement_timeout_ms}"
            ),
            "row_factory": dict_row,
        }
        if host:
            kwargs["host"] = host
        if port:
            kwargs["port"] = port
        if dbname:
            kwargs["dbname"] = dbname
        try:
            self._connection = psycopg.connect(dsn, **kwargs)
        except Exception as exc:
            raise SmokeError(
                f"{label} connection failed ({type(exc).__name__}): {exc}"
            ) from exc
        read_only = self.query("SHOW transaction_read_only")
        if not read_only or read_only[0].get("transaction_read_only") != "on":
            self.close()
            raise SmokeError(f"{label} connection is not read-only.")

    def query(
        self,
        sql: str,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            with self._connection.transaction():
                with self._connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    if cursor.description is None:
                        raise SmokeError(f"{self.label} contract did not return rows.")
                    return [dict(row) for row in cursor.fetchall()]
        except SmokeError:
            raise
        except Exception as exc:
            raise SmokeError(
                f"{self.label} query failed ({type(exc).__name__}): {exc}"
            ) from exc

    def close(self) -> None:
        self._connection.close()


def build_report(
    *,
    source_label: str,
    target_label: str,
    context: SmokeContext,
    results: Sequence[ContractResult],
) -> dict[str, Any]:
    """Build a credential-free JSON report suitable for migration evidence."""

    return {
        "report_version": "catscan-mcp-db-smoke.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": source_label,
        "target": target_label,
        "request": {
            "buyer_count": len(context.buyer_ids),
            "start_date": context.start_date.isoformat(),
            "end_date": context.end_date.isoformat(),
            "days": (context.end_date - context.start_date).days + 1,
            "top_limit": context.top_limit,
        },
        "summary": {
            "contracts": len(results),
            "passed": sum(result.passed for result in results),
            "failed": sum(not result.passed for result in results),
        },
        "results": [asdict(result) for result in results],
    }


def _dsn_from_env(env_name: str) -> str:
    dsn = os.getenv(env_name, "").strip()
    if not dsn:
        raise SmokeError(f"Required DSN environment variable is empty: {env_name}")
    return dsn


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare future CatScan MCP media-buyer contracts across two databases."
    )
    parser.add_argument("--source-dsn-env", default="CATSCAN_SMOKE_SOURCE_DSN")
    parser.add_argument("--target-dsn-env", default="CATSCAN_SMOKE_TARGET_DSN")
    parser.add_argument("--source-label", default="source")
    parser.add_argument("--target-label", default="target")
    parser.add_argument("--source-host")
    parser.add_argument("--source-port", type=int)
    parser.add_argument("--source-dbname")
    parser.add_argument("--target-host")
    parser.add_argument("--target-port", type=int)
    parser.add_argument("--target-dbname")
    parser.add_argument("--buyer-id", action="append", dest="buyer_ids")
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--stable-lag-days", type=int, default=1)
    parser.add_argument("--top-limit", type=int, default=10)
    parser.add_argument("--statement-timeout-ms", type=int, default=60_000)
    parser.add_argument("--report-json", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    source: PsycopgEndpoint | None = None
    target: PsycopgEndpoint | None = None
    try:
        source = PsycopgEndpoint(
            label=args.source_label,
            dsn=_dsn_from_env(args.source_dsn_env),
            host=args.source_host,
            port=args.source_port,
            dbname=args.source_dbname,
            statement_timeout_ms=args.statement_timeout_ms,
        )
        target = PsycopgEndpoint(
            label=args.target_label,
            dsn=_dsn_from_env(args.target_dsn_env),
            host=args.target_host,
            port=args.target_port,
            dbname=args.target_dbname,
            statement_timeout_ms=args.statement_timeout_ms,
        )
        context = discover_context(
            source,
            target,
            buyer_ids=args.buyer_ids,
            end_date=args.end_date,
            days=args.days,
            stable_lag_days=args.stable_lag_days,
            top_limit=args.top_limit,
        )
        results = run_contracts(source, target, context)
        report = build_report(
            source_label=source.label,
            target_label=target.label,
            context=context,
            results=results,
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        print(
            f"CatScan MCP DB smoke: {len(context.buyer_ids)} shared buyers, "
            f"{context.start_date}..{context.end_date}"
        )
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            print(
                f"{status} {result.contract}: "
                f"rows {result.source.row_count}/{result.target.row_count}, "
                f"ms {result.source.duration_ms:.2f}/{result.target.duration_ms:.2f}, "
                f"sha256 {result.source.sha256[:12]}/{result.target.sha256[:12]}"
            )
            for sample in result.differences.samples:
                print(f"  difference {json.dumps(sample, sort_keys=True)}")
        print(
            f"Summary: {report['summary']['passed']}/{report['summary']['contracts']} "
            "contracts matched exactly."
        )
        return 0 if report["summary"]["failed"] == 0 else 1
    except (SmokeError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    finally:
        if source is not None:
            source.close()
        if target is not None:
            target.close()


if __name__ == "__main__":
    raise SystemExit(main())
