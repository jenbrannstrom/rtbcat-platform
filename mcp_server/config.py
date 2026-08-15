"""Environment-only configuration for the standalone MCP process."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _positive_int(value: str, *, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be at least 1.")
    return parsed


@dataclass(frozen=True)
class MCPConfig:
    """Configuration read once when the server process starts."""

    enabled: bool = False
    api_base_url: str = "http://api:8000"
    port: int = 8010
    rate_limit_per_minute: int = 60

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> MCPConfig:
        values = os.environ if environ is None else environ
        return cls(
            enabled=(
                values.get("CATSCAN_MCP_ENABLED", "").strip().lower()
                in _TRUE_VALUES
            ),
            api_base_url=values.get(
                "RTBCAT_API_BASE_URL", "http://api:8000"
            ).rstrip("/"),
            port=_positive_int(
                values.get("CATSCAN_MCP_PORT", "8010"),
                name="CATSCAN_MCP_PORT",
            ),
            rate_limit_per_minute=_positive_int(
                values.get("CATSCAN_MCP_RATE_LIMIT_PER_MINUTE", "60"),
                name="CATSCAN_MCP_RATE_LIMIT_PER_MINUTE",
            ),
        )
