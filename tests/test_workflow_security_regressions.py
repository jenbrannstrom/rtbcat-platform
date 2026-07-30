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


def test_deploy_cleans_registry_credentials_on_every_exit_path() -> None:
    source = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )

    assert "cleanup_ar_credentials()" in source
    assert "trap cleanup_ar_credentials EXIT" in source
    assert source.index("trap cleanup_ar_credentials EXIT") < source.index(
        "docker compose -f docker-compose.gcp.yml pull"
    )
    assert "trap - EXIT" in source
