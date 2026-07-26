#!/usr/bin/env python3
"""Compare or apply PostgreSQL sequence state for the final frozen cutover.

The default mode is read-only. Applying target sequence values requires both
``--apply`` and the exact confirmation string ``APPLY_SEQUENCE_STATE``. Apply
mode also requires a JSON evidence path so the original target sequence state
is written before the first ``setval()``.

PostgreSQL sequence changes are not transactional. If an apply or its
verification fails, this helper therefore compensates by restoring the
pre-apply target state and verifying that restoration. Connection strings are
read only from named environment variables and are never included in reports.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable

import psycopg
from psycopg import sql


APPLY_CONFIRMATION = "APPLY_SEQUENCE_STATE"
DEFAULT_EXPECTED_COUNT = 38


@dataclass(frozen=True, order=True)
class SequenceState:
    schema: str
    name: str
    last_value: int
    is_called: bool

    @property
    def qualified_name(self) -> str:
        return ".".join(_quote_identifier(part) for part in (self.schema, self.name))


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dsn-env",
        default="SOURCE_POSTGRES_DSN",
        help="Environment variable holding the frozen source DSN",
    )
    parser.add_argument(
        "--target-dsn-env",
        default="TARGET_POSTGRES_DSN",
        help="Environment variable holding the target DSN",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=DEFAULT_EXPECTED_COUNT,
        help=f"Required sequence count (default: {DEFAULT_EXPECTED_COUNT})",
    )
    parser.add_argument("--json-out", help="Optional path for a value-only JSON report")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply frozen source sequence state to the target",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"With --apply, must equal {APPLY_CONFIRMATION}",
    )
    return parser.parse_args(argv)


def collect_sequence_states(conn: Any) -> list[SequenceState]:
    """Read every non-system sequence from one consistent transaction."""
    sequence_rows = conn.execute(
        """
        SELECT n.nspname, c.relname
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE c.relkind = 'S'
          AND n.nspname <> 'information_schema'
          AND n.nspname NOT LIKE 'pg\\_%' ESCAPE '\\'
        ORDER BY n.nspname, c.relname
        """
    ).fetchall()

    states: list[SequenceState] = []
    for schema, name in sequence_rows:
        query = sql.SQL("SELECT last_value, is_called FROM {}.{}").format(
            sql.Identifier(schema),
            sql.Identifier(name),
        )
        last_value, is_called = conn.execute(query).fetchone()
        states.append(
            SequenceState(
                schema=str(schema),
                name=str(name),
                last_value=int(last_value),
                is_called=bool(is_called),
            )
        )
    return states


def state_map(states: Iterable[SequenceState]) -> dict[tuple[str, str], SequenceState]:
    return {(state.schema, state.name): state for state in states}


def require_matching_inventory(
    source_states: list[SequenceState],
    target_states: list[SequenceState],
    expected_count: int,
) -> None:
    if expected_count < 1:
        raise ValueError("--expected-count must be at least 1")
    if len(source_states) != expected_count:
        raise RuntimeError(
            f"Source has {len(source_states)} sequences; expected {expected_count}"
        )
    if len(target_states) != expected_count:
        raise RuntimeError(
            f"Target has {len(target_states)} sequences; expected {expected_count}"
        )

    source_names = set(state_map(source_states))
    target_names = set(state_map(target_states))
    if source_names != target_names:
        missing = sorted(source_names - target_names)
        extra = sorted(target_names - source_names)
        raise RuntimeError(
            f"Sequence inventory mismatch: missing_on_target={missing}, "
            f"extra_on_target={extra}"
        )


def apply_sequence_states(conn: Any, source_states: list[SequenceState]) -> None:
    """Apply sequence values; callers must account for nontransactional setval."""
    for state in source_states:
        conn.execute(
            "SELECT pg_catalog.setval(%s::regclass, %s, %s)",
            (state.qualified_name, state.last_value, state.is_called),
        )


def require_target_update_privileges(
    conn: Any,
    target_states: list[SequenceState],
) -> None:
    """Refuse apply before setval if the target role lacks UPDATE anywhere."""
    missing: list[str] = []
    for state in target_states:
        allowed = conn.execute(
            "SELECT pg_catalog.has_sequence_privilege(%s::regclass, 'UPDATE')",
            (state.qualified_name,),
        ).fetchone()[0]
        if not bool(allowed):
            missing.append(state.qualified_name)
    if missing:
        raise RuntimeError(
            "Target role lacks UPDATE on sequences: " + ", ".join(missing)
        )


def states_equal(
    source_states: list[SequenceState],
    target_states: list[SequenceState],
) -> bool:
    return state_map(source_states) == state_map(target_states)


def _dsn_from_env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"Required DSN environment variable is empty: {name}")
    return value


def _serialize(states: list[SequenceState]) -> list[dict[str, object]]:
    return [asdict(state) for state in states]


def _write_report(path: str, report: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    output.chmod(0o600)


def _report(
    *,
    mode: str,
    status: str,
    expected_count: int,
    source_states: list[SequenceState],
    target_before: list[SequenceState],
    target_after: list[SequenceState] | None,
    applied: bool,
    apply_attempted: bool,
    recovered_target_before: bool | None = None,
    target_after_failed_apply: list[SequenceState] | None = None,
    error: str | None = None,
) -> dict[str, object]:
    report: dict[str, object] = {
        "report_version": "rtbcat-postgres-sequence-sync.v2",
        "mode": mode,
        "status": status,
        "applied": applied,
        "apply_attempted": apply_attempted,
        "expected_count": expected_count,
        "sequence_count": len(source_states),
        "exact_match": (
            target_after is not None
            and states_equal(source_states, target_after)
        ),
        "source": _serialize(source_states),
        "target_before": _serialize(target_before),
        "target_after": (
            _serialize(target_after) if target_after is not None else None
        ),
    }
    if recovered_target_before is not None:
        report["recovery"] = {
            "attempted": True,
            "recovered_target_before": recovered_target_before,
            "target_after_failed_apply": (
                _serialize(target_after_failed_apply)
                if target_after_failed_apply is not None
                else None
            ),
        }
    if error is not None:
        report["error"] = error
    return report


def restore_target_before(
    conn: Any,
    target_before: list[SequenceState],
) -> tuple[list[SequenceState], list[SequenceState]]:
    """Compensate for a failed setval apply and verify the original state."""
    conn.rollback()
    target_after_failed_apply = collect_sequence_states(conn)
    apply_sequence_states(conn, target_before)
    target_recovered = collect_sequence_states(conn)
    if not states_equal(target_before, target_recovered):
        raise RuntimeError("Target differs from its pre-apply sequence state")
    conn.commit()
    return target_after_failed_apply, target_recovered


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        print(
            f"Refusing apply: --confirm must equal {APPLY_CONFIRMATION}",
            file=sys.stderr,
        )
        return 2
    if args.apply and not args.json_out:
        print(
            "Refusing apply: --json-out is required for pre-apply recovery evidence",
            file=sys.stderr,
        )
        return 2

    try:
        source_dsn = _dsn_from_env(args.source_dsn_env)
        target_dsn = _dsn_from_env(args.target_dsn_env)
        if source_dsn == target_dsn:
            raise RuntimeError("Source and target DSNs must not be identical")

        with psycopg.connect(source_dsn) as source_conn:
            source_conn.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            source_states = collect_sequence_states(source_conn)

        with psycopg.connect(target_dsn) as target_conn:
            target_conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            target_before = collect_sequence_states(target_conn)
            require_matching_inventory(
                source_states,
                target_before,
                args.expected_count,
            )

            if args.apply:
                require_target_update_privileges(target_conn, target_before)
                prepared_report = _report(
                    mode="apply",
                    status="prepared",
                    expected_count=args.expected_count,
                    source_states=source_states,
                    target_before=target_before,
                    target_after=None,
                    applied=False,
                    apply_attempted=False,
                )
                _write_report(args.json_out, prepared_report)

                try:
                    apply_sequence_states(target_conn, source_states)
                    target_after = collect_sequence_states(target_conn)
                    if not states_equal(source_states, target_after):
                        raise RuntimeError(
                            "Target sequence verification differs after apply"
                        )
                except (RuntimeError, psycopg.Error) as apply_exc:
                    target_after_failed_apply: list[SequenceState] | None = None
                    recovered_target_before = False
                    recovery_error: str | None = None
                    try:
                        (
                            target_after_failed_apply,
                            _target_recovered,
                        ) = restore_target_before(target_conn, target_before)
                        recovered_target_before = True
                    except (RuntimeError, psycopg.Error) as recovery_exc:
                        recovery_error = str(recovery_exc)

                    error = f"Apply failed: {apply_exc}"
                    if recovery_error is not None:
                        error += f"; automatic target restoration failed: {recovery_error}"
                    failure_report = _report(
                        mode="apply",
                        status="failed",
                        expected_count=args.expected_count,
                        source_states=source_states,
                        target_before=target_before,
                        target_after=target_before if recovered_target_before else None,
                        applied=False,
                        apply_attempted=True,
                        recovered_target_before=recovered_target_before,
                        target_after_failed_apply=target_after_failed_apply,
                        error=error,
                    )
                    _write_report(args.json_out, failure_report)
                    print(f"Sequence synchronization failed: {error}", file=sys.stderr)
                    return 1
            else:
                target_after = target_before

        report = _report(
            mode="apply" if args.apply else "compare",
            status="accepted",
            expected_count=args.expected_count,
            source_states=source_states,
            target_before=target_before,
            target_after=target_after,
            applied=bool(args.apply),
            apply_attempted=bool(args.apply),
        )
        if args.json_out:
            _write_report(args.json_out, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if bool(report["exact_match"]) or not args.apply else 1
    except (OSError, RuntimeError, ValueError, psycopg.Error) as exc:
        print(f"Sequence synchronization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
