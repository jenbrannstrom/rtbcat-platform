"""Protocol-safe MCP errors for adapter failures."""

from __future__ import annotations

from typing import Any

from mcp.shared.exceptions import MCPError


AUTH_ERROR = -32001
PERMISSION_ERROR = -32003
NOT_FOUND_ERROR = -32004
API_UNAVAILABLE_ERROR = -32005
RATE_LIMIT_ERROR = -32029
UPSTREAM_ERROR = -32050
INVALID_PARAMS = -32602


class AgentAPIResponseError(Exception):
    """An HTTP error response returned by the Agent API."""

    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(status_code)
        self.status_code = status_code
        self.detail = detail


class AgentAPIUnavailableError(Exception):
    """The Agent API could not be reached or did not return valid JSON."""


def authentication_error(
    message: str = "Bearer authentication required.",
) -> MCPError:
    return MCPError(
        code=AUTH_ERROR,
        message=message,
        data={
            "error_type": "authentication",
            "http_status": 401,
            "retryable": False,
        },
    )


def rate_limit_error(retry_after_seconds: float) -> MCPError:
    retry_after = max(1, int(retry_after_seconds + 0.999))
    return MCPError(
        code=RATE_LIMIT_ERROR,
        message=f"Rate limit exceeded. Retry in {retry_after} seconds.",
        data={
            "error_type": "rate_limit",
            "http_status": 429,
            "retryable": True,
            "retry_after_seconds": retry_after,
        },
    )


def agent_api_error(exc: AgentAPIResponseError) -> MCPError:
    status = exc.status_code
    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else "RTBcat Agent API rejected the request."
    )

    if status == 401:
        code = AUTH_ERROR
        error_type = "authentication"
    elif status == 403:
        code = PERMISSION_ERROR
        error_type = "permission"
    elif status == 404:
        code = NOT_FOUND_ERROR
        error_type = "not_found"
    elif status in {400, 422}:
        code = INVALID_PARAMS
        error_type = "invalid_request"
    else:
        code = UPSTREAM_ERROR
        error_type = "agent_api"

    return MCPError(
        code=code,
        message=message,
        data={
            "error_type": error_type,
            "http_status": status,
            "retryable": status >= 500,
            "detail": exc.detail,
        },
    )


def agent_api_unavailable_error() -> MCPError:
    return MCPError(
        code=API_UNAVAILABLE_ERROR,
        message="RTBcat Agent API is unreachable. Retry the request.",
        data={
            "error_type": "agent_api_unreachable",
            "http_status": 503,
            "retryable": True,
        },
    )
