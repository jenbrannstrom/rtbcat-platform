"""Tests for the guarded PostgreSQL sequence cutover helper."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scripts.hetzner import sync_postgres_sequences as sequence_sync


def _state(
    schema: str = "public",
    name: str = "example_id_seq",
    last_value: int = 7,
    is_called: bool = True,
) -> sequence_sync.SequenceState:
    return sequence_sync.SequenceState(schema, name, last_value, is_called)


def test_qualified_name_quotes_each_identifier() -> None:
    state = _state(schema='odd"schema', name='name.with"quote')

    assert state.qualified_name == '"odd""schema"."name.with""quote"'


def test_matching_inventory_requires_expected_count() -> None:
    states = [_state()]

    with pytest.raises(RuntimeError, match="Source has 1 sequences; expected 2"):
        sequence_sync.require_matching_inventory(states, states, expected_count=2)


def test_matching_inventory_reports_missing_and_extra() -> None:
    source = [_state(name="source_seq")]
    target = [_state(name="target_seq")]

    with pytest.raises(RuntimeError, match="Sequence inventory mismatch"):
        sequence_sync.require_matching_inventory(source, target, expected_count=1)


def test_states_equal_compares_values_and_is_called() -> None:
    source = [_state(last_value=10, is_called=True)]

    assert sequence_sync.states_equal(source, [_state(last_value=10, is_called=True)])
    assert not sequence_sync.states_equal(
        source,
        [_state(last_value=10, is_called=False)],
    )


def test_apply_uses_regclass_parameter_and_preserves_is_called() -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    conn = SimpleNamespace(
        execute=lambda query, params: calls.append((query, params)),
    )
    source = [_state(last_value=42, is_called=False)]

    sequence_sync.apply_sequence_states(conn, source)

    assert calls == [
        (
            "SELECT pg_catalog.setval(%s::regclass, %s, %s)",
            ('"public"."example_id_seq"', 42, False),
        )
    ]


def test_apply_mode_requires_exact_confirmation(capsys) -> None:
    result = sequence_sync.main(["--apply", "--confirm", "wrong"])

    assert result == 2
    assert sequence_sync.APPLY_CONFIRMATION in capsys.readouterr().err


def test_apply_mode_requires_recovery_evidence_path(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("SOURCE_POSTGRES_DSN", "postgresql://source")
    monkeypatch.setenv("TARGET_POSTGRES_DSN", "postgresql://target")

    result = sequence_sync.main(
        ["--apply", "--confirm", sequence_sync.APPLY_CONFIRMATION]
    )

    assert result == 2
    assert "--json-out is required" in capsys.readouterr().err


def test_target_update_privileges_are_preflighted() -> None:
    states = [_state(name="allowed"), _state(name="denied")]
    answers = iter([(True,), (False,)])
    conn = SimpleNamespace(
        execute=lambda _query, _params: SimpleNamespace(
            fetchone=lambda: next(answers)
        )
    )

    with pytest.raises(RuntimeError, match='"public"."denied"'):
        sequence_sync.require_target_update_privileges(conn, states)


def test_failed_apply_recovery_restores_and_commits(monkeypatch) -> None:
    target_before = [_state(last_value=7, is_called=False)]
    target_partial = [_state(last_value=42, is_called=True)]
    collected = iter([target_partial, target_before])
    calls: list[str] = []
    conn = SimpleNamespace(
        rollback=lambda: calls.append("rollback"),
        commit=lambda: calls.append("commit"),
    )
    monkeypatch.setattr(
        sequence_sync,
        "collect_sequence_states",
        lambda _conn: next(collected),
    )
    monkeypatch.setattr(
        sequence_sync,
        "apply_sequence_states",
        lambda _conn, states: calls.append(f"restore:{states[0].last_value}"),
    )

    partial, recovered = sequence_sync.restore_target_before(conn, target_before)

    assert partial == target_partial
    assert recovered == target_before
    assert calls == ["rollback", "restore:7", "commit"]


def test_report_is_mode_0600_and_contains_no_dsn(tmp_path) -> None:
    report_path = tmp_path / "sequence-report.json"
    report = sequence_sync._report(
        mode="apply",
        status="prepared",
        expected_count=1,
        source_states=[_state(last_value=42)],
        target_before=[_state(last_value=7)],
        target_after=None,
        applied=False,
        apply_attempted=False,
    )

    sequence_sync._write_report(str(report_path), report)

    payload = json.loads(report_path.read_text())
    assert payload["status"] == "prepared"
    assert payload["target_after"] is None
    assert report_path.stat().st_mode & 0o777 == 0o600
    assert "dsn" not in report_path.read_text().lower()


def test_compare_mode_requires_dsn_environment(monkeypatch, capsys) -> None:
    monkeypatch.delenv("SOURCE_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("TARGET_POSTGRES_DSN", raising=False)

    result = sequence_sync.main([])

    assert result == 1
    assert "SOURCE_POSTGRES_DSN" in capsys.readouterr().err
