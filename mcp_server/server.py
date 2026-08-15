"""Stateless Streamable HTTP MCP application and process entrypoint."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import MCPServer

from . import __version__
from .client import AgentAPIClient
from .config import MCPConfig
from .ratelimit import TokenBucketRateLimiter
from .tools import (
    register_asset_tools,
    register_buyer_tools,
    register_creative_tools,
    register_performance_tools,
    register_quality_tools,
)
from .tools.common import ToolRuntime


ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]


class MCPApplication:
    """Expose public health and gate the MCP transport with a kill switch."""

    def __init__(
        self,
        *,
        enabled: bool,
        mcp_server: MCPServer,
        mcp_app: Any,
        runtime: ToolRuntime,
    ) -> None:
        self.enabled = enabled
        self.mcp_server = mcp_server
        self.mcp_app = mcp_app
        self.runtime = runtime

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        if scope["type"] != "http":
            await self.mcp_app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health":
            await _json_response(send, 200, {"enabled": self.enabled})
            return
        if (path == "/mcp" or path.startswith("/mcp/")) and not self.enabled:
            await _json_response(
                send,
                503,
                {"detail": "MCP server disabled by CATSCAN_MCP_ENABLED."},
            )
            return
        await self.mcp_app(scope, receive, send)


async def _json_response(
    send: ASGISend,
    status_code: int,
    payload: dict[str, Any],
) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def create_app(
    config: MCPConfig,
    *,
    client: AgentAPIClient | None = None,
    rate_limiter: TokenBucketRateLimiter | None = None,
) -> MCPApplication:
    """Build one configured MCP ASGI application."""
    api_client = client or AgentAPIClient(config.api_base_url)
    limiter = rate_limiter or TokenBucketRateLimiter(
        config.rate_limit_per_minute
    )
    runtime = ToolRuntime(client=api_client, rate_limiter=limiter)

    @asynccontextmanager
    async def lifespan(_server: MCPServer):
        try:
            yield None
        finally:
            await api_client.close()

    server = MCPServer(
        name="rtbcat-readonly",
        title="RTBcat Read-Only MCP",
        description="Buyer-scoped evidence from the RTBcat Agent API.",
        version=__version__,
        lifespan=lifespan,
    )
    register_buyer_tools(server, runtime)
    register_creative_tools(server, runtime)
    register_asset_tools(server, runtime)
    register_performance_tools(server, runtime)
    register_quality_tools(server, runtime)

    streamable_app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host="0.0.0.0",
    )
    return MCPApplication(
        enabled=config.enabled,
        mcp_server=server,
        mcp_app=streamable_app,
        runtime=runtime,
    )


CONFIG = MCPConfig.from_env()
app = create_app(CONFIG)


def main() -> None:
    """Run the configured MCP ASGI application."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=CONFIG.port)


if __name__ == "__main__":
    main()
