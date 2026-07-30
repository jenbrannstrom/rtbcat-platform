#!/usr/bin/env python3
"""Create the bounded Cloud SQL source objects for the Hetzner migration.

This command deliberately does not create a replication slot or subscription.
An unattached slot retains WAL indefinitely, so the subscriber must create the
slot only when it is ready to consume it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


EXPECTED_TABLE_COUNT = 98
EXPECTED_SCHEMAS = ("financial_viability", "public")
FINANCE_OWNER_ENV = "RTBCAT_FINANCE_OWNER_ROLE"
ROLE_NAME = "rtbcat_migration_repl"
PUBLICATION_NAME = "rtbcat_migration_pub"
CONFIRMATION = "CREATE_SOURCE_REPLICATION"


def _finance_owner() -> str:
    """Resolve the financial_viability schema owner role at runtime.

    The role name identifies a private finance controller, so it stays out of
    this public repository and is supplied from the root-only operator
    environment instead.
    """
    owner = os.environ.get(FINANCE_OWNER_ENV, "").strip()
    if not owner:
        raise SystemExit(
            f"{FINANCE_OWNER_ENV} must name the financial_viability owner role."
        )
    return owner


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn-env",
        default="POSTGRES_DSN",
        help="Environment variable holding the source PostgreSQL DSN.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create the role and publication. The default is read-only preflight.",
    )
    parser.add_argument(
        "--confirm",
        help=f"Required with --apply; must equal {CONFIRMATION}.",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the new replication-role password from stdin.",
    )
    return parser


def _qualified_identifiers(tables: Sequence[dict[str, Any]]) -> sql.Composed:
    return sql.SQL(", ").join(
        sql.SQL("{}.{}").format(
            sql.Identifier(str(table["schema_name"])),
            sql.Identifier(str(table["table_name"])),
        )
        for table in tables
    )


def _fetch_preflight(conn: psycopg.Connection) -> dict[str, Any]:
    finance_owner = _finance_owner()
    current = conn.execute(
        """
        SELECT
            current_user AS current_user,
            current_database() AS database_name,
            current_setting('wal_level') AS wal_level,
            current_setting('max_replication_slots')::integer AS max_slots,
            (SELECT count(*) FROM pg_replication_slots) AS existing_slots,
            (SELECT count(*) FROM pg_publication) AS existing_publications,
            (SELECT count(*) FROM pg_roles WHERE rolname = %s) AS role_exists,
            (
                SELECT count(*)
                FROM pg_publication
                WHERE pubname = %s
            ) AS publication_exists,
            pg_has_role(current_user, %s, 'MEMBER') AS finance_membership_exists
        """,
        (ROLE_NAME, PUBLICATION_NAME, finance_owner),
    ).fetchone()
    assert current is not None

    tables = conn.execute(
        """
        SELECT
            n.nspname AS schema_name,
            c.relname AS table_name,
            owner.rolname AS owner_name,
            c.relrowsecurity AS row_security,
            EXISTS (
                SELECT 1
                FROM pg_index i
                WHERE i.indrelid = c.oid
                  AND i.indisprimary
            ) AS has_primary_key
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_roles owner ON owner.oid = c.relowner
        WHERE c.relkind = 'r'
          AND n.nspname = ANY(%s)
        ORDER BY n.nspname, c.relname
        """,
        (list(EXPECTED_SCHEMAS),),
    ).fetchall()

    private_tables = conn.execute(
        """
        SELECT count(*) AS table_count
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname = 'agent_private'
        """
    ).fetchone()
    assert private_tables is not None

    owner_counts: dict[str, int] = {}
    for table in tables:
        key = f"{table['schema_name']}:{table['owner_name']}"
        owner_counts[key] = owner_counts.get(key, 0) + 1

    failures: list[str] = []
    if current["wal_level"] != "logical":
        failures.append("wal_level is not logical")
    if int(current["max_slots"]) < 1:
        failures.append("max_replication_slots is less than one")
    if int(current["existing_slots"]) != 0:
        failures.append("a replication slot already exists")
    if int(current["role_exists"]) != 0:
        failures.append(f"role {ROLE_NAME} already exists")
    if int(current["publication_exists"]) != 0:
        failures.append(f"publication {PUBLICATION_NAME} already exists")
    if len(tables) != EXPECTED_TABLE_COUNT:
        failures.append(
            f"expected {EXPECTED_TABLE_COUNT} tables, found {len(tables)}"
        )
    if any(bool(table["row_security"]) for table in tables):
        failures.append("one or more publication tables use row-level security")
    if any(not bool(table["has_primary_key"]) for table in tables):
        failures.append("one or more publication tables lack a primary key")
    if int(private_tables["table_count"]) != 1:
        failures.append("expected exactly one excluded agent_private table")
    expected_owners = {
        f"public:{current['current_user']}": 84,
        f"financial_viability:{finance_owner}": 14,
    }
    if owner_counts != expected_owners:
        failures.append(
            f"table ownership differs: expected {expected_owners}, found {owner_counts}"
        )

    return {
        "current": dict(current),
        "tables": [dict(table) for table in tables],
        "private_table_count": int(private_tables["table_count"]),
        "owner_counts": owner_counts,
        "failures": failures,
    }


def _apply(
    conn: psycopg.Connection,
    *,
    password: str,
    preflight: dict[str, Any],
) -> None:
    current_user = str(preflight["current"]["current_user"])
    database_name = str(preflight["current"]["database_name"])
    table_list = _qualified_identifiers(preflight["tables"])
    finance_owner = _finance_owner()
    finance_membership_preexisting = bool(
        preflight["current"]["finance_membership_exists"]
    )

    conn.execute("SET LOCAL lock_timeout = '5s'")
    conn.execute("SET LOCAL statement_timeout = '30s'")
    conn.execute(
        sql.SQL(
            "CREATE ROLE {} WITH LOGIN REPLICATION PASSWORD {}"
        ).format(sql.Identifier(ROLE_NAME), sql.Literal(password))
    )
    conn.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(database_name),
            sql.Identifier(ROLE_NAME),
        )
    )

    # The 14 finance tables have a separate owner. Borrow membership only when
    # this invocation needs to create it; never revoke access that predated us.
    if not finance_membership_preexisting:
        conn.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(finance_owner),
                sql.Identifier(current_user),
            )
        )
    conn.execute(
        sql.SQL("GRANT USAGE ON SCHEMA {}, {} TO {}").format(
            sql.Identifier("public"),
            sql.Identifier("financial_viability"),
            sql.Identifier(ROLE_NAME),
        )
    )
    conn.execute(
        sql.SQL("GRANT SELECT ON TABLE {} TO {}").format(
            table_list,
            sql.Identifier(ROLE_NAME),
        )
    )
    conn.execute(
        sql.SQL(
            "CREATE PUBLICATION {} FOR TABLE {} "
            "WITH (publish = 'insert, update, delete, truncate')"
        ).format(
            sql.Identifier(PUBLICATION_NAME),
            table_list,
        )
    )
    if not finance_membership_preexisting:
        conn.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(finance_owner),
                sql.Identifier(current_user),
            )
        )


def _verify(
    conn: psycopg.Connection,
    *,
    finance_membership_expected: bool,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            role.rolcanlogin,
            role.rolreplication,
            role.rolsuper,
            role.rolcreatedb,
            role.rolcreaterole,
            role.rolbypassrls,
            (
                SELECT count(*)
                FROM pg_publication_tables
                WHERE pubname = %s
            ) AS publication_tables,
            (
                SELECT count(*)
                FROM pg_replication_slots
            ) AS replication_slots,
            pg_has_role(current_user, %s, 'MEMBER') AS finance_membership_remains
        FROM pg_roles role
        WHERE role.rolname = %s
        """,
        (PUBLICATION_NAME, _finance_owner(), ROLE_NAME),
    ).fetchone()
    if row is None:
        raise RuntimeError("replication role was not created")
    result = dict(row)
    expected = {
        "rolcanlogin": True,
        "rolreplication": True,
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolbypassrls": False,
        "publication_tables": EXPECTED_TABLE_COUNT,
        "replication_slots": 0,
        "finance_membership_remains": finance_membership_expected,
    }
    for key, value in expected.items():
        if result[key] != value:
            raise RuntimeError(f"postcondition failed for {key}: {result[key]!r}")
    return result


