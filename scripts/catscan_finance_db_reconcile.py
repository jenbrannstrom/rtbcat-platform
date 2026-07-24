#!/usr/bin/env python3
"""Compare the private finance schema across two CatScan PostgreSQL databases.

This is a migration-only companion to ``catscan_mcp_db_smoke.py``. Finance
contracts must never be exposed as media-buyer MCP tools.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

try:
    from scripts.catscan_mcp_db_smoke import (
        ContractResult,
        PsycopgEndpoint,
        QueryDigest,
        QueryEndpoint,
        SmokeError,
        ToolContract,
        compare_rows,
        normalize_rows,
        rows_sha256,
    )
except ModuleNotFoundError:  # Direct execution puts scripts/ on sys.path.
    from catscan_mcp_db_smoke import (  # type: ignore[no-redef]
        ContractResult,
        PsycopgEndpoint,
        QueryDigest,
        QueryEndpoint,
        SmokeError,
        ToolContract,
        compare_rows,
        normalize_rows,
        rows_sha256,
    )


FINANCE_CONTRACTS: tuple[ToolContract, ...] = (
    ToolContract(
        name="finance.schema_columns",
        description="Verify the private finance table and column contract.",
        key_columns=("table_name", "ordinal_position"),
        sql="""
            SELECT
                table_name,
                ordinal_position,
                column_name,
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'financial_viability'
            ORDER BY table_name, ordinal_position
        """,
    ),
    ToolContract(
        name="finance.table_rows",
        description="Verify exact cardinality for every private finance table.",
        key_columns=("table_name",),
        sql="""
            SELECT 'contract_terms'::text AS table_name, COUNT(*)::bigint AS rows
            FROM financial_viability.contract_terms
            UNION ALL
            SELECT 'customer_accounts', COUNT(*)::bigint
            FROM financial_viability.customer_accounts
            UNION ALL
            SELECT 'customer_payment_matches', COUNT(*)::bigint
            FROM financial_viability.customer_payment_matches
            UNION ALL
            SELECT 'daily_customer_balances', COUNT(*)::bigint
            FROM financial_viability.daily_customer_balances
            UNION ALL
            SELECT 'external_account_links', COUNT(*)::bigint
            FROM financial_viability.external_account_links
            UNION ALL
            SELECT 'google_ab_daily_spend', COUNT(*)::bigint
            FROM financial_viability.google_ab_daily_spend
            UNION ALL
            SELECT 'google_ab_daily_spend_raw', COUNT(*)::bigint
            FROM financial_viability.google_ab_daily_spend_raw
            UNION ALL
            SELECT 'google_invoice_obligations', COUNT(*)::bigint
            FROM financial_viability.google_invoice_obligations
            UNION ALL
            SELECT 'integration_runs', COUNT(*)::bigint
            FROM financial_viability.integration_runs
            UNION ALL
            SELECT 'mercury_accounts', COUNT(*)::bigint
            FROM financial_viability.mercury_accounts
            UNION ALL
            SELECT 'mercury_balance_snapshots', COUNT(*)::bigint
            FROM financial_viability.mercury_balance_snapshots
            UNION ALL
            SELECT 'mercury_transactions', COUNT(*)::bigint
            FROM financial_viability.mercury_transactions
            UNION ALL
            SELECT 'sheet_sync_log', COUNT(*)::bigint
            FROM financial_viability.sheet_sync_log
            UNION ALL
            SELECT 'transfer_recommendations', COUNT(*)::bigint
            FROM financial_viability.transfer_recommendations
            ORDER BY table_name
        """,
    ),
    ToolContract(
        name="finance.canonical_spend_monthly",
        description="Verify canonical finance spend by customer, buyer, month, and status.",
        key_columns=(
            "customer_account_id",
            "buyer_account_id",
            "metric_month",
            "currency",
            "source_status",
        ),
        sql="""
            SELECT
                customer_account_id,
                buyer_account_id,
                date_trunc('month', metric_date)::date AS metric_month,
                currency,
                source_status,
                COUNT(*)::bigint AS source_days,
                SUM(spend_micros)::bigint AS spend_micros,
                MIN(metric_date) AS first_metric_date,
                MAX(metric_date) AS latest_metric_date
            FROM financial_viability.google_ab_daily_spend
            GROUP BY
                customer_account_id,
                buyer_account_id,
                date_trunc('month', metric_date),
                currency,
                source_status
            ORDER BY
                customer_account_id,
                buyer_account_id,
                metric_month,
                currency,
                source_status
        """,
    ),
    ToolContract(
        name="finance.raw_spend_monthly",
        description="Verify raw finance spend lineage without exposing source payloads.",
        key_columns=(
            "buyer_account_id",
            "metric_month",
            "currency",
            "source_report_type",
        ),
        sql="""
            SELECT
                buyer_account_id,
                date_trunc('month', metric_date)::date AS metric_month,
                currency,
                source_report_type,
                COUNT(*)::bigint AS source_rows,
                COUNT(DISTINCT source_row_fingerprint)::bigint AS source_fingerprints,
                SUM(spend_micros)::bigint AS spend_micros,
                SUM(COALESCE(impressions, 0))::bigint AS impressions,
                SUM(COALESCE(clicks, 0))::bigint AS clicks,
                MIN(metric_date) AS first_metric_date,
                MAX(metric_date) AS latest_metric_date
            FROM financial_viability.google_ab_daily_spend_raw
            GROUP BY
                buyer_account_id,
                date_trunc('month', metric_date),
                currency,
                source_report_type
            ORDER BY
                buyer_account_id,
                metric_month,
                currency,
                source_report_type
        """,
    ),
    ToolContract(
        name="finance.customer_balances_monthly",
        description="Verify monthly customer ledger totals.",
        key_columns=("customer_account_id", "balance_month", "currency"),
        sql="""
            SELECT
                customer_account_id,
                date_trunc('month', balance_date)::date AS balance_month,
                currency,
                COUNT(*)::bigint AS balance_days,
                SUM(opening_balance_micros)::bigint AS opening_balance_micros,
                SUM(deposits_micros)::bigint AS deposits_micros,
                SUM(ad_spend_micros)::bigint AS ad_spend_micros,
                SUM(fee_charge_micros)::bigint AS fee_charge_micros,
                SUM(google_invoice_paid_micros)::bigint AS google_invoice_paid_micros,
                SUM(adjustments_micros)::bigint AS adjustments_micros,
                SUM(closing_balance_micros)::bigint AS closing_balance_micros,
                SUM(top_up_required_micros)::bigint AS top_up_required_micros
            FROM financial_viability.daily_customer_balances
            GROUP BY
                customer_account_id,
                date_trunc('month', balance_date),
                currency
            ORDER BY customer_account_id, balance_month, currency
        """,
    ),
    ToolContract(
        name="finance.mercury_transactions_monthly",
        description="Verify monthly bank-transaction aggregates.",
        key_columns=(
            "mercury_account_id",
            "posted_month",
            "currency",
            "direction",
            "status",
        ),
        sql="""
            SELECT
                mercury_account_id,
                date_trunc('month', posted_at)::date AS posted_month,
                currency,
                direction,
                status,
                COUNT(*)::bigint AS transactions,
                SUM(amount_micros)::bigint AS amount_micros
            FROM financial_viability.mercury_transactions
            GROUP BY
                mercury_account_id,
                date_trunc('month', posted_at),
                currency,
                direction,
                status
            ORDER BY
                mercury_account_id,
                posted_month,
                currency,
                direction,
                status
        """,
    ),
    ToolContract(
        name="finance.invoice_obligations_monthly",
        description="Verify monthly Google invoice obligations.",
        key_columns=("buyer_account_id", "invoice_month", "currency", "payment_status"),
        sql="""
            SELECT
                buyer_account_id,
                date_trunc('month', invoice_period_start)::date AS invoice_month,
                currency,
                payment_status,
                COUNT(*)::bigint AS obligations,
                SUM(amount_due_micros)::bigint AS amount_due_micros,
                SUM(amount_paid_micros)::bigint AS amount_paid_micros,
                MIN(invoice_period_start) AS first_period_start,
                MAX(invoice_period_end) AS latest_period_end
            FROM financial_viability.google_invoice_obligations
            GROUP BY
                buyer_account_id,
                date_trunc('month', invoice_period_start),
                currency,
                payment_status
            ORDER BY buyer_account_id, invoice_month, currency, payment_status
        """,
    ),
)


def _timed_query(
    endpoint: QueryEndpoint,
    sql: str,
) -> tuple[list[dict[str, Any]], QueryDigest]:
    started = time.perf_counter()
    rows = normalize_rows(endpoint.query(sql))
    return rows, QueryDigest(
        row_count=len(rows),
        sha256=rows_sha256(rows),
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )


def run_finance_contracts(
    source: QueryEndpoint,
    target: QueryEndpoint,
    *,
    contracts: Sequence[ToolContract] = FINANCE_CONTRACTS,
) -> list[ContractResult]:
    """Run private finance reconciliation contracts against both databases."""

    results: list[ContractResult] = []
    for contract in contracts:
        source_rows, source_digest = _timed_query(source, contract.sql)
        target_rows, target_digest = _timed_query(target, contract.sql)
        differences = compare_rows(
            source_rows,
            target_rows,
            key_columns=contract.key_columns,
        )
        results.append(
            ContractResult(
                contract=contract.name,
                description=contract.description,
                passed=(
                    source_digest.sha256 == target_digest.sha256
                    and differences.source_only == 0
                    and differences.target_only == 0
                    and differences.changed == 0
                ),
                source=source_digest,
                target=target_digest,
                differences=differences,
            )
        )
    return results


def build_report(
    *,
    source_label: str,
    target_label: str,
    results: Sequence[ContractResult],
) -> dict[str, Any]:
    return {
        "report_version": "catscan-finance-db-reconcile.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": source_label,
        "target": target_label,
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
        description="Compare the private CatScan finance schema across two databases."
    )
    parser.add_argument("--source-dsn-env", default="CATSCAN_FINANCE_SOURCE_DSN")
    parser.add_argument("--target-dsn-env", default="CATSCAN_FINANCE_TARGET_DSN")
    parser.add_argument("--source-label", default="source-finance")
    parser.add_argument("--target-label", default="target-finance")
    parser.add_argument("--source-host")
    parser.add_argument("--source-port", type=int)
    parser.add_argument("--source-dbname")
    parser.add_argument("--target-host")
    parser.add_argument("--target-port", type=int)
    parser.add_argument("--target-dbname")
    parser.add_argument("--statement-timeout-ms", type=int, default=60_000)
    parser.add_argument("--report-json", type=Path)
    return parser.parse_args(argv)


def _endpoint(
    *,
    label: str,
    dsn_env: str,
    host: str | None,
    port: int | None,
    dbname: str | None,
    statement_timeout_ms: int,
) -> PsycopgEndpoint:
    return PsycopgEndpoint(
        label=label,
        dsn=_dsn_from_env(dsn_env),
        host=host,
        port=port,
        dbname=dbname,
        statement_timeout_ms=statement_timeout_ms,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    source: PsycopgEndpoint | None = None
    target: PsycopgEndpoint | None = None
    try:
        source = _endpoint(
            label=args.source_label,
            dsn_env=args.source_dsn_env,
            host=args.source_host,
            port=args.source_port,
            dbname=args.source_dbname,
            statement_timeout_ms=args.statement_timeout_ms,
        )
        target = _endpoint(
            label=args.target_label,
            dsn_env=args.target_dsn_env,
            host=args.target_host,
            port=args.target_port,
            dbname=args.target_dbname,
            statement_timeout_ms=args.statement_timeout_ms,
        )
        results = run_finance_contracts(source, target)
        report = build_report(
            source_label=source.label,
            target_label=target.label,
            results=results,
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        print("CatScan private finance DB reconciliation")
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
            "finance contracts matched exactly."
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
