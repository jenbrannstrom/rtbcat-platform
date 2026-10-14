"""Bridge a stdio MCP client to RTBcat's authenticated HTTPS read tools.

Run with the Python environment installed from requirements-mcp.txt. Credentials
come only from RTBCAT_AGENT_TOKEN; stdout is reserved for the MCP protocol.
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlsplit

import httpx2
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

DEFAULT_ENDPOINT = "https://mcp.rtb.cat/mcp"
ALLOWED_TOOLS = frozenset({
    "rtbcat_list_buyers", "rtbcat_search_creatives", "rtbcat_get_creative",
    "rtbcat_get_creative_asset", "rtbcat_get_daily_spend",
    "rtbcat_get_creative_performance", "rtbcat_check_data_quality",
    "rtbcat_lookup_publisher",
})


def settings() -> tuple[str, str]:
    """Reject unsafe destinations and malformed credentials without echoing them."""
    endpoint = os.environ.get("RTBCAT_MCP_URL", DEFAULT_ENDPOINT)
    token = os.environ.get("RTBCAT_AGENT_TOKEN", "")
    try:
        url = urlsplit(endpoint)
        valid_url = (
            url.scheme == "https" and url.hostname and url.port != 0
            and not url.username and not url.password
            and not url.query and not url.fragment
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("RTBCAT_MCP_URL must be HTTPS, without user info, query or fragment.")
    if not token.startswith("cat_agent_") or any(c.isspace() for c in token):
        raise ValueError("Set RTBCAT_AGENT_TOKEN through the client's secure secret entry.")
    return endpoint, token


def make_http_client(token: str) -> httpx2.AsyncClient:
    # Refuse redirects and ambient proxies so a credential stays at the
    # operator-selected endpoint. TLS certificate verification remains enabled.
    return httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False, trust_env=False, timeout=60.0,
    )


def error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)], isError=True,
    )


class ReadOnlyBridge:
    def __init__(self, upstream: ClientSession):
        self.upstream = upstream

    async def list_tools(self, _context, params):
        result = await self.upstream.list_tools(params=params)
        return result.model_copy(update={
            "tools": [tool for tool in result.tools if tool.name in ALLOWED_TOOLS],
        })

    async def call_tool(self, _context, params: types.CallToolRequestParams):
        if params.name not in ALLOWED_TOOLS:
            return error_result("Tool is not in the RTBcat read-only allowlist.")
        try:
            return await self.upstream.call_tool(
                params.name, params.arguments, read_timeout_seconds=60.0,
            )
        except Exception:
            # Transport exceptions can include response bodies. Do not emit them
            # to a model or log. Upstream tool results retain their normal errors.
            return error_result(
                "RTBcat request failed. Check connectivity, token expiry, scopes and buyer access."
            )

    def server(self) -> Server:
        return Server(
            "rtbcat-readonly-bridge", version="1.0.0",
            on_list_tools=self.list_tools, on_call_tool=self.call_tool,
        )


async def run() -> None:
    endpoint, token = settings()
    async with make_http_client(token) as http_client:
        async with streamable_http_client(endpoint, http_client=http_client) as streams:
            async with ClientSession(*streams, read_timeout_seconds=60.0) as upstream:
                await upstream.initialize()
                server = ReadOnlyBridge(upstream).server()
                async with stdio_server() as (read, write):
                    await server.run(read, write, server.create_initialization_options())


def main() -> int:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return 0
    except Exception:
        print(
            "RTBcat bridge could not start. Check secure token configuration, HTTPS endpoint and network.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