def main() -> int:
    args = _parser().parse_args()
    dsn = os.getenv(args.dsn_env, "")
    if not dsn:
        raise SystemExit(f"{args.dsn_env} is not set")

    if args.apply:
        if args.confirm != CONFIRMATION:
            raise SystemExit(f"--confirm must equal {CONFIRMATION}")
        if not args.password_stdin:
            raise SystemExit("--password-stdin is required with --apply")
        password = sys.stdin.read().strip()
        if len(password) < 32:
            raise SystemExit("replication password must be at least 32 characters")
    else:
        if args.confirm or args.password_stdin:
            raise SystemExit("--confirm/--password-stdin require --apply")
        password = ""

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        preflight = _fetch_preflight(conn)
        if preflight["failures"]:
            print(
                json.dumps(
                    {
                        "status": "refused",
                        "failures": preflight["failures"],
                        "table_count": len(preflight["tables"]),
                        "owner_counts": preflight["owner_counts"],
                    },
                    sort_keys=True,
                )
            )
            return 2

        if not args.apply:
            print(
                json.dumps(
                    {
                        "status": "preflight_accepted",
                        "database": preflight["current"]["database_name"],
                        "current_user": preflight["current"]["current_user"],
                        "table_count": len(preflight["tables"]),
                        "owner_counts": preflight["owner_counts"],
                        "excluded_private_tables": preflight["private_table_count"],
                        "slot_count": preflight["current"]["existing_slots"],
                    },
                    sort_keys=True,
                )
            )
            conn.rollback()
            return 0

        _apply(conn, password=password, preflight=preflight)
        conn.commit()

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        verified = _verify(
            conn,
            finance_membership_expected=bool(
                preflight["current"]["finance_membership_exists"]
            ),
        )
        conn.rollback()

    print(
        json.dumps(
            {
                "status": "accepted",
                "role": ROLE_NAME,
                "publication": PUBLICATION_NAME,
                **verified,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
