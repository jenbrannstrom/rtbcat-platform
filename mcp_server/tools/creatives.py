"""Creative search and detail MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from .common import ToolRuntime, compact_params, withhold_unreconciled_spend


def register_creative_tools(server: MCPServer, runtime: ToolRuntime) -> None:
    @server.tool(name="rtbcat_search_creatives", structured_output=False)
    async def search_creatives(
        buyer_id: str,
        start_date: str,
        end_date: str,
        context: Context,
        domain: str | None = None,
        format: str | None = None,
        approval_filter: str = "all",
        activity: str = "all",
        search: str | None = None,
        sort_by: str = "spend",
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search one token-scoped buyer's spend-ranked creatives.

        The inclusive window is capped at 90 days and pages at 100 creatives;
        pass next_cursor back unchanged. Creative batches are capped at 100.
        Clicks are never available. Unreconciled allocated spend is withheld
        while spend_rank and ordering remain available.
        """
        payload = await runtime.request(
            context,
            "GET",
            "/agent/v1/creatives",
            params=compact_params(
                buyer_id=buyer_id,
                start_date=start_date,
                end_date=end_date,
                domain=domain,
                format=format,
                approval_filter=approval_filter,
                activity=activity,
                search=search,
                sort_by=sort_by,
                cursor=cursor,
                limit=limit,
            ),
        )
        return withhold_unreconciled_spend(payload)

    @server.tool(name="rtbcat_get_creative", structured_output=False)
    async def get_creative(
        creative_id: str,
        context: Context,
    ) -> dict[str, Any]:
        """Get token-scoped creative detail and destination diagnostics.

        Buyer isolation returns the API's not-found semantics. Date windows
        are capped at 90 days, creative batches at 100 IDs, and clicks are
        never available in creative evidence.
        """
        return await runtime.request(
            context,
            "GET",
            f"/agent/v1/creatives/{creative_id}",
        )
