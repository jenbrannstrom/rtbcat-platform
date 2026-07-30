from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hetzner" / "manage_temp_public_ingress.sh"


def script_text() -> str:
    return SCRIPT.read_text()


def test_temp_ingress_is_scoped_away_from_production_hostname() -> None:
    text = script_text()
    assert r"-hetzner\.rtb\.cat" in text
    assert '"${TEMP_HOSTNAME}" == "scan.rtb.cat"' in text


def test_temp_ingress_requires_shadow_and_scheduler_guards() -> None:
    text = script_text()
    assert "CATSCAN_READ_ONLY_SHADOW" in text
    assert "CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER" in text
    assert "CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER" in text
    assert "CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER" in text
    assert "Every target scheduler flag must remain false." in text


def test_temp_ingress_preserves_loopback_application_listeners() -> None:
    text = script_text()
    assert "$4 ~ /:3000$/ || $4 ~ /:8000$/" in text
    assert r'$4 !~ /^127\.0\.0\.1:/' in text


def test_stage_is_sealed_and_activation_requires_direct_dns() -> None:
    text = script_text()
    assert "STAGE_TEMP_INGRESS_SEALED_NO_DNS" in text
    assert "SEALED: ACME challenge files are available; application proxying is disabled." in text
    assert "return 404;" in text
    assert "verify_direct_dns" in text
    assert '"${resolved[0]}" != "${EXPECTED_IPV4}"' in text


def test_active_proxy_is_operator_restricted_and_read_only_gated() -> None:
    text = script_text()
    assert "ACTIVATE_TEMP_READ_ONLY_INGRESS_SCHEDULERS_OFF" in text
    assert "allow {operator_cidr};" in text
    assert "deny all;" in text
    assert "assert_shadow_safe" in text
    assert "certbot certonly" in text
    assert "for attempt in {1..12}" in text
    assert "Temporary HTTPS health did not settle after Nginx reload." in text
    assert "if grep -q '^# ACTIVE:'" in text


def test_google_oauth_proxying_is_explicit_and_loopback_only() -> None:
    text = script_text()
    assert "--google-oauth" in text
    assert 'ENABLE_GOOGLE_OAUTH="false"' in text
    assert "location = /oauth2/ping" in text
    assert "proxy_pass http://127.0.0.1:4180/ping;" in text
    assert "proxy_pass http://127.0.0.1:4180;" in text
    assert "auth_request /oauth2/auth;" in text
    assert "error_page 401 403 = @api_without_oauth;" in text
    assert "Google OAuth was requested but its loopback proxy is not healthy." in text


def test_failed_activation_returns_to_sealed_mode() -> None:
    text = script_text()
    assert "trap seal_failed_activation EXIT" in text
    assert "Activation was not accepted; restoring sealed ACME-plus-404 mode." in text
    assert "expected 404 after Nginx reload." in text
    assert "ACTIVATION_ACCEPTED=1" in text
    assert "trap - EXIT" in text


def test_seal_rolls_back_proxy_without_deleting_certificates() -> None:
    text = script_text()
    assert "SEAL_TEMP_INGRESS" in text
    assert "certificates were preserved" in text
