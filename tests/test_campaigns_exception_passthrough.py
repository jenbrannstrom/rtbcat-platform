"""Verify campaigns_router.py preserves HTTPException passthrough.

This extends the router guard pattern from
test_router_http_exception_passthrough_guard.py to also cover
api/campaigns_router.py, which lives outside api/routers/.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CAMPAIGNS_ROUTER = REPO_ROOT / "api" / "campaigns_router.py"


def _except_type_names(exc_type: ast.expr | None) -> set[str]:
    if exc_type is None:
        return set()
    if isinstance(exc_type, ast.Name):
        return {exc_type.id}
    if isinstance(exc_type, ast.Tuple):
        names: set[str] = set()
        for elt in exc_type.elts:
            if isinstance(elt, ast.Name):
                names.add(elt.id)
        return names
    return set()


def _handler_raises_http_exception(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if not isinstance(node, ast.Raise):
            continue
        if node.exc is None:
            continue
        if isinstance(node.exc, ast.Call):
            func = node.exc.func
            if isinstance(func, ast.Name) and func.id == "HTTPException":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "HTTPException":
                return True
    return False


def _is_router_handler(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "router":
            return True
    return False


def test_campaigns_router_preserves_http_exception_passthrough() -> None:
    """Every try block in campaigns_router that remaps Exception -> HTTPException
    must also have an except HTTPException: raise clause."""
    source = CAMPAIGNS_ROUTER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not _is_router_handler(node):
            continue

        for stmt in ast.walk(node):
            if not isinstance(stmt, ast.Try):
                continue

            has_exception_to_http_remap = any(
                "Exception" in _except_type_names(handler.type)
                and _handler_raises_http_exception(handler)
                for handler in stmt.handlers
            )
            has_http_passthrough = any(
                "HTTPException" in _except_type_names(handler.type)
                for handler in stmt.handlers
            )

            if has_exception_to_http_remap and not has_http_passthrough:
                violations.append((stmt.lineno, node.name))

    assert not violations, (
        "campaigns_router.py try blocks that remap Exception -> HTTPException "
        "must preserve HTTPException passthrough:\n"
        + "\n".join(f"- line {line} in {name}" for line, name in violations)
    )
