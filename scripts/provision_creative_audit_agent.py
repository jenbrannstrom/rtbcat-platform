#!/usr/bin/env python3
"""Provision least-privilege access for creative language/country audit agents.

The provisioned Postgres role reads buyer-scoped agent_read views by default.
Refresh and scan actions should go through the app API, using the provisioned
app user.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install psycopg[binary]", file=sys.stderr)
    sys.exit(1)

try:
    import bcrypt
except ImportError:
    print("ERROR: bcrypt not installed. Run: pip install bcrypt", file=sys.stderr)
    sys.exit(1)


_PREHASHED_BCRYPT_PREFIX = "$catscan-sha256$"
_AGENT_TOKEN_PREFIX = "cat_agent_"


def _prehash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def hash_password(password: str) -> str:
    """Hash app-user passwords with the same format as api.auth_password."""
    hashed = bcrypt.hashpw(_prehash_password(password).encode(), bcrypt.gensalt()).decode()
    return f"{_PREHASHED_BCRYPT_PREFIX}{hashed}"


def _get_dsn() -> str:
    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("POSTGRES_DSN or DATABASE_URL must be set.")
    return dsn


def _generate_secret() -> str:
    return secrets.token_urlsafe(32)


def _generate_agent_token() -> str:
    return f"{_AGENT_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def _hash_agent_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_buyer_ids(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        token = str(value or "").strip()
        if not token or token in seen:
            continue
        normalized.append(token)
        seen.add(token)
    return normalized


def _schema_exists(conn: psycopg.Connection, schema_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
        (schema_name,),
    ).fetchone() is not None


def _table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    return conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,),
    ).fetchone() is not None


def _ensure_agent_read_schema(conn: psycopg.Connection) -> None:
    if not _schema_exists(conn, "agent_read") or not _schema_exists(conn, "agent_private"):
        raise SystemExit(
            "agent_read schema is not installed. Run Postgres migrations first "
            "(storage/postgres_migrations/066_agent_read_views.sql)."
        )


def _ensure_agent_tokens_table(conn: psycopg.Connection) -> None:
    if not _table_exists(conn, "agent_api_tokens"):
        raise SystemExit(
            "agent_api_tokens is not installed. Run Postgres migrations first "
            "(storage/postgres_migrations/068_agent_api_tokens.sql)."
        )


def _ensure_db_role(
    conn: psycopg.Connection,
    role_name: str,
    password: str,
    *,
    grant_raw_public_read: bool,
) -> None:
    exists = conn.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = %s",
        (role_name,),
    ).fetchone()

    if exists:
        conn.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role_name),
                sql.Literal(password),
            )
        )
    else:
        conn.execute(
            sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role_name),
                sql.Literal(password),
            )
        )

    current_db = conn.execute("SELECT current_database() AS name").fetchone()["name"]
    conn.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(current_db),
            sql.Identifier(role_name),
        )
    )
    conn.execute(
        sql.SQL("GRANT USAGE ON SCHEMA agent_read TO {}").format(
            sql.Identifier(role_name)
        )
    )
    conn.execute(
        sql.SQL("GRANT USAGE ON SCHEMA agent_private TO {}").format(
            sql.Identifier(role_name)
        )
    )
    conn.execute(
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA agent_read TO {}").format(
            sql.Identifier(role_name)
        )
    )
    conn.execute(
        sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA agent_read GRANT SELECT ON TABLES TO {}").format(
            sql.Identifier(role_name)
        )
    )

    if grant_raw_public_read:
        conn.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role_name))
        )
        conn.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
                sql.Identifier(role_name)
            )
        )
        conn.execute(
            sql.SQL("GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                sql.Identifier(role_name)
            )
        )
        conn.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}").format(
                sql.Identifier(role_name)
            )
        )
        conn.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO {}").format(
                sql.Identifier(role_name)
            )
        )

    conn.execute(
        sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(
            sql.Identifier(role_name)
        )
    )
    conn.execute(
        sql.SQL("ALTER ROLE {} SET statement_timeout = '5min'").format(
            sql.Identifier(role_name)
        )
    )


def _ensure_app_user(
    conn: psycopg.Connection,
    *,
    email: str,
    display_name: str,
    password: str,
) -> str:
    row = conn.execute(
        "SELECT id, role FROM users WHERE lower(email) = lower(%s)",
        (email,),
    ).fetchone()

    if row:
        user_id = row["id"]
        if row["role"] != "read":
            print(
                f"Existing app user {email} has role={row['role']}; leaving role unchanged.",
                file=sys.stderr,
            )
    else:
        user_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO users (
                id, email, display_name, role, created_at, default_language
            )
            VALUES (%s, %s, %s, 'read', NOW(), 'en')
            """,
            (user_id, email.lower().strip(), display_name),
        )

    conn.execute(
        """
        INSERT INTO user_passwords (user_id, password_hash, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            updated_at = NOW()
        """,
        (user_id, hash_password(password)),
    )
    return user_id


