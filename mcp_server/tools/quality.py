"""Data-quality MCP tool."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from .common import ToolRuntime


def register_quality_tools(server: MCPServer, runtime: ToolRuntime) -> None:
    @server.tool(name="rtbcat_check_data_quality", structured_output=False)
    async def check_data_quality(
        buyer_id: str,
        start_date: str,
        end_date: str,
        context: Context,
        tolerance_pct: float = 1.0,
    ) -> dict[str, Any]:
        """Compare spend lanes for one token-scoped buyer and window.

        The inclusive window is capped at 90 days and reports whether creative
        allocation reconciles. Creative batches are capped at 100 IDs, and
        clicks are never available in creative evidence.
        """
        return await runtime.request(
            context,
            "GET",
            "/agent/v1/data-quality",
            params={
                "buyer_id": buyer_id,
                "start_date": start_date,
                "end_date": end_date,
                "tolerance_pct": tolerance_pct,
            },
        )
