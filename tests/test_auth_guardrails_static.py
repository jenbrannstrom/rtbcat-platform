"""Static guardrails for auth-loop and auth-health behavior.

These checks intentionally parse source text/AST so they can run without
importing FastAPI dependencies in constrained CI environments.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _literal_set_values(module_path: Path, target_name: str) -> set[str]:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == target_name:
                if not isinstance(node.value, ast.Set):
                    return set()
                values: set[str] = set()
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        values.add(elt.value)
                return values
    return set()


def test_api_key_middleware_keeps_auth_check_and_me_public() -> None:
    public_paths = _literal_set_values(REPO_ROOT / "api" / "auth.py", "PUBLIC_PATHS")
    assert "/auth/check" in public_paths
    assert "/auth/me" in public_paths


def test_session_middleware_has_degraded_auth_503_path() -> None:
    source = (REPO_ROOT / "api" / "session_middleware.py").read_text(encoding="utf-8")

    # Guardrail: session-validation failures should surface degraded-auth
    # semantics rather than being flattened into 401 redirect loops.
    assert "request.state.auth_error = \"database_unavailable\"" in source
    assert "status_code=503" in source
    assert "Authentication service temporarily unavailable." in source
