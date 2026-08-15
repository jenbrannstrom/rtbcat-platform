"""Creative asset-reference MCP tool."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from .common import ToolRuntime


def register_asset_tools(server: MCPServer, runtime: ToolRuntime) -> None:
    @server.tool(name="rtbcat_get_creative_asset", structured_output=False)
    async def get_creative_asset(
        creative_id: str,
        context: Context,
    ) -> dict[str, Any]:
        """Get token-scoped creative asset reference URLs, never asset bytes.

        Buyer isolation returns the API's not-found semantics. Date windows
        are capped at 90 days, creative batches at 100 IDs, and clicks are
        never available in creative evidence.
        """
        return await runtime.request(
            context,
            "GET",
            f"/agent/v1/creatives/{creative_id}/assets",
        )
