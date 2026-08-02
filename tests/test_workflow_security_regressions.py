from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_smoke_rejects_control_characters_before_github_env_export() -> None:
    source = (ROOT / ".github" / "workflows" / "live-major-smoke.yml").read_text(
        encoding="utf-8"
    )

    assert 'reject_env_controls "api_base_url" "${api_base_url}"' in source
    assert '[[ "${value}" =~ [[:cntrl:]] ]]' in source
    assert source.index('reject_env_controls "api_base_url"') < source.index(
        'echo "CATSCAN_API_BASE_URL=${api_base_url}"'
    )


def test_no_gcp_deploy_workflow_is_reintroduced() -> None:
    """The GCP deploy workflow must stay retired.

    It deployed to a VM that stopped serving traffic at the 2026-08-01 Hetzner
    cutover, and reintroducing it would restart a second writer against the
    frozen source. Production releases go through
    build-and-push-ghcr.yml plus scripts/hetzner/deploy_app_release.sh.
    """
    assert not (ROOT / ".github" / "workflows" / "deploy.yml").exists()
