from __future__ import annotations

from scripts.catscan_finance_db_reconcile import (
    FINANCE_CONTRACTS,
    run_finance_contracts,
)


class _FakeEndpoint:
    def __init__(self, label: str, rows_by_sql: dict[str, list[dict]]) -> None:
        self.label = label
        self.rows_by_sql = rows_by_sql

    def query(self, sql: str, params=None):
        assert params is None
        return self.rows_by_sql[sql]

    def close(self) -> None:
        pass


def test_finance_contracts_are_private_read_only_reconciliation_queries() -> None:
    expected = {
        "finance.schema_columns",
        "finance.table_rows",
        "finance.canonical_spend_monthly",
        "finance.raw_spend_monthly",
        "finance.customer_balances_monthly",
        "finance.mercury_transactions_monthly",
        "finance.invoice_obligations_monthly",
    }

    assert {contract.name for contract in FINANCE_CONTRACTS} == expected
    for contract in FINANCE_CONTRACTS:
        normalized_sql = " ".join(contract.sql.lower().split())
        assert contract.name.startswith("finance.")
        assert "financial_viability" in normalized_sql
        assert not any(
            statement in normalized_sql
            for statement in (" insert ", " update ", " delete ", " alter ", " drop ")
        )


def test_finance_runner_compares_all_contracts() -> None:
    rows_by_sql = {
        contract.sql: [
            {
                column: f"value-{index}"
                for index, column in enumerate(contract.key_columns)
            }
        ]
        for contract in FINANCE_CONTRACTS
    }
    source = _FakeEndpoint("source", rows_by_sql)
    target = _FakeEndpoint("target", rows_by_sql)

    results = run_finance_contracts(source, target)

    assert len(results) == len(FINANCE_CONTRACTS)
    assert all(result.passed for result in results)
