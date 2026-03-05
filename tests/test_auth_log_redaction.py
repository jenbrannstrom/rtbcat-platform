"""Verify that auth modules do not log sensitive response bodies or user info."""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Files that handle authentication and should never log raw response bodies
AUTH_FILES = [
    REPO_ROOT / "api" / "auth_authing.py",
    REPO_ROOT / "api" / "auth_oauth_proxy.py",
    REPO_ROOT / "api" / "auth_bootstrap.py",
    REPO_ROOT / "api" / "auth_password.py",
]

# Patterns that indicate raw response body or full dict logging in f-strings
_DANGEROUS_FSTRING_PATTERNS = [
    # Direct response.text logging
    re.compile(r"response\.text|response\.body|response\.content"),
    # Full userinfo dict logging (not just specific fields)
    re.compile(r"\buserinfo\b(?!\[|\.)"),
    # Full token dict logging
    re.compile(r"\btokens?\b(?!\[|\.|_type|_response)"),
]


def _extract_fstring_references(node: ast.JoinedStr) -> list[str]:
    """Extract variable references from an f-string AST node."""
    refs = []
    for value in node.values:
        if isinstance(value, ast.FormattedValue):
            refs.append(ast.dump(value.value))
    return refs


def _find_logger_fstring_calls(tree: ast.Module) -> list[tuple[int, str]]:
    """Find logger.xxx(f"...{variable}...") calls that may leak secrets."""
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match logger.error/warning/info etc.
        if not (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
            and node.func.attr in ("error", "warning", "info", "debug", "critical")
        ):
            continue

        for arg in node.args:
            if isinstance(arg, ast.JoinedStr):
                # Get the source representation of f-string contents
                source_repr = ast.dump(arg)
                for pattern in _DANGEROUS_FSTRING_PATTERNS:
                    if pattern.search(source_repr):
                        issues.append((node.lineno, f"logger.{node.func.attr} with f-string containing {pattern.pattern}"))
    return issues


def test_auth_files_do_not_log_raw_response_bodies() -> None:
    """Auth modules must not log raw HTTP response bodies via f-strings."""
    all_issues: list[tuple[str, int, str]] = []

    for path in AUTH_FILES:
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        issues = _find_logger_fstring_calls(tree)
        for line, desc in issues:
            all_issues.append((rel_path, line, desc))

    assert not all_issues, (
        "Auth modules must not log raw response bodies or full user dicts:\n"
        + "\n".join(f"- {path}:{line} {desc}" for path, line, desc in all_issues)
    )


def test_auth_authing_uses_structured_logging_for_errors() -> None:
    """Verify auth_authing.py error paths use %-style logging, not f-strings with response data."""
    path = REPO_ROOT / "api" / "auth_authing.py"
    if not path.exists():
        return
    source = path.read_text(encoding="utf-8")

    # Should NOT contain these patterns (raw response body logging)
    dangerous_patterns = [
        r'logger\.error\(f".*\{token_response\.text\}',
        r'logger\.error\(f".*\{userinfo_response\.text\}',
        r'logger\.error\(f".*\{userinfo\}"',
    ]
    for pattern in dangerous_patterns:
        matches = re.findall(pattern, source)
        assert not matches, (
            f"auth_authing.py still contains dangerous log pattern: {pattern}\n"
            f"Matches: {matches}"
        )
