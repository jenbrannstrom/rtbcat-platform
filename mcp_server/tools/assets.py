"""Creative asset-reference MCP tool and resource template."""

from __future__ import annotations

import json
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

    @server.resource(
        "rtbcat://creatives/{creative_id}/assets",
        name="rtbcat_creative_assets",
        description=(
            "Authenticated reference-only asset manifest for one token-scoped "
            "creative; no image, video, or HTML bytes are fetched."
        ),
        mime_type="application/json",
    )
    async def creative_asset_resource(
        creative_id: str,
        context: Context,
    ) -> str:
        payload = await runtime.request(
            context,
            "GET",
            f"/agent/v1/creatives/{creative_id}/assets",
        )
        return json.dumps(payload, separators=(",", ":"))
