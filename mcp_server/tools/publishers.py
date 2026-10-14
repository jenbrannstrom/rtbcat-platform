"""Live publisher identity lookup; authenticated upstream through the Agent API."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from .common import ToolRuntime


def register_publisher_tools(server: MCPServer, runtime: ToolRuntime) -> None:
    @server.tool(name="rtbcat_lookup_publisher", structured_output=False)
    async def lookup_publisher(
        buyer_id: str,
        context: Context,
        app_id: str | None = None,
        domain: str | None = None,
        publisher_name: str | None = None,
        include_google: bool = True,
    ) -> dict:
        """Look up who owns, manages or sells an app/site and available contacts.

        Requires agent:publishers:read and access to buyer_id. Supply an Android
        package, numeric Apple app ID, website domain, or publisher_name for a
        company-name search. Name matches are candidates. Fetches live metadata;
        partial results include source failures. Manager declarations, authorized
        sellers, Google profiles and support contacts are distinct evidence.
        This does not assess spend or establish an exclusive commercial mandate.
        """
        return await runtime.request(
            context,
            "POST",
            "/agent/v1/publisher-lookup",
            json={
                "buyer_id": buyer_id,
                "app_id": app_id,
                "domain": domain,
                "publisher_name": publisher_name,
                "include_google": include_google,
            },
        )
