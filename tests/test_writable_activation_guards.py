"""Static and parsing guards for the immutable writable activation path."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVATE = ROOT / "scripts" / "hetzner" / "activate_writable_release.sh"
DEPLOY = ROOT / "scripts" / "hetzner" / "deploy_app_release.sh"
ROLLBACK = ROOT / "scripts" / "hetzner" / "rollback_app_release.sh"
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


def test_deploy_always_renders_activation_controls_from_mode() -> None:
    """Every RTBCAT_DEPLOY_* control must be exported explicitly.

    compose.yml defaults all four to the shadow values, so a deploy that left
    any of them unset would silently redeploy a live host as read-only with
    schedulers off. They must be rendered from the selected mode, never
    inherited from the operator shell.
    """
    deploy = DEPLOY.read_text()

    for var in (
        "RTBCAT_DEPLOY_READ_ONLY_SHADOW",
        "RTBCAT_DEPLOY_GMAIL_SCHEDULER",
        "RTBCAT_DEPLOY_PRECOMPUTE_SCHEDULER",
        "RTBCAT_DEPLOY_CREATIVE_CACHE_SCHEDULER",
    ):
        assert f'export {var}="$EXPECTED' in deploy

    assert 'MODE="shadow"' in deploy, "shadow must remain the default mode"


def test_deploy_fully_specifies_both_postures() -> None:
    deploy = DEPLOY.read_text()

    # shadow: read-only, schedulers off
    assert 'EXPECTED_SHADOW="true"' in deploy
    assert 'EXPECTED_SCHEDULERS="false"' in deploy
    # production: writable, schedulers on
    assert 'EXPECTED_SHADOW="false"' in deploy
    assert 'EXPECTED_SCHEDULERS="true"' in deploy


def test_deploy_couples_confirmation_string_to_mode() -> None:
    """A production deploy must not be issuable with a shadow command line."""
    deploy = DEPLOY.read_text()

    assert 'EXPECTED_CONFIRM="deploy-shadow-no-dns"' in deploy
    assert 'EXPECTED_CONFIRM="deploy-production-live"' in deploy
    assert 'if [[ "$CONFIRM" != "$EXPECTED_CONFIRM" ]]' in deploy


def test_deploy_asserts_runtime_env_matches_requested_posture() -> None:
    """The deploy refuses to *change* posture; it only redeploys within one."""
    deploy = DEPLOY.read_text()

    assert '"${scheduler_flag}=${EXPECTED_SCHEDULERS}"' in deploy
    assert '"CATSCAN_READ_ONLY_SHADOW=${EXPECTED_SHADOW}"' in deploy


def test_deploy_rejects_unknown_mode() -> None:
    result = subprocess.run(
        ["bash", str(DEPLOY), "--mode", "bogus", "--confirm", "whatever"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "shadow or production" in result.stderr


def test_rollback_passes_mode_through_to_deploy() -> None:
    """Rollback must be able to target a live host, not only a shadow one."""
    rollback = ROLLBACK.read_text()

    assert '--mode) MODE="${2:?missing mode}"' in rollback
    assert 'deploy_confirm="deploy-production-live"' in rollback
    assert 'deploy_confirm="deploy-shadow-no-dns"' in rollback
    assert '--mode "$MODE"' in rollback


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
    assert "--mode shadow" in activate
    assert "--mcp-enabled \"$MCP_ENABLED\"" in activate
    assert "--with-google" in activate


def test_verifier_distinguishes_all_three_postures() -> None:
    verify = VERIFY.read_text()

    assert 'EXPECTED_MODE="shadow"' in verify, "shadow must remain the default"
    assert "writable-schedulers-off" in verify
    assert "production" in verify
    # scheduler expectation is mode-dependent, not hardcoded false
    assert 'EXPECTED_SCHEDULER_STATE="false"' in verify
    assert 'EXPECTED_SCHEDULER_STATE="true"' in verify
    assert '"${scheduler_flag}=${EXPECTED_SCHEDULER_STATE}"' in verify
    assert "CATSCAN_READ_ONLY_SHADOW=true" in verify
    assert "CATSCAN_READ_ONLY_SHADOW=false" in verify
    assert "CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER" in verify
    assert "CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER" in verify
    assert "CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER" in verify


def test_verifier_rejects_unknown_mode() -> None:
    result = subprocess.run(
        ["bash", str(VERIFY), "--release-file", "/dev/null", "--mode", "bogus"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "shadow, writable-schedulers-off or production" in result.stderr


def test_publish_workflow_runs_activation_and_scheduler_guards() -> None:
    workflow = WORKFLOW.read_text()

    for test_path in (
        "tests/test_writable_activation_guards.py",
        "tests/test_scheduler_guard.py",
        "tests/test_precompute_scheduler_guard.py",
        "tests/test_creative_cache_router.py",
        "tests/test_live_writable_rehearsal_guards.py",
    ):
        assert test_path in workflow
