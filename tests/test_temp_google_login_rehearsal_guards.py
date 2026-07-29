from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hetzner" / "rehearse_temp_google_login.sh"
OVERRIDE = ROOT / "deploy" / "hetzner" / "temp-google-oauth.override.yml"


def test_override_preserves_shadow_and_scheduler_guards() -> None:
    text = OVERRIDE.read_text()
    assert 'OAUTH2_PROXY_ENABLED: "true"' in text
    assert 'CATSCAN_ENABLE_PASSWORD_LOGIN: "false"' in text
    assert 'CATSCAN_READ_ONLY_SHADOW: "true"' in text
    assert text.count('SCHEDULER: "false"') == 3


def test_rehearsal_is_restricted_to_stale_database_and_accepted_release() -> None:
    text = SCRIPT.read_text()
    assert 'EXPECTED_DATABASE="rtbcat_serving_rehearsal"' in text
    assert "accepted-${RELEASE_GIT_SHA}.marker" in text
    assert "DEPLOY_COMPOSE_SHA256" in text


def test_rehearsal_has_deadman_and_failure_restoration() -> None:
    text = SCRIPT.read_text()
    assert "--on-active=15m" in text
    assert "RESTORE_TEMP_GOOGLE_LOGIN_SHADOW" in text
    assert "restore_on_exit" in text
    assert "trap restore_on_exit EXIT" in text


def test_rehearsal_requires_read_only_and_disabled_schedulers() -> None:
    text = SCRIPT.read_text()
    assert "CATSCAN_READ_ONLY_SHADOW=true" in text
    assert "CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER=false" in text
    assert "CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER=false" in text
    assert "CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER=false" in text
    assert "check_gmail_import_idle.py" in text


def test_rehearsal_trusts_only_loopback_and_exact_docker_gateway() -> None:
    text = SCRIPT.read_text()
    override = OVERRIDE.read_text()
    assert ".NetworkSettings.Networks" in text
    assert 'RTBCAT_OAUTH2_PROXY_TRUSTED_IPS="127.0.0.1,::1,${API_GATEWAY}"' in text
    assert "Expected exactly one IPv4 Docker gateway" in text
    assert "${RTBCAT_OAUTH2_PROXY_TRUSTED_IPS:?" in override
    assert "172.16.0.0/12" not in override


def test_rehearsal_requires_exact_confirmation() -> None:
    text = SCRIPT.read_text()
    assert "ENABLE_TEMP_GOOGLE_LOGIN_READ_ONLY_SCHEDULERS_OFF" in text
    assert "RESTORE_TEMP_GOOGLE_LOGIN_SHADOW" in text
