"""MCP-to-Agent-API contract tests for all seven read tools."""

from __future__ import annotations

import json

import httpx
import pytest

from tests.mcp_server_test_support import (
    BUYER_A,
    BUYER_B,
    CREATIVE_A,
    CURSOR,
    MISSING_CREATIVE,
    PERFORMANCE_ARGUMENTS,
    SEARCH_ARGUMENTS,
    TOKEN_A,
    TOKEN_STATS,
    WINDOW_ARGUMENTS,
    MCPHarness,
    allocation,
    creative_assets_payload,
)


@pytest.mark.asyncio
async def test_all_seven_tools_equal_direct_agent_api_contracts() -> None:
    async with MCPHarness() as harness:
        cases = [
            (
                "rtbcat_list_buyers",
                {},
                ("GET", "/agent/v1/buyers", None, None),
            ),
            (
                "rtbcat_search_creatives",
                SEARCH_ARGUMENTS,
                (
                    "GET",
                    "/agent/v1/creatives",
                    {
                        **SEARCH_ARGUMENTS,
                        "approval_filter": "all",
                        "activity": "all",
                        "sort_by": "spend",
                    },
                    None,
                ),
            ),
            (
                "rtbcat_get_creative",
                {"creative_id": CREATIVE_A},
                ("GET", f"/agent/v1/creatives/{CREATIVE_A}", None, None),
            ),
            (
                "rtbcat_get_creative_asset",
                {"creative_id": CREATIVE_A},
                (
                    "GET",
                    f"/agent/v1/creatives/{CREATIVE_A}/assets",
                    None,
                    None,
                ),
            ),
            (
                "rtbcat_get_daily_spend",
                WINDOW_ARGUMENTS,
                (
                    "GET",
                    "/agent/v1/daily-spend",
                    {**WINDOW_ARGUMENTS, "include_empty": True},
                    None,
                ),
            ),
            (
                "rtbcat_get_creative_performance",
                PERFORMANCE_ARGUMENTS,
                (
                    "POST",
                    "/agent/v1/creative-performance/batch",
                    None,
                    {**PERFORMANCE_ARGUMENTS, "tolerance_pct": 1.0},
                ),
            ),
            (
                "rtbcat_check_data_quality",
                WINDOW_ARGUMENTS,
                (
                    "GET",
                    "/agent/v1/data-quality",
                    {**WINDOW_ARGUMENTS, "tolerance_pct": 1.0},
                    None,
                ),
            ),
        ]

        for tool_name, arguments, direct in cases:
            message = await harness.call_tool(tool_name, arguments)
            method, path, params, body = direct
            response = await harness.direct_request(
                method,
                path,
                params=params,
                json_body=body,
            )
            assert response.status_code == 200
            assert harness.tool_payload(message) == response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        (
            "rtbcat_search_creatives",
            {**SEARCH_ARGUMENTS, "buyer_id": BUYER_B},
        ),
        (
            "rtbcat_get_daily_spend",
            {**WINDOW_ARGUMENTS, "buyer_id": BUYER_B},
        ),
        (
            "rtbcat_get_creative_performance",
            {**PERFORMANCE_ARGUMENTS, "buyer_id": BUYER_B},
        ),
        (
            "rtbcat_check_data_quality",
            {**WINDOW_ARGUMENTS, "buyer_id": BUYER_B},
        ),
    ],
)
async def test_every_buyer_argument_preserves_api_403(
    tool_name: str,
    arguments: dict,
) -> None:
    async with MCPHarness() as harness:
        message = await harness.call_tool(tool_name, arguments, token=TOKEN_A)

    assert message["error"]["data"]["http_status"] == 403
    assert message["error"]["data"]["error_type"] == "permission"
    assert message["error"]["message"] == (
        "Agent token is not scoped to this buyer."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "required_scope"),
    [
        (
            "rtbcat_search_creatives",
            SEARCH_ARGUMENTS,
            "agent:creatives:read",
        ),
        (
            "rtbcat_get_creative",
            {"creative_id": CREATIVE_A},
            "agent:creatives:read",
        ),
        (
            "rtbcat_get_creative_asset",
            {"creative_id": CREATIVE_A},
            "agent:assets:read",
        ),
        (
            "rtbcat_get_creative_performance",
            PERFORMANCE_ARGUMENTS,
            "agent:creative-performance:read",
        ),
    ],
)
async def test_stats_only_credential_preserves_creative_scope_403(
    tool_name: str,
    arguments: dict,
    required_scope: str,
) -> None:
    async with MCPHarness() as harness:
        message = await harness.call_tool(
            tool_name,
            arguments,
            token=TOKEN_STATS,
        )

    assert message["error"]["data"]["http_status"] == 403
    assert required_scope in message["error"]["message"]


