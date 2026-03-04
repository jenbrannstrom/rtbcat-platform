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


def test_router_handlers_have_return_annotations() -> None:
    missing: list[tuple[str, int, str]] = []

    for path in sorted(ROUTERS_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        for node in tree.body:
            if _is_router_handler(node) and node.returns is None:
                missing.append((rel_path, node.lineno, node.name))

    assert not missing, (
        "Route handlers must include explicit return annotations:\n"
        + "\n".join(f"- {path}:{line} {name}" for path, line, name in missing)
    )
