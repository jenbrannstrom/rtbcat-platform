"""Static guardrails for auth-loop and auth-health behavior.

These checks intentionally parse source text/AST so they can run without
importing FastAPI dependencies in constrained CI environments.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _literal_sequence_values(module_path: Path, target_name: str) -> set[str]:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == target_name:
                if not isinstance(node.value, (ast.Set, ast.Tuple, ast.List)):
                    return set()
                values: set[str] = set()
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        values.add(elt.value)
                return values
    return set()


def _literal_set_values(module_path: Path, target_name: str) -> set[str]:
    return _literal_sequence_values(module_path, target_name)


def test_api_key_middleware_keeps_auth_check_and_me_public() -> None:
    public_paths = _literal_set_values(REPO_ROOT / "api" / "auth_public_paths.py", "PUBLIC_PATHS")
    assert "/auth/check" in public_paths
    assert "/auth/me" in public_paths


def test_api_key_middleware_keeps_login_entrypoints_public() -> None:
    public_paths = _literal_set_values(REPO_ROOT / "api" / "auth_public_paths.py", "PUBLIC_PATHS")

    assert "/auth/bootstrap" in public_paths
    assert "/auth/providers" in public_paths
    assert "/auth/login" in public_paths
    assert "/auth/register" in public_paths
    assert "/auth/authing/login" in public_paths
    assert "/auth/authing/callback" in public_paths


def test_auth_middlewares_share_public_route_contract() -> None:
    api_key_source = (REPO_ROOT / "api" / "auth.py").read_text(encoding="utf-8")
    session_source = (REPO_ROOT / "api" / "session_middleware.py").read_text(encoding="utf-8")

    assert "from api.auth_public_paths import" in api_key_source
    assert "from api.auth_public_paths import" in session_source
    assert "PUBLIC_PATHS = {" not in api_key_source
    assert "PUBLIC_PATHS = {" not in session_source


def test_agent_api_prefixes_bypass_generic_middleware_contract() -> None:
    public_prefixes = _literal_sequence_values(
        REPO_ROOT / "api" / "auth_public_paths.py",
        "PUBLIC_PREFIXES",
    )
    session_source = (REPO_ROOT / "api" / "session_middleware.py").read_text(encoding="utf-8")

    assert "/agent/v1/" in public_prefixes
    assert "/api/agent/v1/" in public_prefixes
    assert "AGENT_API_PREFIXES" not in session_source
    assert "AgentTokenService().authenticate_request(request)" not in session_source


def test_gcp_nginx_uses_oauth_as_optional_identity_source() -> None:
    source = (REPO_ROOT / "scripts" / "apply_gcp_nginx_auth_contract.sh").read_text(
        encoding="utf-8"
    )

    # Guardrail: OAuth2 Proxy must not be a hard gate in front of the app/API,
    # otherwise password login and bootstrap get redirected before FastAPI can
    # create or validate an rtbcat_session.
    assert "error_page 401 403 = @api_without_oauth;" in source
    assert "location @api_without_oauth" in source
    assert "error_page 401 = /oauth2/sign_in;" not in source


def test_gcp_nginx_can_edge_gate_agent_api() -> None:
    source = (REPO_ROOT / "scripts" / "apply_gcp_nginx_auth_contract.sh").read_text(
        encoding="utf-8"
    )

    assert "location ^~ /api/agent/v1/" in source
    assert "CATSCAN_AGENT_API_HTPASSWD" in source
    assert "auth_basic \"Cat-Scan Agent API\";" in source
    assert "auth_basic_user_file /etc/nginx/catscan-agent-api.htpasswd;" in source


def test_gcp_nginx_contract_owns_tls_site_and_disables_stale_site() -> None:
    source = (REPO_ROOT / "scripts" / "apply_gcp_nginx_auth_contract.sh").read_text(
        encoding="utf-8"
    )

    assert "listen 443 ssl;" in source
    assert "include /etc/nginx/snippets/catscan-app-locations.conf;" in source
    assert "/etc/nginx/sites-enabled/catscan.conf" in source
    assert "catscan.conf.disabled." in source


def test_gcp_deploy_paths_apply_repo_owned_nginx_contract() -> None:
    startup_source = (REPO_ROOT / "terraform" / "gcp" / "startup.sh").read_text(
        encoding="utf-8"
    )
    deploy_source = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )

    assert "scripts/apply_gcp_nginx_auth_contract.sh" in startup_source
    assert "scripts/apply_gcp_nginx_auth_contract.sh" in deploy_source


def test_caddy_leaves_auth_to_the_app() -> None:
    source = (REPO_ROOT / "Caddyfile").read_text(encoding="utf-8")

    assert "handle /api/*" in source
    assert "uri strip_prefix /api" in source
    assert "reverse_proxy api:8000" in source
    assert "oauth2" not in source.lower()


def test_session_middleware_has_degraded_auth_503_path() -> None:
    source = (REPO_ROOT / "api" / "session_middleware.py").read_text(encoding="utf-8")

    # Guardrail: session-validation failures should surface degraded-auth
    # semantics rather than being flattened into 401 redirect loops.
    assert "request.state.auth_error = \"database_unavailable\"" in source
    assert "status_code=503" in source
    assert "Authentication service temporarily unavailable." in source
