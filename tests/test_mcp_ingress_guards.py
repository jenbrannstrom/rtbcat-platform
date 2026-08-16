"""Static and parsing guards for the fixed MCP Nginx generator."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hetzner" / "apply_mcp_ingress.sh"


def test_mcp_ingress_script_parses_and_exposes_fixed_scope() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "mcp.rtb.cat" in result.stdout
    assert "APPLY_MCP_RTB_CAT_INGRESS" in result.stdout
    assert "never changes DNS" in result.stdout


def test_mcp_ingress_uses_expected_tls_and_loopback_upstream() -> None:
    script = SCRIPT.read_text()

    for required in (
        'HOSTNAME="mcp.rtb.cat"',
        "/etc/letsencrypt/live/${HOSTNAME}",
        "ssl_protocols TLSv1.2 TLSv1.3;",
        "proxy_pass http://127.0.0.1:8010;",
        "proxy_read_timeout 600s;",
        "proxy_buffering off;",
        "proxy_request_buffering off;",
        "proxy_set_header Authorization $http_authorization;",
    ):
        assert required in script


def test_mcp_ingress_requires_healthy_container_and_valid_nginx() -> None:
    script = SCRIPT.read_text()

    for required in (
        "rtbcat-mcp",
        "{{.State.Health.Status}}",
        "http://127.0.0.1:8010/health",
        "nginx -t",
        "systemctl reload nginx",
        '--resolve "${HOSTNAME}:443:127.0.0.1"',
    ):
        assert required in script


def test_mcp_ingress_does_not_issue_tls_change_dns_or_enable_mcp() -> None:
    script = SCRIPT.read_text()

    for forbidden in (
        "certbot certonly",
        "CLOUDFLARE_API_TOKEN",
        "CATSCAN_MCP_ENABLED=true",
        "docker compose up",
    ):
        assert forbidden not in script
