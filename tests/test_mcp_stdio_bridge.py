"""Client credential boundaries and real MCP wire compatibility for the bridge."""

import asyncio
import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock

import pytest
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from integrations.grok.stdio_bridge import ReadOnlyBridge, make_http_client, settings


@pytest.mark.parametrize("endpoint", [
    "http://example.com/mcp", "https://user:pass@example.com/mcp",
    "https://example.com/mcp?token=bad", "https://example.com/mcp#fragment",
    "https://example.com:invalid/mcp", "https:///mcp",
])
def test_unsafe_endpoint_rejected(monkeypatch, endpoint):
    monkeypatch.setenv("RTBCAT_MCP_URL", endpoint)
    monkeypatch.setenv("RTBCAT_AGENT_TOKEN", "cat_agent_test_fixture")
    with pytest.raises(ValueError, match="HTTPS"):
        settings()


@pytest.mark.parametrize("token", ["", "wrong-prefix", "cat_agent_test\nheader"])
def test_missing_or_malformed_token_rejected(monkeypatch, token):
    monkeypatch.delenv("RTBCAT_MCP_URL", raising=False)
    monkeypatch.setenv("RTBCAT_AGENT_TOKEN", token)
    with pytest.raises(ValueError, match="secure secret entry"):
        settings()


@pytest.mark.asyncio
async def test_http_client_refuses_redirects_and_ambient_proxies():
    async with make_http_client("cat_agent_test_fixture") as client:
        assert client.follow_redirects is False
        assert client.trust_env is False


@pytest.mark.asyncio
async def test_unlisted_tool_never_reaches_upstream():
    upstream = AsyncMock()
    result = await ReadOnlyBridge(upstream).call_tool(
        None, types.CallToolRequestParams(name="run_sql", arguments={"sql": "DELETE FROM users"}),
    )
    assert result.is_error
    upstream.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_transport_error_does_not_expose_credentials():
    upstream = AsyncMock()
    upstream.call_tool.side_effect = RuntimeError("Bearer cat_agent_test_fixture")
    result = await ReadOnlyBridge(upstream).call_tool(
        None, types.CallToolRequestParams(name="rtbcat_list_buyers"),
    )
    assert result.is_error
    assert "cat_agent_" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_pagination_and_schemas_preserved_but_unknown_tools_hidden():
    upstream = AsyncMock()
    tool = types.Tool(name="rtbcat_list_buyers", inputSchema={"type": "object"})
    upstream.list_tools.return_value = types.ListToolsResult(
        tools=[tool, types.Tool(name="write_config", inputSchema={"type": "object"})],
        nextCursor="opaque-cursor",
    )
    params = types.PaginatedRequestParams(cursor="previous-cursor")
    result = await ReadOnlyBridge(upstream).list_tools(None, params)
    assert result.tools == [tool]
    assert result.next_cursor == "opaque-cursor"
    upstream.list_tools.assert_awaited_once_with(params=params)


@pytest.mark.asyncio
async def test_stdio_handshake_listing_and_structured_call():
    """Use real pipes and the SDK client to exercise initialization and tool calls."""
    script = dedent("""
        import asyncio
        from unittest.mock import AsyncMock
        from mcp import types
        from mcp.server.stdio import stdio_server
        from integrations.grok.stdio_bridge import ReadOnlyBridge

        async def main():
            upstream = AsyncMock()
            upstream.list_tools.return_value = types.ListToolsResult(tools=[
                types.Tool(name="rtbcat_list_buyers", inputSchema={"type": "object"}),
            ])
            upstream.call_tool.return_value = types.CallToolResult(
                content=[types.TextContent(type="text", text="buyer evidence")],
                structuredContent={"buyers": [{"buyer_id": "123"}], "partial": False},
            )
            server = ReadOnlyBridge(upstream).server()
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())
        asyncio.run(main())
    """)
    params = StdioServerParameters(
        command=sys.executable, args=["-c", script],
        env={"PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )
    async with asyncio.timeout(15):
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                initialized = await session.initialize()
                assert initialized.server_info.name == "rtbcat-readonly-bridge"
                tools = await session.list_tools()
                assert [t.name for t in tools.tools] == ["rtbcat_list_buyers"]
                result = await session.call_tool("rtbcat_list_buyers", {})
                assert result.structured_content["buyers"] == [{"buyer_id": "123"}]
                assert result.structured_content["partial"] is False
                denied = await session.call_tool("run_sql", {})
                assert denied.is_error