def _active_buyer_ids(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT buyer_id
        FROM buyer_seats
        WHERE COALESCE(active, TRUE) = TRUE
        ORDER BY buyer_id
        """
    ).fetchall()
    return [row["buyer_id"] for row in rows]


def _grant_buyer_read(conn: psycopg.Connection, *, user_id: str, buyer_ids: list[str]) -> None:
    for buyer_id in buyer_ids:
        conn.execute(
            """
            INSERT INTO user_buyer_seat_permissions (
                id, user_id, buyer_id, access_level, granted_by, granted_at
            )
            VALUES (%s, %s, %s, 'read', 'provision_creative_audit_agent', NOW())
            ON CONFLICT (user_id, buyer_id) DO UPDATE SET
                access_level = CASE
                    WHEN user_buyer_seat_permissions.access_level = 'admin' THEN 'admin'
                    ELSE 'read'
                END,
                granted_by = EXCLUDED.granted_by,
                granted_at = NOW()
            """,
            (str(uuid.uuid4()), user_id, buyer_id),
        )


def _grant_db_buyer_read(
    conn: psycopg.Connection,
    *,
    database_role: str,
    buyer_ids: list[str],
) -> None:
    for buyer_id in buyer_ids:
        conn.execute(
            """
            INSERT INTO agent_private.buyer_role_grants (
                database_role, buyer_id, granted_by, granted_at
            )
            VALUES (%s, %s, 'provision_creative_audit_agent', NOW())
            ON CONFLICT (database_role, buyer_id) DO UPDATE SET
                granted_by = EXCLUDED.granted_by,
                granted_at = NOW()
            """,
            (database_role, buyer_id),
        )


def _create_agent_api_token(
    conn: psycopg.Connection,
    *,
    user_id: str,
    name: str,
    buyer_id: str | None,
    expires_in_days: int,
) -> str:
    token = _generate_agent_token()
    expires_at = datetime.now(UTC) + timedelta(days=max(1, min(expires_in_days, 366)))
    conn.execute(
        """
        INSERT INTO agent_api_tokens (
            id, name, token_hash, token_prefix, user_id, buyer_id,
            scopes, expires_at, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'agent:stats:read', %s, %s)
        """,
        (
            str(uuid.uuid4()),
            name,
            _hash_agent_token(token),
            token[:22],
            user_id,
            buyer_id,
            expires_at,
            user_id,
        ),
    )
    return token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision read-only DB and app access for creative audit agents."
    )
    parser.add_argument("--db-user", default="catscan_creative_audit_agent")
    parser.add_argument(
        "--db-password",
        default=os.getenv("CATSCAN_CREATIVE_AUDIT_DB_PASSWORD"),
        help="Defaults to CATSCAN_CREATIVE_AUDIT_DB_PASSWORD or a generated password.",
    )
    parser.add_argument("--skip-db-role", action="store_true")
    parser.add_argument(
        "--db-buyer-id",
        action="append",
        default=[],
        help=(
            "Buyer seat ID visible to the direct DB role through agent_read views. "
            "Defaults to --buyer-id values when omitted."
        ),
    )
    parser.add_argument(
        "--db-all-buyers",
        action="store_true",
        help="Grant the direct DB role all-buyer visibility through agent_read views.",
    )
    parser.add_argument(
        "--grant-raw-public-read",
        action="store_true",
        help=(
            "Also grant database-wide SELECT on public tables. Use only for trusted "
            "internal jobs; buyer isolation is not enforced on raw public tables."
        ),
    )
    parser.add_argument("--app-email", default="creative-audit-agent@localhost")
    parser.add_argument("--app-display-name", default="Creative Audit Agent")
    parser.add_argument(
        "--app-password",
        default=os.getenv("CATSCAN_CREATIVE_AUDIT_APP_PASSWORD"),
        help="Defaults to CATSCAN_CREATIVE_AUDIT_APP_PASSWORD or a generated password.",
    )
    parser.add_argument("--skip-app-user", action="store_true")
    parser.add_argument(
        "--buyer-id",
        action="append",
        default=[],
        help="Buyer seat ID to grant read access. Repeat for multiple seats.",
    )
    parser.add_argument(
        "--all-active-buyers",
        action="store_true",
        help="Grant app read access to all active buyer seats.",
    )
    parser.add_argument(
        "--create-api-token",
        action="store_true",
        help="Create a hashed bearer token for /api/agent/v1 stats access.",
    )
    parser.add_argument(
        "--api-token-name",
        default="Creative Audit Agent API",
        help="Display name for --create-api-token.",
    )
    parser.add_argument(
        "--api-token-buyer-id",
        help=(
            "Optional hard buyer scope for --create-api-token. Defaults to the "
            "single app buyer grant when exactly one buyer is granted."
        ),
    )
    parser.add_argument(
        "--api-token-expires-days",
        type=int,
        default=90,
        help="Token lifetime in days for --create-api-token (1..366, default 90).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_password = args.db_password or _generate_secret()
    app_password = args.app_password or _generate_secret()
    api_token: str | None = None

    with psycopg.connect(_get_dsn(), row_factory=dict_row) as conn:
        if not args.skip_db_role:
            _ensure_agent_read_schema(conn)
        if args.create_api_token:
            _ensure_agent_tokens_table(conn)
            if args.skip_app_user:
                raise SystemExit("--create-api-token requires an app user; remove --skip-app-user.")

        active_buyer_ids = _active_buyer_ids(conn) if args.all_active_buyers else []
        app_buyer_ids = _normalize_buyer_ids([*args.buyer_id, *active_buyer_ids])
        db_buyer_ids = _normalize_buyer_ids(args.db_buyer_id or args.buyer_id)
        if args.all_active_buyers:
            db_buyer_ids = _normalize_buyer_ids([*db_buyer_ids, *active_buyer_ids])
        if args.db_all_buyers:
            db_buyer_ids = ["*"]

        if not args.skip_db_role:
            _ensure_db_role(
                conn,
                args.db_user,
                db_password,
                grant_raw_public_read=args.grant_raw_public_read,
            )
            if db_buyer_ids:
                _grant_db_buyer_read(
                    conn,
                    database_role=args.db_user,
                    buyer_ids=db_buyer_ids,
                )

        app_user_id: str | None = None
        if not args.skip_app_user:
            app_user_id = _ensure_app_user(
                conn,
                email=args.app_email,
                display_name=args.app_display_name,
                password=app_password,
            )
            if app_buyer_ids:
                _grant_buyer_read(conn, user_id=app_user_id, buyer_ids=app_buyer_ids)
            if args.create_api_token:
                hard_scope_buyer_id = args.api_token_buyer_id
                if not hard_scope_buyer_id and len(app_buyer_ids) == 1:
                    hard_scope_buyer_id = app_buyer_ids[0]
                if not hard_scope_buyer_id:
                    raise SystemExit(
                        "--create-api-token requires a buyer hard-scope. Provide exactly one "
                        "--buyer-id or pass --api-token-buyer-id."
                    )
                if hard_scope_buyer_id and hard_scope_buyer_id not in app_buyer_ids:
                    raise SystemExit(
                        "--api-token-buyer-id must also be granted to the app user via --buyer-id "
                        "or --all-active-buyers."
                    )
                api_token = _create_agent_api_token(
                    conn,
                    user_id=app_user_id,
                    name=args.api_token_name,
                    buyer_id=hard_scope_buyer_id,
                    expires_in_days=args.api_token_expires_days,
                )

        conn.commit()

    if not args.skip_db_role:
        print(f"DB user: {args.db_user}")
        print(f"DB password: {db_password}")
        print(f"DB agent_read buyer grants: {len(db_buyer_ids)}")
        if args.grant_raw_public_read:
            print("WARNING: raw public table SELECT was granted; this is not buyer isolated.")
        if not db_buyer_ids:
            print(
                "WARNING: DB role has no agent_read buyer grants; grant --db-buyer-id, "
                "--buyer-id, --all-active-buyers, or --db-all-buyers.",
                file=sys.stderr,
            )
    if not args.skip_app_user:
        print(f"App user: {args.app_email}")
        print(f"App password: {app_password}")
        print(f"App buyer read grants: {len(app_buyer_ids)}")
        if not app_buyer_ids:
            print(
                "WARNING: app user has no buyer seat grants; grant --buyer-id or rerun with --all-active-buyers.",
                file=sys.stderr,
            )
    if api_token:
        print(f"Agent API token: {api_token}")
        print("Agent API token scope: agent:stats:read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
