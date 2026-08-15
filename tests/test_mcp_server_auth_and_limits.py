"""MCP auth, limiting, kill-switch, and isolation tests."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import httpx
import pytest

from mcp_server.config import MCPConfig
from mcp_server.ratelimit import TokenBucketRateLimiter
from tests.mcp_server_test_support import (
    TOKEN_A,
    TOKEN_B,
    TOKEN_INVALID,
    MCPHarness,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_missing_bearer_is_mcp_auth_error_without_api_call() -> None:
    async with MCPHarness() as harness:
        message = await harness.call_tool(
            "rtbcat_list_buyers",
            {},
            token=None,
        )
        request_count = harness.state.api_requests

    assert request_count == 0
    assert message["error"]["data"] == {
        "error_type": "authentication",
        "http_status": 401,
        "retryable": False,
    }
    assert "result" not in message


@pytest.mark.asyncio
async def test_invalid_or_revoked_bearer_preserves_api_401() -> None:
    async with MCPHarness() as harness:
        message = await harness.call_tool(
            "rtbcat_list_buyers",
            {},
            token=TOKEN_INVALID,
        )
        request_count = harness.state.api_requests

    assert request_count == 1
    assert message["error"]["data"]["http_status"] == 401
    assert message["error"]["data"]["error_type"] == "authentication"
    assert TOKEN_INVALID not in json.dumps(message)


@pytest.mark.asyncio
async def test_rate_limit_n_plus_one_call_is_retryable_error() -> None:
    async with MCPHarness(rate_limit=2) as harness:
        first = await harness.call_tool("rtbcat_list_buyers", {})
        second = await harness.call_tool("rtbcat_list_buyers", {})
        third = await harness.call_tool("rtbcat_list_buyers", {})
        request_count = harness.state.api_requests

    assert "result" in first
    assert "result" in second
    assert request_count == 2
    assert third["error"]["data"]["http_status"] == 429
    assert third["error"]["data"]["retryable"] is True
    assert third["error"]["data"]["retry_after_seconds"] == 30
    assert "Retry in 30 seconds" in third["error"]["message"]


@pytest.mark.asyncio
async def test_rate_limit_buckets_are_independent_hashed_credentials() -> None:
    limiter = TokenBucketRateLimiter(1)
    async with MCPHarness(limiter=limiter) as harness:
        first_a = await harness.call_tool(
            "rtbcat_list_buyers", {}, token=TOKEN_A
        )
        second_a = await harness.call_tool(
            "rtbcat_list_buyers", {}, token=TOKEN_A
        )
        first_b = await harness.call_tool(
            "rtbcat_list_buyers", {}, token=TOKEN_B
        )

    assert "result" in first_a
    assert second_a["error"]["data"]["http_status"] == 429
    assert "result" in first_b
    assert limiter.bucket_keys == {
        limiter.token_key(TOKEN_A),
        limiter.token_key(TOKEN_B),
    }
    assert TOKEN_A not in limiter.bucket_keys
    assert TOKEN_B not in limiter.bucket_keys


def test_rate_limit_refills_continuously_per_minute() -> None:
    now = [100.0]
    limiter = TokenBucketRateLimiter(2, clock=lambda: now[0])

    assert limiter.consume(TOKEN_A) is None
    assert limiter.consume(TOKEN_A) is None
    assert limiter.consume(TOKEN_A) == pytest.approx(30.0)

    now[0] += 30.0
    assert limiter.consume(TOKEN_A) is None


@pytest.mark.asyncio
async def test_kill_switch_disabled_keeps_health_green_and_rejects_mcp() -> None:
    async with MCPHarness(enabled=False) as harness:
        health = await harness.mcp_http.get("/health")
        mcp_response = await harness.mcp_http.post(
            "/mcp",
            headers={"accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            },
        )

    assert health.status_code == 200
    assert health.json() == {"enabled": False}
    assert mcp_response.status_code == 503
    assert mcp_response.json() == {
        "detail": "MCP server disabled by CATSCAN_MCP_ENABLED."
    }


@pytest.mark.asyncio
async def test_kill_switch_enabled_health_and_tool_call_work() -> None:
    async with MCPHarness(enabled=True) as harness:
        health = await harness.mcp_http.get("/health")
        message = await harness.call_tool("rtbcat_list_buyers", {})

    assert health.status_code == 200
    assert health.json() == {"enabled": True}
    assert "result" in message


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", " on "])
def test_kill_switch_uses_scheduler_guard_truthiness(value: str) -> None:
    config = MCPConfig.from_env({"CATSCAN_MCP_ENABLED": value})
    assert config.enabled is True


def test_kill_switch_defaults_off() -> None:
    config = MCPConfig.from_env({})
    assert config.enabled is False
    assert config.api_base_url == "http://api:8000"
    assert config.port == 8010
    assert config.rate_limit_per_minute == 60


@pytest.mark.asyncio
async def test_timeout_is_retryable_protocol_error() -> None:
    async def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    async with MCPHarness(
        upstream_transport=httpx.MockTransport(timeout)
    ) as harness:
        message = await harness.call_tool("rtbcat_list_buyers", {})

    assert "result" not in message
    assert message["error"]["data"] == {
        "error_type": "agent_api_unreachable",
        "http_status": 503,
        "retryable": True,
    }


@pytest.mark.asyncio
async def test_tool_descriptions_publish_all_limits() -> None:
    async with MCPHarness() as harness:
        tools = await harness.app.mcp_server.list_tools()

    assert len(tools) == 7
    for tool in tools:
        description = " ".join((tool.description or "").lower().split())
        assert "token-scoped" in description
        assert "90 days" in description
        assert "100" in description
        assert "clicks are never available" in description


def test_mcp_package_has_no_repo_package_imports() -> None:
    forbidden = {
        "api",
        "services",
        "storage",
        "collectors",
        "analytics",
        "importers",
        "config",
        "utils",
    }
    violations: list[str] = []
    package_root = REPO_ROOT / "mcp_server"

    for source_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(source_path.read_text(), filename=str(source_path))
        for node in ast.walk(tree):
            imported_roots: list[str] = []
            if isinstance(node, ast.Import):
                imported_roots = [
                    alias.name.split(".", 1)[0] for alias in node.names
                ]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported_roots = [(node.module or "").split(".", 1)[0]]
            for root in imported_roots:
                if root in forbidden:
                    violations.append(
                        f"{source_path.relative_to(package_root)}:{node.lineno}: {root}"
                    )

    assert violations == []


def test_mcp_package_uses_only_isolated_runtime_dependencies() -> None:
    package_root = REPO_ROOT / "mcp_server"
    allowed_third_party = {"httpx", "mcp", "uvicorn"}
    unexpected_imports: list[str] = []
    combined_source = ""

    for source_path in sorted(package_root.rglob("*.py")):
        source = source_path.read_text()
        combined_source += source.lower()
        tree = ast.parse(
            source,
            filename=str(source_path),
            feature_version=(3, 11),
        )
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                roots = [(node.module or "").split(".", 1)[0]]
            for root in roots:
                if (
                    root
                    and root not in sys.stdlib_module_names
                    and root not in allowed_third_party
                ):
                    unexpected_imports.append(
                        f"{source_path.relative_to(package_root)}:{node.lineno}: {root}"
                    )

    assert unexpected_imports == []
    for forbidden_text in (
        "postgresql://",
        "postgres_dsn",
        "select * from",
        "insert into",
        "delete from",
        "import logging",
        "from logging",
    ):
        assert forbidden_text not in combined_source


def test_mcp_runtime_requirements_are_minimal_and_pinned() -> None:
    requirements = (REPO_ROOT / "requirements-mcp.txt").read_text().splitlines()
    assert requirements == [
        "mcp==2.0.0",
        "httpx==0.28.1",
        "uvicorn==0.41.0",
    ]


def test_mcp_dockerfile_is_minimal_non_root_and_health_checked() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.mcp").read_text()
    assert dockerfile.count("FROM python:3.11-slim-bookworm") == 2
    assert "--uid 10001" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "COPY --chown=rtbcat:rtbcat mcp_server/ ./mcp_server/" in dockerfile
    assert "COPY --chown=rtbcat:rtbcat . ." not in dockerfile
    assert 'LABEL org.opencontainers.image.revision="${GIT_SHA}"' in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "urllib.request.urlopen" in dockerfile
    assert "curl" not in dockerfile
    assert "EXPOSE 8010" in dockerfile
    assert "--host 0.0.0.0" in dockerfile
    assert "${CATSCAN_MCP_PORT:-8010}" in dockerfile


def test_mcp_package_and_workflows_are_wired() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    security = (REPO_ROOT / ".github/workflows/security.yml").read_text()
    build = (
        REPO_ROOT / ".github/workflows/build-and-push-ghcr.yml"
    ).read_text()

    assert '"mcp_server"' in pyproject
    assert '"mcp_server.tools"' in pyproject
    assert "requirements-mcp.txt" in security
    assert "tests/test_mcp_server_tools.py" in build
    assert "tests/test_mcp_server_auth_and_limits.py" in build


def test_public_mcp_docs_cover_shipped_contract() -> None:
    docs = (REPO_ROOT / "docs/MCP_SERVER.md").read_text()
    tool_names = {
        "rtbcat_list_buyers",
        "rtbcat_search_creatives",
        "rtbcat_get_creative",
        "rtbcat_get_creative_asset",
        "rtbcat_get_daily_spend",
        "rtbcat_get_creative_performance",
        "rtbcat_check_data_quality",
    }
    for tool_name in tool_names:
        assert tool_name in docs
    assert "https://mcp.rtb.cat/mcp" in docs
    assert "Streamable HTTP" in docs
    assert "Authorization" in docs
    assert "POST /agent/v1/tokens" in docs
    assert "DELETE /agent/v1/tokens/{id}" in docs
    assert "spend_figures_withheld" in docs
    for variable in (
        "CATSCAN_MCP_ENABLED",
        "RTBCAT_API_BASE_URL",
        "CATSCAN_MCP_PORT",
        "CATSCAN_MCP_RATE_LIMIT_PER_MINUTE",
    ):
        assert variable in docs
