"""Static guards for the bounded B1 live writable rehearsal."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REHEARSE = ROOT / "scripts" / "hetzner" / "rehearse_live_writable_release.sh"


def test_b1_script_parses_and_exposes_exact_confirmations() -> None:
    subprocess.run(["bash", "-n", str(REHEARSE)], check=True)
    result = subprocess.run(
        ["bash", str(REHEARSE), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "REHEARSE_LIVE_WRITABLE_SCHEDULERS_OFF_NO_DNS" in result.stdout
    assert "PREFLIGHT_B1_LIVE_WRITABLE" in result.stdout
    assert "RESTORE_B1_READ_ONLY_SHADOW" not in result.stdout


def test_b1_is_bounded_to_rehearsal_and_restores_defense_in_depth() -> None:
    script = REHEARSE.read_text()

    for guard in (
        'EXPECTED_DATABASE="rtbcat_serving_rehearsal"',
        "RTBCAT_DEPLOY_READ_ONLY_SHADOW=false",
        "RTBCAT_DEPLOY_GMAIL_SCHEDULER=false",
        "RTBCAT_DEPLOY_PRECOMPUTE_SCHEDULER=false",
        "RTBCAT_DEPLOY_CREATIVE_CACHE_SCHEDULER=false",
        "default_transaction_read_only",
        "run_db_helper set-off",
        "run_db_helper set-on",
        "compose stop",
        "verify_with_retry writable-schedulers-off",
        "verify_with_retry shadow",
        "systemd-run",
        "--on-active=15m",
        "verify_with_retry",
        "rolled_back",
        "residue_absent",
    ):
        assert guard in script


def test_b1_does_not_weaken_final_activation_guards() -> None:
    final_activation = (
        ROOT / "scripts" / "hetzner" / "activate_writable_release.sh"
    ).read_text()

    assert "REHEARSE_LIVE_WRITABLE" not in final_activation
    assert ".source_writers_frozen == true" in final_activation
    assert ".subscriber_caught_up == true" in final_activation
    assert ".sequence_sync_exact_match == true" in final_activation
