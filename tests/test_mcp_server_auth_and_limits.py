"""MCP auth, limiting, kill-switch, and isolation tests."""

from __future__ import annotations

import ast
import json
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
    package_root = Path(__file__).resolve().parents[1] / "mcp_server"

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
