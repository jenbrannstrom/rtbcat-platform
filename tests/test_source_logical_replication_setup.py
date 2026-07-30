from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from psycopg import sql


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "hetzner"
    / "setup_source_logical_replication.py"
)
SPEC = spec_from_file_location("setup_source_logical_replication", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fixed_source_object_contract() -> None:
    assert MODULE.EXPECTED_TABLE_COUNT == 98
    assert MODULE.EXPECTED_SCHEMAS == ("financial_viability", "public")
    assert MODULE.ROLE_NAME == "rtbcat_migration_repl"
    assert MODULE.PUBLICATION_NAME == "rtbcat_migration_pub"
    assert MODULE.CONFIRMATION == "CREATE_SOURCE_REPLICATION"


def test_qualified_identifiers_quote_every_name() -> None:
    tables = [
        {"schema_name": "public", "table_name": "normal"},
        {"schema_name": "financial_viability", "table_name": 'quote"table'},
    ]

    rendered = MODULE._qualified_identifiers(tables).as_string(None)

    assert rendered == (
        '"public"."normal", '
        '"financial_viability"."quote""table"'
    )


def test_apply_requires_confirmation_and_password_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://unused")
    monkeypatch.setattr(
        "sys.argv",
        ["setup_source_logical_replication.py", "--apply"],
    )

    with pytest.raises(SystemExit, match="--confirm must equal"):
        MODULE.main()


def test_password_is_rejected_before_database_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://unused")
    monkeypatch.setattr(
        "sys.argv",
        [
            "setup_source_logical_replication.py",
            "--apply",
            "--confirm",
            MODULE.CONFIRMATION,
            "--password-stdin",
        ],
    )
    monkeypatch.setattr("sys.stdin.read", lambda: "too-short")

    with pytest.raises(SystemExit, match="at least 32 characters"):
        MODULE.main()


def test_publication_list_is_explicit_not_all_tables() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "FOR ALL TABLES" not in source
    assert "CREATE PUBLICATION {} FOR TABLE {}" in source
    assert "replication slot" in source.lower()
    assert isinstance(MODULE._qualified_identifiers([]), sql.Composed)


def test_finance_owner_comes_from_the_operator_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The private role name must be supplied at runtime, never hardcoded.

    This repository is public, so the assertion is on the mechanism rather than
    on the role name itself.
    """
    monkeypatch.setenv(MODULE.FINANCE_OWNER_ENV, "role-from-environment")

    assert MODULE._finance_owner() == "role-from-environment"


def test_finance_owner_refuses_to_guess_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(MODULE.FINANCE_OWNER_ENV, raising=False)

    with pytest.raises(SystemExit, match=MODULE.FINANCE_OWNER_ENV):
        MODULE._finance_owner()

    monkeypatch.setenv(MODULE.FINANCE_OWNER_ENV, "   ")

    with pytest.raises(SystemExit, match=MODULE.FINANCE_OWNER_ENV):
        MODULE._finance_owner()


class _RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: object) -> None:
        if isinstance(statement, str):
            self.statements.append(statement)
        else:
            self.statements.append(statement.as_string(None))


def _apply_statements(
    monkeypatch: pytest.MonkeyPatch,
    *,
    finance_membership_exists: bool,
) -> list[str]:
    monkeypatch.setenv(MODULE.FINANCE_OWNER_ENV, "role-from-environment")
    connection = _RecordingConnection()
    MODULE._apply(
        connection,
        password="a" * 32,
        preflight={
            "current": {
                "current_user": "operator",
                "database_name": "source_database",
                "finance_membership_exists": finance_membership_exists,
            },
            "tables": [],
        },
    )
    return connection.statements


def test_apply_preserves_preexisting_finance_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements = _apply_statements(
        monkeypatch,
        finance_membership_exists=True,
    )

    assert 'GRANT "role-from-environment" TO "operator"' not in statements
    assert 'REVOKE "role-from-environment" FROM "operator"' not in statements


def test_apply_revokes_only_finance_membership_it_created(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements = _apply_statements(
        monkeypatch,
        finance_membership_exists=False,
    )

    assert 'GRANT "role-from-environment" TO "operator"' in statements
    assert 'REVOKE "role-from-environment" FROM "operator"' in statements
