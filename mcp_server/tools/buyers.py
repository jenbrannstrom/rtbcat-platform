"""Buyer-list MCP tool."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from .common import ToolRuntime


def register_buyer_tools(server: MCPServer, runtime: ToolRuntime) -> None:
    @server.tool(name="rtbcat_list_buyers", structured_output=False)
    async def list_buyers(context: Context) -> dict[str, Any]:
        """List buyers visible to the caller's token and seat grants.

        Buyer access is always token-scoped. Date-window tools are capped at
        90 days, creative batches at 100 IDs, and clicks are never available
        in creative evidence.
        """
        return await runtime.request(context, "GET", "/agent/v1/buyers")
