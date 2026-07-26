"""Static and parsing guards for the immutable writable activation path."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVATE = ROOT / "scripts" / "hetzner" / "activate_writable_release.sh"
DEPLOY = ROOT / "scripts" / "hetzner" / "deploy_app_release.sh"
VERIFY = ROOT / "scripts" / "hetzner" / "verify_app_release.sh"
COMPOSE = ROOT / "deploy" / "hetzner" / "compose.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "build-and-push-ghcr.yml"


def test_activation_scripts_parse_and_expose_help() -> None:
    for script in (ACTIVATE, DEPLOY, VERIFY):
        subprocess.run(["bash", "-n", str(script)], check=True)

    result = subprocess.run(
        ["bash", str(ACTIVATE), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "ACTIVATE_WRITABLE_SCHEDULERS_OFF_NO_DNS" in result.stdout
    assert "REHEARSE_WRITABLE_SCHEDULERS_OFF_NO_DNS" in result.stdout


def test_compose_defaults_to_shadow_with_every_scheduler_off() -> None:
    compose = COMPOSE.read_text()

    assert (
        "CATSCAN_READ_ONLY_SHADOW: "
        "${RTBCAT_DEPLOY_READ_ONLY_SHADOW:-true}"
    ) in compose
    assert (
        "CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER: "
        "${RTBCAT_DEPLOY_GMAIL_SCHEDULER:-false}"
    ) in compose
    assert (
        "CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER: "
        "${RTBCAT_DEPLOY_PRECOMPUTE_SCHEDULER:-false}"
    ) in compose
    assert (
        "CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER: "
        "${RTBCAT_DEPLOY_CREATIVE_CACHE_SCHEDULER:-false}"
    ) in compose
    assert "build:" not in compose
    assert '"127.0.0.1:8000:8000"' in compose
    assert '"127.0.0.1:3000:3000"' in compose


def test_shadow_deploy_overrides_inherited_activation_controls() -> None:
    deploy = DEPLOY.read_text()

    assert "export RTBCAT_DEPLOY_READ_ONLY_SHADOW=true" in deploy
    assert "export RTBCAT_DEPLOY_GMAIL_SCHEDULER=false" in deploy
    assert "export RTBCAT_DEPLOY_PRECOMPUTE_SCHEDULER=false" in deploy
    assert "export RTBCAT_DEPLOY_CREATIVE_CACHE_SCHEDULER=false" in deploy
    assert "CATSCAN_READ_ONLY_SHADOW=true" in deploy


def test_writable_activation_requires_all_cutover_and_recovery_gates() -> None:
    activate = ACTIVATE.read_text()

    for gate in (
        ".source_writers_frozen == true",
        ".source_active_writer_sessions == 0",
        ".subscriber_caught_up == true",
        ".sequence_sync_exact_match == true",
        ".final_reconciliation_accepted == true",
        ".target_backup_accepted == true",
        ".dns_changed == false",
        ".target_scheduler_enabled == false",
    ):
        assert gate in activate

    assert "RTBCAT_DEPLOY_READ_ONLY_SHADOW=false" in activate
    assert "RTBCAT_DEPLOY_GMAIL_SCHEDULER=false" in activate
    assert "RTBCAT_DEPLOY_PRECOMPUTE_SCHEDULER=false" in activate
    assert "RTBCAT_DEPLOY_CREATIVE_CACHE_SCHEDULER=false" in activate
    assert "export RTBCAT_DEPLOY_READ_ONLY_SHADOW=true" in activate
    assert "shadow_restored_after_failure" in activate
    assert "--mode writable-schedulers-off" in activate
    assert "--mode shadow --with-google" in activate


def test_verifier_distinguishes_shadow_and_writable_scheduler_off_modes() -> None:
    verify = VERIFY.read_text()

    assert 'EXPECTED_MODE="shadow"' in verify
    assert '"writable-schedulers-off"' in verify
    assert "CATSCAN_READ_ONLY_SHADOW=true" in verify
    assert "CATSCAN_READ_ONLY_SHADOW=false" in verify
    assert "CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER" in verify
    assert "CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER" in verify
    assert "CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER" in verify


def test_publish_workflow_runs_activation_and_scheduler_guards() -> None:
    workflow = WORKFLOW.read_text()

    for test_path in (
        "tests/test_writable_activation_guards.py",
        "tests/test_scheduler_guard.py",
        "tests/test_precompute_scheduler_guard.py",
        "tests/test_creative_cache_router.py",
    ):
        assert test_path in workflow
