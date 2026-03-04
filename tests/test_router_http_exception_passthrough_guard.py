from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTERS_DIR = REPO_ROOT / "api" / "routers"


def _is_router_handler(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "router"
        ):
            return True
    return False


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


def test_route_try_blocks_preserve_http_exception_passthrough() -> None:
    violations: list[tuple[str, int, str]] = []

    for path in sorted(ROUTERS_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel_path = path.relative_to(REPO_ROOT).as_posix()

        for node in tree.body:
            if not _is_router_handler(node):
                continue

            for stmt in node.body:
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
                    violations.append((rel_path, stmt.lineno, node.name))

    assert not violations, (
        "Route try blocks that remap Exception -> HTTPException must preserve "
        "HTTPException passthrough in the same try:\n"
        + "\n".join(f"- {path}:{line} {name}" for path, line, name in violations)
    )
