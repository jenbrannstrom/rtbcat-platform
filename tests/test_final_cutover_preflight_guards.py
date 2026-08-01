"""Static guards for the read-only final-cutover preflight."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "hetzner" / "preflight_final_cutover.sh"


def script_text() -> str:
    return PREFLIGHT.read_text()


def test_preflight_parses_and_exposes_read_only_help() -> None:
    subprocess.run(["bash", "-n", str(PREFLIGHT)], check=True)
    result = subprocess.run(
        ["bash", str(PREFLIGHT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "This command is read-only" in result.stdout
    assert "--json-out" in result.stdout


def test_preflight_uses_read_only_provider_and_host_operations() -> None:
    text = script_text()

    for required in (
        "sql instances describe",
        "scheduler jobs list",
        "compute instances describe",
        "compute ssh",
        "pgbackrest --stanza=rtbcat info --output=json",
        "pg_subscription_rel",
        "logical-replication-monitor.jsonl",
        "docker ps -q",
        'authority_changed: false',
    ):
        assert required in text

    for forbidden in (
        "scheduler jobs pause",
        "scheduler jobs resume",
        "docker stop",
        "docker compose down",
        "ALTER ROLE",
        "pg_terminate_backend",
        "ALTER SUBSCRIPTION",
        "setval(",
        "api.cloudflare.com",
    ):
        assert forbidden not in text


def test_preflight_requires_current_migration_contracts() -> None:
    text = script_text()

    for contract in (
        '.ready == 98',
        '.not_ready == 0',
        '.subscription_enabled == true',
        '.generated_buyer == true',
        '.id_bigint == true',
        '.status == "ok"',
        'target_app_sealed: $app_sealed_ok',
        'ready_for_freeze',
    ):
        assert contract in text


def test_preflight_writes_private_evidence() -> None:
    text = script_text()
    assert 'install -m 0600 "$report_tmp" "$JSON_OUT"' in text
    assert 'if [[ -L "$JSON_OUT" ]]' in text
