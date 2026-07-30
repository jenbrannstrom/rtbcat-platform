from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hetzner" / "install_temp_google_oauth_proxy.sh"


def script_text() -> str:
    return SCRIPT.read_text()


def test_oauth_proxy_is_checksum_pinned_and_temp_hostname_scoped() -> None:
    text = script_text()
    assert 'OAUTH2_PROXY_VERSION="7.6.0"' in text
    assert 'OAUTH2_PROXY_SHA256="' in text
    assert "sha256sum -c -" in text
    assert r"-hetzner\.rtb\.cat" in text
    assert "INSTALL_TEMP_GOOGLE_OAUTH_PROXY_NO_DNS" in text


def test_oauth_inputs_are_root_only_and_not_logged() -> None:
    text = script_text()
    assert 'stat -c \'%u:%g:%a\'' in text
    assert '"0:0:600"' in text
    assert "client_secret = {json.dumps(client_secret)}" in text
    assert 'echo "${client_secret}"' not in text
    assert 'printf "${client_secret}"' not in text


def test_oauth_proxy_is_loopback_only_and_domain_restricted() -> None:
    text = script_text()
    assert 'http_address = "127.0.0.1:4180"' in text
    assert "email_domains = {json.dumps(domains)}" in text
    assert "$4 ~ /:4180$/" in text
    assert r'$4 !~ /^127\.0\.0\.1:/' in text


def test_oauth_service_is_hardened() -> None:
    text = script_text()
    assert "User=rtbcat-oauth" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "CapabilityBoundingSet=" in text
    assert "systemctl enable rtbcat-temp-oauth2-proxy.service" in text
    assert "systemctl restart rtbcat-temp-oauth2-proxy.service" in text