@pytest.mark.asyncio
async def test_asset_tool_returns_reference_manifest_without_bytes() -> None:
    async with MCPHarness() as harness:
        templates = await harness.app.mcp_server.list_resource_templates()
        assert templates == []
        message = await harness.call_tool(
            "rtbcat_get_creative_asset",
            {"creative_id": CREATIVE_A},
        )

    manifest = harness.tool_payload(message)
    assert manifest == creative_assets_payload()
    assert manifest["references_only"] is True
    assert "bytes" not in json.dumps(manifest).lower()


@pytest.mark.asyncio
async def test_non_reconciling_search_withholds_spend_and_keeps_rank() -> None:
    async with MCPHarness(allocation_status="non_reconciling") as harness:
        message = await harness.call_tool(
            "rtbcat_search_creatives",
            SEARCH_ARGUMENTS,
        )

    payload = harness.tool_payload(message)
    metrics = payload["creatives"][0]["metrics"]
    assert metrics["spend_micros"] is None
    assert metrics["spend_rank"] == 1
    assert payload["spend_figures_withheld"] is True
    assert payload["allocation"] == allocation("non_reconciling")
    assert metrics["provenance"]["allocation"] == allocation(
        "non_reconciling"
    )


@pytest.mark.asyncio
async def test_not_applicable_allocated_search_withholds_spend() -> None:
    async with MCPHarness(allocation_status="not_applicable") as harness:
        message = await harness.call_tool(
            "rtbcat_search_creatives",
            SEARCH_ARGUMENTS,
        )

    payload = harness.tool_payload(message)
    assert payload["creatives"][0]["metrics"]["spend_micros"] is None
    assert payload["spend_figures_withheld"] is True
    assert payload["allocation"]["allocation_status"] == "not_applicable"


@pytest.mark.asyncio
async def test_reconciled_search_is_byte_equivalent_json() -> None:
    async with MCPHarness(allocation_status="reconciled") as harness:
        message = await harness.call_tool(
            "rtbcat_search_creatives",
            SEARCH_ARGUMENTS,
        )
        direct = await harness.direct_request(
            "GET",
            "/agent/v1/creatives",
            params={
                **SEARCH_ARGUMENTS,
                "approval_filter": "all",
                "activity": "all",
                "sort_by": "spend",
            },
        )

    tool_json = json.dumps(
        harness.tool_payload(message),
        separators=(",", ":"),
    )
    direct_json = json.dumps(direct.json(), separators=(",", ":"))
    assert tool_json == direct_json


@pytest.mark.asyncio
async def test_non_reconciling_performance_nulls_every_spend_field() -> None:
    async with MCPHarness(allocation_status="non_reconciling") as harness:
        message = await harness.call_tool(
            "rtbcat_get_creative_performance",
            PERFORMANCE_ARGUMENTS,
        )

    payload = harness.tool_payload(message)
    row = payload["performance"][0]
    assert row["total_spend_micros"] is None
    assert row["avg_cpm_micros"] is None
    assert row["total_impressions"] == 1_000
    assert row["provenance"]["allocation"] == allocation(
        "non_reconciling"
    )
    assert payload["spend_figures_withheld"] is True


