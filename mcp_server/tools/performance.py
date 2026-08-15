"""Daily-spend and creative-performance MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from .common import ToolRuntime, withhold_unreconciled_spend


def register_performance_tools(
    server: MCPServer,
    runtime: ToolRuntime,
) -> None:
    @server.tool(name="rtbcat_get_daily_spend", structured_output=False)
    async def get_daily_spend(
        buyer_id: str,
        start_date: str,
        end_date: str,
        context: Context,
        include_empty: bool = True,
    ) -> dict[str, Any]:
        """Get canonical daily spend for one token-scoped buyer.

        The inclusive date window is capped at 90 days. Creative batches are
        capped at 100 IDs. Creative clicks are never available; canonical
        daily-spend clicks come from the buyer-grain source when present.
        """
        payload = await runtime.request(
            context,
            "GET",
            "/agent/v1/daily-spend",
            params={
                "buyer_id": buyer_id,
                "start_date": start_date,
                "end_date": end_date,
                "include_empty": include_empty,
            },
        )
        return withhold_unreconciled_spend(payload)

    @server.tool(
        name="rtbcat_get_creative_performance",
        structured_output=False,
    )
    async def get_creative_performance(
        buyer_id: str,
        creative_ids: list[str],
        start_date: str,
        end_date: str,
        context: Context,
        tolerance_pct: float = 1.0,
    ) -> dict[str, Any]:
        """Get precomputed performance for a token-scoped creative batch.

        The inclusive window is capped at 90 days and the batch at 100
        creative IDs. Clicks are never available. Unreconciled allocated
        spend is withheld while ranking and non-spend evidence remain.
        """
        payload = await runtime.request(
            context,
            "POST",
            "/agent/v1/creative-performance/batch",
            json={
                "buyer_id": buyer_id,
                "creative_ids": creative_ids,
                "start_date": start_date,
                "end_date": end_date,
                "tolerance_pct": tolerance_pct,
            },
        )
        return withhold_unreconciled_spend(payload)
