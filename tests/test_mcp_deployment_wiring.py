"""Guards for the immutable third-image MCP deployment path."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "hetzner" / "compose.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "build-and-push-ghcr.yml"
DEPLOY = ROOT / "scripts" / "hetzner" / "deploy_app_release.sh"
VERIFY = ROOT / "scripts" / "hetzner" / "verify_app_release.sh"
ROLLBACK = ROOT / "scripts" / "hetzner" / "rollback_app_release.sh"
ACTIVATE = ROOT / "scripts" / "hetzner" / "activate_writable_release.sh"
LIVE_REHEARSAL = ROOT / "scripts" / "hetzner" / "rehearse_live_writable_release.sh"
LOGIN_REHEARSAL = ROOT / "scripts" / "hetzner" / "rehearse_temp_google_login.sh"
RELEASE_EXAMPLE = ROOT / "deploy" / "hetzner" / "release.env.example"

DIGEST = "sha256:" + "a" * 64


def _compose_environment(runtime_env: Path, *, with_mcp: bool) -> dict[str, str]:
    env = os.environ | {
        "API_IMAGE": f"ghcr.io/example/catscan-api@{DIGEST}",
        "DASHBOARD_IMAGE": f"ghcr.io/example/catscan-dashboard@{DIGEST}",
        "RELEASE_GIT_SHA": "b" * 40,
        "RELEASE_VERSION": "1.2.3",
        "RTBCAT_RUNTIME_ENV_FILE": str(runtime_env),
        "RTBCAT_POSTGRES_PASSWORD_FILE": "/tmp/postgres-password",
        "RTBCAT_POSTGRES_CA_FILE": "/tmp/postgres-ca.crt",
        "RTBCAT_GOOGLE_CREDENTIALS_FILE": "/tmp/google-adc.json",
    }
    if with_mcp:
        env["MCP_IMAGE"] = f"ghcr.io/example/catscan-mcp@{DIGEST}"
    else:
        env.pop("MCP_IMAGE", None)
    return env


def _render_compose(path: Path, env: dict[str, str]) -> dict:
    result = subprocess.run(
        ["docker", "compose", "-f", str(path), "config", "--format", "json"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return yaml.safe_load(result.stdout)


def test_compose_mcp_service_is_loopback_only_hardened_and_secretless() -> None:
    compose = yaml.safe_load(COMPOSE.read_text())
    mcp = compose["services"]["mcp"]

    assert mcp["image"] == (
        "${MCP_IMAGE:?Set MCP_IMAGE to a GHCR sha256 digest reference}"
    )
    assert mcp["pull_policy"] == "never"
    assert mcp["container_name"] == "rtbcat-mcp"
    assert mcp["ports"] == ["127.0.0.1:8010:8010"]
    assert mcp["cap_drop"] == ["ALL"]
    assert mcp["security_opt"] == ["no-new-privileges:true"]
    assert mcp["depends_on"] == {"api": {"condition": "service_healthy"}}
    assert mcp["logging"] == compose["services"]["api"]["logging"]
    assert mcp["healthcheck"]["test"][0:2] == ["CMD", "python"]
    assert "/health" in " ".join(mcp["healthcheck"]["test"])

    assert "volumes" not in mcp
    assert "secrets" not in mcp
    assert "env_file" not in mcp
    service_text = yaml.safe_dump(mcp)
    for forbidden in (
        "POSTGRES_",
        "DATABASE_URL",
        "DSN",
        "/run/rtbcat-secrets",
        "CATSCAN_API_KEY",
    ):
        assert forbidden not in service_text


def test_compose_mcp_configuration_defaults_dark_and_uses_internal_api() -> None:
    mcp = yaml.safe_load(COMPOSE.read_text())["services"]["mcp"]
    environment = mcp["environment"]

    assert environment["CATSCAN_MCP_ENABLED"] == ("${RTBCAT_DEPLOY_MCP_ENABLED:-false}")
    assert environment["RTBCAT_API_BASE_URL"] == "http://api:8000"
    assert environment["CATSCAN_MCP_PORT"] == "8010"
    assert environment["CATSCAN_MCP_RATE_LIMIT_PER_MINUTE"] == (
        "${RTBCAT_MCP_RATE_LIMIT_PER_MINUTE:-60}"
    )


def test_workflow_builds_and_validates_digest_pinned_mcp_image() -> None:
    workflow = WORKFLOW.read_text()

    for required in (
        "file: Dockerfile.mcp",
        "id: mcp",
        "scope=hetzner-catscan-mcp",
        "MCP_DIGEST: ${{ steps.mcp.outputs.digest }}",
        'for digest in "$API_DIGEST" "$DASHBOARD_DIGEST" "$MCP_DIGEST"',
        'printf \'MCP_IMAGE=%s@%s\\n\' "$MCP_IMAGE" "$MCP_DIGEST"',
        "tests/test_mcp_deployment_wiring.py",
        "tests/test_mcp_ingress_guards.py",
    ):
        assert required in workflow


def test_release_example_includes_digest_pinned_mcp_image() -> None:
    example = RELEASE_EXAMPLE.read_text()
    assert (
        "MCP_IMAGE=ghcr.io/replace-owner/catscan-mcp@sha256:" + "0123456789abcdef" * 4
    ) in example


def test_deploy_and_verify_scripts_cover_mcp_image_identity_and_listener() -> None:
    deploy = DEPLOY.read_text()
    verify = VERIFY.read_text()

    for required in (
        'MCP_IMAGE="$(release_value_optional MCP_IMAGE)"',
        "catscan-mcp@sha256:",
        '"${docker_pull[@]}" pull "$MCP_IMAGE"',
        'release_images+=("$MCP_IMAGE")',
        '--entrypoint /usr/bin/id "$MCP_IMAGE" -u',
        'export RTBCAT_DEPLOY_MCP_ENABLED="$MCP_ENABLED"',
        'grep -Fxq "$MCP_IMAGE"',
        '--mcp-enabled "$MCP_ENABLED"',
    ):
        assert required in deploy

    for required in (
        "containers+=(rtbcat-mcp)",
        "actual_mcp_image",
        'PortBindings["8010/tcp"]',
        '"HostIp":"127.0.0.1","HostPort":"8010"',
        "http://127.0.0.1:8010/health",
        "CATSCAN_MCP_ENABLED=${EXPECTED_MCP_ENABLED}",
        "/:(3000|8000|8010)$/",
    ):
        assert required in verify


def test_rollback_and_every_compose_renderer_accept_pre_mcp_manifests() -> None:
    deploy = DEPLOY.read_text()
    verify = VERIFY.read_text()
    rollback = ROLLBACK.read_text()

    assert "release_value_optional MCP_IMAGE" in deploy
    assert "release_value_optional MCP_IMAGE" in verify
    assert 'HAS_MCP="false"' in deploy
    assert 'has_mcp="false"' in verify
    assert "Pre-MCP release unexpectedly has rtbcat-mcp running." in verify
    assert '--mcp-enabled "$MCP_ENABLED"' in rollback

    for renderer in (ACTIVATE, LIVE_REHEARSAL):
        text = renderer.read_text()
        assert "release_value_optional MCP_IMAGE" in text
        assert "unset MCP_IMAGE" in text
    login_text = LOGIN_REHEARSAL.read_text()
    assert "unset MCP_IMAGE" in login_text
    assert 'MCP_IMAGE="${MCP_IMAGE:-}"' in login_text


def test_compose_renders_for_phase4_and_archived_pre_mcp_generations(
    tmp_path: Path,
) -> None:
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text("")

    phase4 = _render_compose(
        COMPOSE,
        _compose_environment(runtime_env, with_mcp=True),
    )
    assert set(phase4["services"]) == {"api", "dashboard", "mcp"}
    assert phase4["services"]["mcp"]["environment"]["CATSCAN_MCP_ENABLED"] == ("false")

    # Accepted releases archive their checksum-matched Compose generation.
    # This models an archived pre-Phase-4 file, whose manifest has no MCP_IMAGE.
    legacy = yaml.safe_load(COMPOSE.read_text())
    del legacy["services"]["mcp"]
    legacy_compose = tmp_path / "pre-mcp-compose.yml"
    legacy_compose.write_text(yaml.safe_dump(legacy, sort_keys=False))
    pre_mcp = _render_compose(
        legacy_compose,
        _compose_environment(runtime_env, with_mcp=False),
    )
    assert set(pre_mcp["services"]) == {"api", "dashboard"}
