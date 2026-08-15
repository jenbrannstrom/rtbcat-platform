"""Shared auth, request, and spend-safety behavior for MCP tools."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import Context

from ..client import AgentAPIClient
from ..errors import (
    AgentAPIResponseError,
    AgentAPIUnavailableError,
    agent_api_error,
    agent_api_unavailable_error,
    authentication_error,
    rate_limit_error,
)
from ..ratelimit import TokenBucketRateLimiter


@dataclass(frozen=True)
class ToolRuntime:
    """Dependencies shared by every registered tool and resource."""

    client: AgentAPIClient
    rate_limiter: TokenBucketRateLimiter

    async def request(
        self,
        context: Context,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = _bearer_token(context)
        retry_after = self.rate_limiter.consume(token)
        if retry_after is not None:
            raise rate_limit_error(retry_after)
        try:
            return await self.client.request_json(
                method,
                path,
                token=token,
                params=params,
                json=json,
            )
        except AgentAPIResponseError as exc:
            raise agent_api_error(exc) from None
        except AgentAPIUnavailableError:
            raise agent_api_unavailable_error() from None


def _bearer_token(context: Context) -> str:
    headers = context.headers or {}
    authorization = next(
        (
            value
            for key, value in headers.items()
            if key.lower() == "authorization"
        ),
        "",
    )
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise authentication_error()
    return token.strip()


def compact_params(**values: Any) -> dict[str, Any]:
    """Drop absent optional query parameters without changing supplied values."""
    return {key: value for key, value in values.items() if value is not None}


def withhold_unreconciled_spend(payload: dict[str, Any]) -> dict[str, Any]:
    """Hide allocated spend while preserving ranking and provenance evidence."""
    allocation = _unreconciled_allocation(payload)
    if allocation is None:
        return payload
    transformed = _null_spend_fields(payload)
    assert isinstance(transformed, dict)
    transformed["spend_figures_withheld"] = True
    transformed["allocation"] = copy.deepcopy(allocation)
    return transformed


def _unreconciled_allocation(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        provenance = value.get("provenance")
        if isinstance(provenance, dict):
            allocation_value = provenance.get("allocation")
            allocation = (
                allocation_value
                if isinstance(allocation_value, dict)
                else provenance
            )
            status = allocation.get("allocation_status")
            if (
                status is not None
                and status != "reconciled"
                and provenance.get("is_canonical") is not True
            ):
                return allocation
        for child in value.values():
            found = _unreconciled_allocation(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _unreconciled_allocation(child)
            if found is not None:
                return found
    return None


def _null_spend_fields(value: Any, *, in_allocation: bool = False) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in value.items():
            child_is_allocation = in_allocation or key == "allocation"
            if not child_is_allocation and (
                key.endswith("spend_micros") or key == "avg_cpm_micros"
            ):
                output[key] = None
            else:
                output[key] = _null_spend_fields(
                    child,
                    in_allocation=child_is_allocation,
                )
        return output
    if isinstance(value, list):
        return [
            _null_spend_fields(child, in_allocation=in_allocation)
            for child in value
        ]
    return copy.deepcopy(value)