@pytest.mark.asyncio
async def test_canonical_daily_spend_passes_not_applicable_through() -> None:
    async with MCPHarness(allocation_status="not_applicable") as harness:
        message = await harness.call_tool(
            "rtbcat_get_daily_spend",
            WINDOW_ARGUMENTS,
        )
        direct = await harness.direct_request(
            "GET",
            "/agent/v1/daily-spend",
            params={**WINDOW_ARGUMENTS, "include_empty": True},
        )

    assert harness.tool_payload(message) == direct.json()
    assert harness.tool_payload(message)["summary"]["total_spend_micros"] == 2_000_000
    assert "spend_figures_withheld" not in harness.tool_payload(message)


@pytest.mark.asyncio
async def test_freshness_and_missing_dates_are_untouched() -> None:
    async with MCPHarness() as harness:
        message = await harness.call_tool(
            "rtbcat_search_creatives",
            SEARCH_ARGUMENTS,
        )

    provenance = harness.tool_payload(message)["creatives"][0]["metrics"][
        "provenance"
    ]
    assert provenance["latest_complete_date"] == "2026-08-01"
    assert provenance["missing_source_dates"] == ["2026-08-02"]


@pytest.mark.asyncio
async def test_search_cursor_reaches_agent_api_unchanged() -> None:
    async with MCPHarness() as harness:
        await harness.call_tool(
            "rtbcat_search_creatives",
            {**SEARCH_ARGUMENTS, "cursor": CURSOR},
        )

    assert harness.state.creative_search_calls[-1]["cursor"] == CURSOR


@pytest.mark.asyncio
async def test_not_found_detail_is_preserved_as_protocol_error() -> None:
    async with MCPHarness() as harness:
        message = await harness.call_tool(
            "rtbcat_get_creative",
            {"creative_id": MISSING_CREATIVE},
        )

    assert message["error"]["data"]["http_status"] == 404
    assert message["error"]["data"]["error_type"] == "not_found"
    assert message["error"]["message"] == "Creative not found."


@pytest.mark.asyncio
async def test_api_400_detail_is_preserved() -> None:
    async with MCPHarness() as harness:
        message = await harness.call_tool(
            "rtbcat_get_daily_spend",
            {
                "buyer_id": BUYER_A,
                "start_date": "2026-08-02",
                "end_date": "2026-08-01",
            },
        )

    assert message["error"]["code"] == -32602
    assert message["error"]["data"]["http_status"] == 400
    assert message["error"]["message"] == (
        "end_date must be on or after start_date."
    )


@pytest.mark.asyncio
async def test_api_422_detail_is_preserved() -> None:
    async with MCPHarness() as harness:
        message = await harness.call_tool(
            "rtbcat_search_creatives",
            {**SEARCH_ARGUMENTS, "sort_by": "clicks"},
        )

    assert message["error"]["code"] == -32602
    assert message["error"]["data"]["http_status"] == 422
    assert isinstance(message["error"]["data"]["detail"], list)


@pytest.mark.asyncio
async def test_api_500_is_error_not_empty_result() -> None:
    async with MCPHarness() as harness:
        harness.state.fail_buyers = True
        message = await harness.call_tool("rtbcat_list_buyers", {})

    assert "result" not in message
    assert message["error"]["data"] == {
        "error_type": "agent_api",
        "http_status": 500,
        "retryable": True,
        "detail": "Synthetic upstream failure.",
    }


@pytest.mark.asyncio
async def test_connect_error_is_retryable_not_empty_result() -> None:
    async def fail_connect(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connection failure", request=request)

    transport = httpx.MockTransport(fail_connect)
    async with MCPHarness(upstream_transport=transport) as harness:
        message = await harness.call_tool("rtbcat_list_buyers", {})

    assert "result" not in message
    assert message["error"]["message"] == (
        "RTBcat Agent API is unreachable. Retry the request."
    )
    assert message["error"]["data"]["retryable"] is True
